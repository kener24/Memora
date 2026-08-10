from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from accounts.models import CustomUser
from core.responses import success_response
from organizations.models import Branch, Organization

from .access import get_contract_permissions, is_global_contract_user, scope_contracts
from .choices import (
    ContractActivityAction, ContractStatus, IdempotencyOperation, PaymentFrequency,
)
from .exceptions import ConflictError
from .models import Contract, ContractActivity, ContractIdempotencyKey, ContractPlanItem
from .pagination import ContractPagination
from .pdf import build_contract_pdf
from .permissions import ContractPermission
from .serializers import (
    CancellationSerializer, ContractDetailSerializer, ContractDraftSerializer, ContractListSerializer,
)
from .services import (
    SELLER_ROLE_CODES, allocate_contract_number, plan_is_available, record_contract_activity, snapshot_contract,
)


def idempotency_key(request):
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise ValidationError({"idempotency_key": "Envía una clave de idempotencia para esta operación."})
    if len(key) < 8 or len(key) > 128:
        raise ValidationError({"idempotency_key": "La clave de idempotencia no es válida."})
    return key


class ContractViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (ContractPermission,)
    pagination_class = ContractPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        "contract_number", "customer_name_snapshot", "customer_identity_snapshot",
        "beneficiary_name_snapshot", "plan_name_snapshot", "customer__first_name",
        "customer__last_name", "customer__identity_number", "beneficiary__first_name",
        "beneficiary__last_name", "plan__name", "seller__first_name", "seller__last_name",
    )
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        items = ContractPlanItem.objects.select_related("service", "original_plan_item")
        activities = ContractActivity.objects.select_related("user")
        queryset = Contract.objects.select_related(
            "organization", "branch", "customer", "beneficiary__customer", "plan", "seller",
            "created_by", "cancelled_by",
        ).prefetch_related(Prefetch("plan_items", queryset=items), Prefetch("activities", queryset=activities))
        queryset = scope_contracts(queryset, self.request.user)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("status") in ContractStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("seller"):
            queryset = queryset.filter(seller_id=params["seller"])
        if params.get("plan"):
            queryset = queryset.filter(plan_id=params["plan"])
        if params.get("allow_financing") in {"true", "false"}:
            queryset = queryset.filter(allow_financing=params["allow_financing"] == "true")
        date_from = parse_date(params.get("date_from", ""))
        date_to = parse_date(params.get("date_to", ""))
        if date_from:
            queryset = queryset.filter(sale_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale_date__lte=date_to)
        ordering = {
            "sale_date": ("sale_date",), "-sale_date": ("-sale_date",),
            "total_price": ("total_price",), "-total_price": ("-total_price",),
            "contract_number": ("contract_number",), "-created_at": ("-created_at",),
        }.get(params.get("ordering"), ("-created_at",))
        return queryset.order_by(*ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return ContractListSerializer
        if self.action in {"create", "partial_update", "update"}:
            return ContractDraftSerializer
        return ContractDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        return success_response(
            ContractDetailSerializer(self.get_object(), context={"request": request}).data,
            "Contrato obtenido correctamente.",
        )

    def create(self, request, *args, **kwargs):
        key = idempotency_key(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.validated_data["organization"]
        existing = ContractIdempotencyKey.objects.filter(
            organization=organization, key=key, operation=IdempotencyOperation.CREATE
        ).select_related("contract").first()
        if existing:
            contract = get_object_or_404(scope_contracts(self.get_queryset(), request.user), pk=existing.contract_id)
            return success_response(
                ContractDetailSerializer(contract, context={"request": request}).data,
                "Borrador recuperado de forma idempotente.",
            )
        try:
            with transaction.atomic():
                contract = serializer.save(
                    contract_number=allocate_contract_number(organization),
                    created_by=request.user,
                    status=ContractStatus.DRAFT,
                )
                record_contract_activity(
                    contract, request.user, ContractActivityAction.DRAFT_CREATED,
                    "Se creó el borrador del contrato.",
                )
                ContractIdempotencyKey.objects.create(
                    organization=organization, key=key, operation=IdempotencyOperation.CREATE,
                    contract=contract,
                )
        except IntegrityError:
            existing = ContractIdempotencyKey.objects.filter(
                organization=organization, key=key, operation=IdempotencyOperation.CREATE
            ).select_related("contract").first()
            if not existing:
                raise
            contract = existing.contract
        return success_response(
            ContractDetailSerializer(contract, context={"request": request}).data,
            "Borrador creado correctamente.", status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        contract = self.get_object()
        if contract.status != ContractStatus.DRAFT:
            raise ConflictError("Un contrato confirmado no puede modificarse.")
        serializer = self.get_serializer(contract, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            contract = serializer.save()
            record_contract_activity(
                contract, request.user, ContractActivityAction.DRAFT_UPDATED,
                "Se actualizaron las condiciones del borrador.",
            )
        return success_response(
            ContractDetailSerializer(contract, context={"request": request}).data, "Borrador actualizado."
        )

    @action(detail=True, methods=("post",))
    def confirm(self, request, pk=None):
        key = idempotency_key(request)
        visible = self.get_object()
        existing = ContractIdempotencyKey.objects.filter(
            organization=visible.organization, key=key, operation=IdempotencyOperation.CONFIRM
        ).first()
        if existing:
            if existing.contract_id != visible.pk:
                raise ConflictError("La clave de idempotencia ya corresponde a otra venta.")
            return success_response(
                ContractDetailSerializer(visible, context={"request": request}).data,
                "Contrato recuperado de forma idempotente.",
            )
        try:
            with transaction.atomic():
                contract = scope_contracts(self.get_queryset(), request.user).select_for_update().get(pk=visible.pk)
                if contract.status != ContractStatus.DRAFT:
                    raise ConflictError("Este contrato ya fue confirmado o cancelado.")
                validator = ContractDraftSerializer(
                    contract, data={}, partial=True, context={"request": request}
                )
                validator.is_valid(raise_exception=True)
                if contract.plan.base_price != contract.subtotal:
                    raise ValidationError({
                        "plan": "El precio del plan cambió. Actualiza y revisa el borrador antes de confirmar."
                    })
                if not plan_is_available(contract.plan, contract.branch):
                    raise ValidationError({"plan": "Este plan ya no está disponible para nuevas ventas."})
                snapshot_contract(contract)
                contract.status = ContractStatus.ACTIVE
                contract.save(update_fields=(
                    "plan_name_snapshot", "plan_description_snapshot", "customer_name_snapshot",
                    "customer_identity_snapshot", "customer_address_snapshot", "customer_phone_snapshot",
                    "beneficiary_name_snapshot", "beneficiary_identity_snapshot",
                    "beneficiary_relationship_snapshot", "status", "updated_at",
                ))
                if (
                    contract.allow_financing
                    and contract.financed_amount > 0
                    and contract.payment_frequency != PaymentFrequency.CUSTOM
                ):
                    from installments.services import generate_schedule

                    generate_schedule(contract, request.user)
                record_contract_activity(
                    contract, request.user, ContractActivityAction.CONFIRMED,
                    "Se confirmó la venta y se congeló el snapshot contractual.",
                )
                ContractIdempotencyKey.objects.create(
                    organization=contract.organization, key=key,
                    operation=IdempotencyOperation.CONFIRM, contract=contract,
                )
        except Contract.DoesNotExist as exc:
            raise ValidationError({"detail": "El contrato no está disponible."}) from exc
        except IntegrityError:
            existing = ContractIdempotencyKey.objects.filter(
                organization=visible.organization, key=key, operation=IdempotencyOperation.CONFIRM
            ).first()
            if not existing or existing.contract_id != visible.pk:
                raise
            contract = visible
        return success_response(
            ContractDetailSerializer(contract, context={"request": request}).data,
            "Contrato creado correctamente.",
        )

    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        contract = self.get_object()
        serializer = CancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if contract.status != ContractStatus.ACTIVE:
            raise ConflictError("Solo un contrato activo puede cancelarse.")
        with transaction.atomic():
            contract = scope_contracts(self.get_queryset(), request.user).select_for_update().get(pk=contract.pk)
            if contract.status != ContractStatus.ACTIVE:
                raise ConflictError("El contrato ya no está activo.")
            contract.status = ContractStatus.CANCELLED
            contract.cancelled_at = timezone.now()
            contract.cancelled_by = request.user
            contract.cancellation_reason = serializer.validated_data["reason"]
            contract.save(update_fields=(
                "status", "cancelled_at", "cancelled_by", "cancellation_reason", "updated_at",
            ))
            from installments.services import cancel_contract_schedule

            cancel_contract_schedule(contract, request.user)
            record_contract_activity(
                contract, request.user, ContractActivityAction.CANCELLED,
                "Se canceló el contrato de forma controlada.",
            )
        return success_response(
            ContractDetailSerializer(contract, context={"request": request}).data, "Contrato cancelado."
        )

    @action(detail=True, methods=("get",), url_path="pdf")
    def pdf(self, request, pk=None):
        contract = self.get_object()
        if contract.status == ContractStatus.DRAFT:
            raise ConflictError("Confirma el contrato antes de generar su PDF.")
        content = build_contract_pdf(contract)
        record_contract_activity(
            contract, request.user, ContractActivityAction.PDF_GENERATED,
            "Se generó el PDF histórico del contrato.",
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="Contrato_{contract.contract_number}.pdf"'
        response["Content-Length"] = len(content)
        return response

    @action(detail=False, methods=("get",), url_path="options")
    def module_options(self, request):
        permissions = get_contract_permissions(request.user)
        if permissions.global_access:
            branches = Branch.objects.filter(is_active=True).select_related("organization").order_by("name")
            sellers = CustomUser.objects.filter(
                is_active=True, role__code__in=SELLER_ROLE_CODES
            ).select_related("organization", "role").order_by("first_name", "last_name")
            organizations = Organization.objects.filter(is_active=True).order_by("name")
        else:
            branches = Branch.objects.filter(
                organization_id=request.user.organization_id, is_active=True
            ).order_by("name")
            sellers = CustomUser.objects.filter(
                organization_id=request.user.organization_id, is_active=True,
                role__code__in=SELLER_ROLE_CODES,
            ).select_related("role").order_by("first_name", "last_name")
            organizations = []
        if request.user.role_id and request.user.role.code == "seller":
            branches = branches.filter(pk=request.user.branch_id)
            sellers = sellers.filter(pk=request.user.pk)
        return success_response({
            "statuses": [{"value": value, "label": label} for value, label in ContractStatus.choices],
            "payment_frequencies": [
                {"value": value, "label": label} for value, label in PaymentFrequency.choices
            ],
            "branches": [
                {"id": branch.pk, "name": branch.name, "code": branch.code,
                 "organization_id": branch.organization_id} for branch in branches
            ],
            "sellers": [
                {"id": seller.pk, "name": seller.get_full_name().strip() or seller.username,
                 "role": seller.role.name, "organization_id": seller.organization_id} for seller in sellers
            ],
            "organizations": [{"id": org.pk, "name": org.name} for org in organizations],
            "permissions": permissions.as_dict(),
        }, "Opciones del módulo obtenidas.")
