from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import CustomUser, RoleCode
from contracts.access import scope_contracts
from contracts.exceptions import ConflictError
from contracts.models import Contract
from core.responses import success_response
from organizations.models import Branch

from .access import get_payment_permissions, scope_payments, scope_receipts
from .choices import PaymentMethod, PaymentStatus, PaymentType
from .models import Payment, Receipt
from .pagination import PaymentPagination
from .pdf import build_receipt_pdf
from .permissions import PaymentPermission
from .serializers import (
    PaymentInputSerializer, PaymentPreviewSerializer, PaymentSerializer, ReceiptSerializer,
    SettlementSerializer, VoidPaymentSerializer,
)
from .services import (
    financial_summary, preview_allocation, preview_data, register_payment, void_payment,
)


def payment_queryset():
    return Payment.objects.select_related(
        "organization", "branch", "contract", "customer", "received_by", "created_by", "voided_by",
        "receipt",
        "collector_session",
    ).prefetch_related("applications__installment__schedule")


def scoped_contract(user, contract_id):
    queryset = Contract.objects.select_related("organization", "branch", "customer")
    if getattr(getattr(user, "role", None), "code", None) == RoleCode.COLLECTOR:
        queryset = queryset.filter(
            collection_assignments__collector=user, collection_assignments__status="active",
        )
    return get_object_or_404(scope_contracts(queryset, user), pk=contract_id)


def idempotency_key(request):
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise ValidationError({"idempotency_key": "Envía una clave de idempotencia para registrar el pago."})
    if len(key) < 8 or len(key) > 128:
        raise ValidationError({"idempotency_key": "La clave de idempotencia no es válida."})
    return key


def require(user, permission, message):
    if not getattr(get_payment_permissions(user), permission):
        raise PermissionDenied(message)


class PaymentViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (PaymentPermission,)
    serializer_class = PaymentSerializer
    pagination_class = PaymentPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        "payment_number", "receipt__receipt_number", "contract__contract_number",
        "contract__customer_name_snapshot", "contract__customer_identity_snapshot",
        "customer__first_name", "customer__last_name", "customer__identity_number", "reference",
    )
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = scope_payments(payment_queryset(), self.request.user)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("status") in PaymentStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("payment_method") in PaymentMethod.values:
            queryset = queryset.filter(payment_method=params["payment_method"])
        if params.get("payment_type") in PaymentType.values:
            queryset = queryset.filter(payment_type=params["payment_type"])
        for parameter, lookup in (
            ("branch", "branch_id"), ("received_by", "received_by_id"),
            ("contract", "contract_id"), ("customer", "customer_id"),
        ):
            if params.get(parameter):
                queryset = queryset.filter(**{lookup: params[parameter]})
        date_from = parse_date(params.get("date_from", ""))
        date_to = parse_date(params.get("date_to", ""))
        today = timezone.localdate()
        preset = params.get("preset")
        if preset == "today":
            date_from = date_to = today
        elif preset == "week":
            date_from, date_to = today - timedelta(days=today.weekday()), today
        elif preset == "month":
            date_from, date_to = today.replace(day=1), today
        if date_from:
            queryset = queryset.filter(payment_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__date__lte=date_to)
        ordering = {
            "payment_date": ("payment_date", "id"), "-payment_date": ("-payment_date", "-id"),
            "amount": ("amount",), "-amount": ("-amount",),
            "payment_number": ("payment_number",),
        }.get(params.get("ordering"), ("-payment_date", "-id"))
        return queryset.order_by(*ordering)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        total = queryset.filter(status=PaymentStatus.CONFIRMED).aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request, "include_financial_summary": False})
        payload = self.paginator.payload(serializer.data)
        payload["total_confirmed"] = str(total)
        return success_response(payload, "Pagos obtenidos correctamente.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(self.get_serializer(self.get_object()).data, "Pago obtenido correctamente.")

    def create(self, request, *args, **kwargs):
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = serializer.validated_data.get("contract")
        if not submitted:
            raise ValidationError({"contract": "Selecciona el contrato que recibirá el pago."})
        permissions = get_payment_permissions(request.user)
        payment_type = serializer.validated_data["payment_type"]
        if payment_type == PaymentType.INITIAL_PAYMENT and not permissions.register_initial_payment:
            raise PermissionDenied("No tienes permiso para registrar pagos de prima.")
        if payment_type == PaymentType.SETTLEMENT and not permissions.settle_contract:
            raise PermissionDenied("No tienes permiso para liquidar contratos.")
        requested_date = serializer.validated_data.get("payment_date")
        if requested_date and timezone.localtime(requested_date).date() < timezone.localdate() and not permissions.backdate_payment:
            raise ValidationError({"payment_date": "No tienes permiso para registrar pagos retroactivos."})
        contract = scoped_contract(request.user, submitted.pk)
        payload = dict(serializer.validated_data)
        payload.pop("contract", None)
        payment, created = register_payment(
            contract, request.user, payload, idempotency_key(request),
            can_backdate=permissions.backdate_payment,
        )
        payment = payment_queryset().get(pk=payment.pk)
        return success_response(
            PaymentSerializer(payment, context={"request": request}).data,
            "Pago registrado correctamente." if created else "Este pago ya fue procesado.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=("post",), url_path="void")
    def void(self, request, pk=None):
        payment = self.get_object()
        serializer = VoidPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = void_payment(payment, request.user, serializer.validated_data["reason"])
        payment = payment_queryset().get(pk=payment.pk)
        return success_response(self.get_serializer(payment).data, "Pago anulado y obligaciones reconstruidas.")

    @action(detail=True, methods=("get",), url_path="receipt")
    def receipt(self, request, pk=None):
        payment = self.get_object()
        receipt = get_object_or_404(scope_receipts(Receipt.objects.all(), request.user), payment=payment)
        return success_response(ReceiptSerializer(receipt).data, "Recibo obtenido correctamente.")

    @action(detail=True, methods=("get",), url_path="receipt/pdf")
    def receipt_pdf(self, request, pk=None):
        payment = self.get_object()
        receipt = get_object_or_404(
            scope_receipts(Receipt.objects.select_related("payment", "organization"), request.user), payment=payment
        )
        content = build_receipt_pdf(receipt)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="Recibo_{receipt.receipt_number}.pdf"'
        response["Content-Length"] = len(content)
        return response


class ContractPaymentPreviewView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, contract_id):
        require(request.user, "create_payment", "No tienes permiso para registrar pagos.")
        contract = scoped_contract(request.user, contract_id)
        serializer = PaymentPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_type = serializer.validated_data["payment_type"]
        permissions = get_payment_permissions(request.user)
        if payment_type == PaymentType.INITIAL_PAYMENT and not permissions.register_initial_payment:
            raise PermissionDenied("No tienes permiso para registrar pagos de prima.")
        if payment_type == PaymentType.SETTLEMENT and not permissions.settle_contract:
            raise PermissionDenied("No tienes permiso para liquidar contratos.")
        preview = preview_allocation(contract, serializer.validated_data["amount"], payment_type)
        result = preview_data(preview)
        result["financial_summary"] = financial_summary(contract)
        return success_response(result, "Vista previa calculada sin guardar cambios.")


class ContractPaymentsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, contract_id):
        require(request.user, "view_payment", "No tienes permiso para ver pagos.")
        contract = scoped_contract(request.user, contract_id)
        queryset = scope_payments(payment_queryset(), request.user).filter(contract=contract)
        paginator = PaymentPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = PaymentSerializer(page, many=True, context={"request": request, "include_financial_summary": False}).data
        return success_response({
            "financial_summary": financial_summary(contract), "payments": paginator.payload(data),
        }, "Historial de pagos obtenido.")


class ContractSettlementView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, contract_id):
        require(request.user, "settle_contract", "No tienes permiso para liquidar contratos.")
        contract = scoped_contract(request.user, contract_id)
        serializer = SettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        current = financial_summary(contract)["contract_balance"]
        if serializer.validated_data["expected_balance"] != current:
            raise ConflictError("El saldo cambió. Actualiza la información antes de continuar.")
        payload = dict(serializer.validated_data)
        payload.pop("expected_balance")
        payload.update({"amount": current, "payment_type": PaymentType.SETTLEMENT})
        payment, created = register_payment(
            contract, request.user, payload, idempotency_key(request),
            can_backdate=get_payment_permissions(request.user).backdate_payment,
        )
        payment = payment_queryset().get(pk=payment.pk)
        return success_response(
            PaymentSerializer(payment, context={"request": request}).data,
            "Contrato liquidado correctamente." if created else "Esta liquidación ya fue procesada.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PaymentOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permissions = get_payment_permissions(request.user)
        if not permissions.view_payment:
            raise PermissionDenied("No tienes permiso para ver pagos.")
        branches = Branch.objects.filter(is_active=True)
        receivers = CustomUser.objects.filter(is_active=True)
        if not permissions.global_access:
            branches = branches.filter(organization_id=request.user.organization_id)
            receivers = receivers.filter(organization_id=request.user.organization_id)
        return success_response({
            "payment_types": [{"value": value, "label": label} for value, label in PaymentType.choices],
            "payment_methods": [{"value": value, "label": label} for value, label in PaymentMethod.choices],
            "statuses": [{"value": value, "label": label} for value, label in PaymentStatus.choices],
            "branches": [{"id": item.pk, "name": item.name, "code": item.code} for item in branches.order_by("name")],
            "receivers": [{"id": item.pk, "name": item.get_full_name().strip() or item.username} for item in receivers.order_by("first_name", "last_name")],
            "permissions": permissions.as_dict(),
        }, "Opciones de pagos obtenidas.")
