from datetime import timedelta

from django.db.models import F, Q, Sum
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import CustomUser
from contracts.access import is_branch_restricted, is_global_contract_user, scope_contracts
from contracts.choices import ContractActivityAction, ContractStatus, PaymentFrequency
from contracts.models import Contract
from contracts.services import record_contract_activity
from core.responses import success_response
from organizations.models import Branch
from plans.models import FuneralPlan

from .access import get_installment_permissions, scope_installments, scope_schedules
from .choices import InstallmentStatus, ScheduleStatus
from .models import Installment, InstallmentSchedule
from .pagination import InstallmentPagination
from .pdf import build_payment_plan_pdf
from .permissions import InstallmentPermission
from .serializers import (
    GenerateScheduleSerializer, InstallmentSerializer, ReprogramScheduleSerializer,
    ScheduleConditionsSerializer, ScheduleSummarySerializer, preview_data,
)
from .services import generate_schedule, reprogram_schedule


def installment_queryset():
    return Installment.objects.select_related(
        "organization", "branch", "schedule", "contract__customer", "contract__seller", "contract__plan"
    )


def schedule_queryset():
    return InstallmentSchedule.objects.select_related(
        "organization", "branch", "contract__customer", "contract__seller", "contract__plan",
        "generated_by", "reprogrammed_by", "previous_schedule",
    )


def scoped_contract_or_404(user, contract_id):
    queryset = Contract.objects.select_related(
        "organization", "branch", "customer", "seller", "plan"
    )
    return get_object_or_404(scope_contracts(queryset, user), pk=contract_id)


def require_permission(user, field, message):
    if not getattr(get_installment_permissions(user), field):
        raise PermissionDenied(message)


def schedule_payload(schedule, request, include_history=True):
    items = schedule.installments.select_related(
        "organization", "branch", "schedule", "contract__customer", "contract__seller", "contract__plan"
    ).order_by("installment_number")
    paginator = InstallmentPagination()
    page = paginator.paginate_queryset(items, request)
    installment_data = InstallmentSerializer(page, many=True, context={"request": request}).data
    paginated = {
        "count": paginator.page.paginator.count,
        "page": paginator.page.number,
        "page_size": paginator.get_page_size(request),
        "total_pages": paginator.page.paginator.num_pages,
        "next": paginator.get_next_link(),
        "previous": paginator.get_previous_link(),
        "results": installment_data,
    }
    result = {
        "schedule": ScheduleSummarySerializer(schedule, context={"request": request}).data,
        "installments": paginated,
    }
    if include_history:
        history = schedule.contract.installment_schedules.select_related(
            "generated_by", "reprogrammed_by", "previous_schedule"
        ).order_by("-version")
        result["history"] = ScheduleSummarySerializer(history, many=True, context={"request": request}).data
    return result


class InstallmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = (InstallmentPermission,)
    serializer_class = InstallmentSerializer
    pagination_class = InstallmentPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        "contract__contract_number", "contract__customer_name_snapshot",
        "contract__customer_identity_snapshot", "contract__customer__customer_code",
        "contract__customer__first_name", "contract__customer__last_name",
    )
    http_method_names = ("get", "head", "options")

    def get_queryset(self):
        queryset = scope_installments(installment_queryset(), self.request.user)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        effective_status = params.get("status")
        today = timezone.localdate()
        if effective_status == InstallmentStatus.OVERDUE:
            queryset = queryset.filter(
                due_date__lt=today, current_amount__gt=F("paid_amount")
            ).exclude(status__in=(InstallmentStatus.CANCELLED, InstallmentStatus.PAID))
        elif effective_status == InstallmentStatus.PENDING:
            queryset = queryset.filter(
                due_date__gte=today, paid_amount=0, status=InstallmentStatus.PENDING
            )
        elif effective_status in InstallmentStatus.values:
            queryset = queryset.filter(status=effective_status)
        if effective_status != InstallmentStatus.CANCELLED and params.get("include_history") != "true":
            queryset = queryset.filter(schedule__status=ScheduleStatus.ACTIVE)
        for parameter, lookup in (
            ("branch", "branch_id"), ("seller", "contract__seller_id"),
            ("plan", "contract__plan_id"), ("contract", "contract_id"),
        ):
            if params.get(parameter):
                queryset = queryset.filter(**{lookup: params[parameter]})
        date_from = parse_date(params.get("date_from", ""))
        date_to = parse_date(params.get("date_to", ""))
        preset = params.get("preset")
        if preset == "today":
            date_from = date_to = today
        elif preset == "week":
            date_from, date_to = today, today + timedelta(days=6)
        elif preset == "month":
            date_from = today.replace(day=1)
            next_month = (date_from.replace(day=28) + timedelta(days=4)).replace(day=1)
            date_to = next_month - timedelta(days=1)
        elif preset == "overdue":
            queryset = queryset.filter(
                due_date__lt=today, current_amount__gt=F("paid_amount")
            ).exclude(status__in=(InstallmentStatus.CANCELLED, InstallmentStatus.PAID))
        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)
        ordering = {
            "due_date": ("due_date", "contract_id", "installment_number"),
            "-due_date": ("-due_date", "contract_id", "installment_number"),
            "amount": ("current_amount",), "-amount": ("-current_amount",),
            "contract": ("contract__contract_number", "installment_number"),
        }.get(params.get("ordering"), ("due_date", "contract_id", "installment_number"))
        return queryset.order_by(*ordering)


class ContractScheduleView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, contract_id):
        require_permission(request.user, "view_installments", "No tienes permiso para ver cuotas.")
        contract = scoped_contract_or_404(request.user, contract_id)
        schedule = scope_schedules(schedule_queryset(), request.user).filter(contract=contract).first()
        if not schedule:
            return success_response({
                "schedule": None, "installments": None, "history": [],
                "reason": "cash" if not contract.allow_financing or contract.financed_amount <= 0 else "not_generated",
            }, "Este contrato no posee un calendario de cuotas.")
        return success_response(schedule_payload(schedule, request), "Calendario obtenido correctamente.")


class GenerateScheduleView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, contract_id):
        require_permission(request.user, "generate_schedule", "No tienes permiso para generar calendarios.")
        contract = scoped_contract_or_404(request.user, contract_id)
        serializer = GenerateScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule, created = generate_schedule(
            contract, request.user, manual_installments=serializer.validated_data.get("manual_installments"),
        )
        return success_response(
            schedule_payload(schedule, request),
            "Calendario generado correctamente." if created else "El contrato ya posee un calendario activo.",
            status=201 if created else 200,
        )


class PreviewScheduleView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, contract_id):
        permissions = get_installment_permissions(request.user)
        if not (permissions.generate_schedule or permissions.reprogram_schedule):
            raise PermissionDenied("No tienes permiso para calcular calendarios.")
        contract = scoped_contract_or_404(request.user, contract_id)
        if contract.status != ContractStatus.ACTIVE:
            raise ValidationError({"contract": "Solo contratos activos pueden programar cuotas."})
        serializer = ScheduleConditionsSerializer(
            data=request.data, context={"request": request, "contract": contract}
        )
        serializer.is_valid(raise_exception=True)
        return success_response(preview_data(serializer.validated_data["preview"]), "Vista previa calculada.")


class ReprogramScheduleView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, contract_id):
        require_permission(request.user, "reprogram_schedule", "No tienes permiso para reprogramar este contrato.")
        contract = scoped_contract_or_404(request.user, contract_id)
        serializer = ReprogramScheduleSerializer(
            data=request.data, context={"request": request, "contract": contract}
        )
        serializer.is_valid(raise_exception=True)
        schedule = reprogram_schedule(
            contract, request.user, frequency=serializer.validated_data["frequency"],
            installment_amount=serializer.validated_data.get("installment_amount"),
            first_due_date=serializer.validated_data.get("first_due_date"),
            manual_installments=serializer.validated_data.get("manual_installments"),
            reason=serializer.validated_data["reason"],
        )
        return success_response(schedule_payload(schedule, request), "Calendario reprogramado correctamente.")


class PaymentPlanPDFView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, contract_id):
        require_permission(request.user, "view_installments", "No tienes permiso para descargar este calendario.")
        contract = scoped_contract_or_404(request.user, contract_id)
        schedule = scope_schedules(schedule_queryset(), request.user).filter(
            contract=contract
        ).order_by("-version").first()
        if not schedule:
            raise Http404
        content = build_payment_plan_pdf(schedule)
        record_contract_activity(
            contract, request.user, ContractActivityAction.SCHEDULE_PDF_GENERATED,
            f"Se generó el plan de pagos del calendario v{schedule.version}.",
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="Plan_Pagos_{contract.contract_number}.pdf"'
        response["Content-Length"] = len(content)
        return response


class InstallmentOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permissions = get_installment_permissions(request.user)
        if not permissions.view_installments:
            raise PermissionDenied("No tienes permiso para ver cuotas.")
        branches = Branch.objects.filter(is_active=True)
        sellers = CustomUser.objects.filter(is_active=True, role__code__in=("admin", "manager", "seller"))
        plans = FuneralPlan.objects.filter(is_active=True)
        if not permissions.global_access:
            branches = branches.filter(organization_id=request.user.organization_id)
            sellers = sellers.filter(organization_id=request.user.organization_id)
            plans = plans.filter(organization_id=request.user.organization_id)
        if is_branch_restricted(request.user):
            branches = branches.filter(pk=request.user.branch_id)
            sellers = sellers.filter(branch_id=request.user.branch_id)
        return success_response({
            "statuses": [{"value": value, "label": label} for value, label in InstallmentStatus.choices],
            "schedule_statuses": [{"value": value, "label": label} for value, label in ScheduleStatus.choices],
            "frequencies": [{"value": value, "label": label} for value, label in PaymentFrequency.choices],
            "branches": [
                {"id": item.pk, "name": item.name, "code": item.code, "organization_id": item.organization_id}
                for item in branches.order_by("name")
            ],
            "sellers": [
                {"id": item.pk, "name": item.get_full_name().strip() or item.username}
                for item in sellers.select_related("role").order_by("first_name", "last_name")
            ],
            "plans": [
                {"id": item.pk, "name": item.name, "code": item.code}
                for item in plans.order_by("name")
            ],
            "permissions": permissions.as_dict(),
        }, "Opciones de cuotas obtenidas.")


class InstallmentSummaryView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require_permission(request.user, "view_installments", "No tienes permiso para ver cuotas.")
        today = timezone.localdate()
        base = scope_installments(installment_queryset(), request.user).filter(
            schedule__status=ScheduleStatus.ACTIVE
        )
        overdue = base.filter(
            due_date__lt=today, current_amount__gt=F("paid_amount")
        ).exclude(status__in=(InstallmentStatus.CANCELLED, InstallmentStatus.PAID))
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month = base.filter(due_date__gte=month_start, due_date__lt=next_month).exclude(
            status=InstallmentStatus.CANCELLED
        )
        return success_response({
            "due_today": base.filter(due_date=today).exclude(status=InstallmentStatus.CANCELLED).count(),
            "overdue": overdue.count(),
            "scheduled_this_month": str(month.aggregate(value=Sum("current_amount"))["value"] or "0.00"),
        }, "Resumen de obligaciones obtenido.")
