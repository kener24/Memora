from datetime import timedelta
from urllib.parse import urlencode

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import CustomUser
from contracts.access import scope_contracts
from contracts.models import Contract
from core.responses import success_response
from organizations.models import Branch
from payments.access import scope_payments
from payments.models import Payment
from plans.models import FuneralPlan

from .access import get_collection_permissions
from .choices import (
    AGING_BUCKETS, CollectionActionStatus, CollectionActionType, CollectionOutcome,
    CollectionPriority, CollectionStatus, PromiseStatus,
)
from .excel import build_portfolio_excel
from .models import CollectionAction, PaymentPromise
from .pagination import PortfolioPagination
from .pdf import build_portfolio_pdf
from .serializers import (
    CollectionActionInputSerializer, CollectionActionSerializer, FulfillPromiseSerializer,
    PaymentPromiseInputSerializer, PaymentPromiseSerializer, VoidSerializer,
)
from .services import (
    acknowledge_broken_promise, actions_queryset, aging_summary, apply_portfolio_filters, cancel_promise,
    create_collection_action, create_payment_promise, filtered_totals, fulfill_promise,
    portfolio_queryset, portfolio_row, portfolio_summary, promises_queryset, void_collection_action,
)


def require(user, permission, message):
    if not getattr(get_collection_permissions(user), permission):
        raise PermissionDenied(message)


def scoped_contract(user, pk):
    return get_object_or_404(
        scope_contracts(Contract.objects.select_related("organization", "branch", "customer"), user), pk=pk,
    )


def filtered_portfolio(request, *, include_paid=False):
    queryset = portfolio_queryset(request.user, include_paid=include_paid)
    return apply_portfolio_filters(queryset, request.query_params)


def filter_description(params):
    ignored = {"page", "page_size"}
    return ", ".join(f"{key}={value}" for key, value in params.items() if key not in ignored and value)[:500]


class PortfolioListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_portfolio", "No tienes permiso para ver cartera.")
        include_paid = request.query_params.get("status") == CollectionStatus.PAID
        queryset = filtered_portfolio(request, include_paid=include_paid)
        totals = filtered_totals(queryset)
        paginator = PortfolioPagination()
        page = paginator.paginate_queryset(queryset, request)
        return success_response(paginator.payload([portfolio_row(item) for item in page], totals), "Cartera obtenida correctamente.")


class PortfolioSummaryView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_portfolio", "No tienes permiso para ver cartera.")
        return success_response(portfolio_summary(request.user, request.query_params), "Resumen de cartera obtenido.")


class AgingSummaryView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_overdue", "No tienes permiso para ver morosidad.")
        return success_response(aging_summary(request.user, request.query_params), "Antigüedad de saldos obtenida.")


class ContractCollectionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, contract_id):
        require(request.user, "view_portfolio", "No tienes permiso para ver cartera.")
        scoped_contract(request.user, contract_id)
        contract = get_object_or_404(portfolio_queryset(request.user, include_paid=True), pk=contract_id)
        actions = actions_queryset(request.user).filter(contract_id=contract_id)[:100]
        promises = promises_queryset(request.user).filter(contract_id=contract_id)[:100]
        return success_response({
            "portfolio": portfolio_row(contract),
            "actions": CollectionActionSerializer(actions, many=True).data,
            "promises": PaymentPromiseSerializer(promises, many=True).data,
        }, "Detalle de cobranza obtenido.")


class CustomerCollectionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, customer_id):
        require(request.user, "view_portfolio", "No tienes permiso para ver cartera.")
        contracts = portfolio_queryset(request.user, include_paid=True).filter(customer_id=customer_id)
        if not contracts.exists():
            if not scope_contracts(Contract.objects.all(), request.user).filter(customer_id=customer_id).exists():
                raise Http404
        return success_response({
            "contracts": [portfolio_row(item) for item in contracts],
            "actions": CollectionActionSerializer(actions_queryset(request.user).filter(customer_id=customer_id)[:100], many=True).data,
            "promises": PaymentPromiseSerializer(promises_queryset(request.user).filter(customer_id=customer_id)[:100], many=True).data,
        }, "Cartera del cliente obtenida.")


class CollectionActionViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = CollectionActionSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = actions_queryset(self.request.user).prefetch_related("audits__actor", "payment_promise__audits__actor")
        params = self.request.query_params
        for key in ("contract", "customer"):
            if params.get(key):
                queryset = queryset.filter(**{f"{key}_id": params[key]})
        if params.get("status") in CollectionActionStatus.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def list(self, request, *args, **kwargs):
        require(request.user, "view_action", "No tienes permiso para ver gestiones.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Gestiones obtenidas.")

    def retrieve(self, request, *args, **kwargs):
        require(request.user, "view_action", "No tienes permiso para ver gestiones.")
        return success_response(self.get_serializer(self.get_object()).data, "Gestión obtenida.")

    def create(self, request, *args, **kwargs):
        require(request.user, "create_action", "No tienes permiso para registrar gestiones.")
        serializer = CollectionActionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = scoped_contract(request.user, serializer.validated_data["contract"])
        action_item = create_collection_action(contract, contract.customer, request.user, serializer.validated_data)
        action_item = self.get_queryset().get(pk=action_item.pk)
        return success_response(self.get_serializer(action_item).data, "Gestión registrada.", status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="void")
    def void(self, request, pk=None):
        require(request.user, "void_action", "No tienes permiso para anular gestiones.")
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = void_collection_action(self.get_object(), request.user, serializer.validated_data["reason"])
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Gestión anulada.")


class PaymentPromiseViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentPromiseSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = promises_queryset(self.request.user).prefetch_related("audits__actor")
        params = self.request.query_params
        for key in ("contract", "customer"):
            if params.get(key):
                queryset = queryset.filter(**{f"{key}_id": params[key]})
        promise_status = params.get("status")
        if promise_status == PromiseStatus.BROKEN:
            queryset = queryset.filter(status=PromiseStatus.PENDING, promised_date__lt=timezone.localdate())
        elif promise_status == PromiseStatus.PENDING:
            queryset = queryset.filter(status=PromiseStatus.PENDING, promised_date__gte=timezone.localdate())
        elif promise_status in PromiseStatus.values:
            queryset = queryset.filter(status=promise_status)
        return queryset

    def list(self, request, *args, **kwargs):
        require(request.user, "view_promise", "No tienes permiso para ver promesas.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Promesas obtenidas.")

    def retrieve(self, request, *args, **kwargs):
        require(request.user, "view_promise", "No tienes permiso para ver promesas.")
        return success_response(self.get_serializer(self.get_object()).data, "Promesa obtenida.")

    def create(self, request, *args, **kwargs):
        require(request.user, "create_promise", "No tienes permiso para registrar promesas.")
        serializer = PaymentPromiseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = scoped_contract(request.user, serializer.validated_data["contract"])
        promise = create_payment_promise(contract, contract.customer, request.user, serializer.validated_data)
        return success_response(self.get_serializer(self.get_queryset().get(pk=promise.pk)).data, "Promesa registrada.", status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="cancel")
    def cancel(self, request, pk=None):
        require(request.user, "resolve_promise", "No tienes permiso para resolver promesas.")
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        promise = cancel_promise(self.get_object(), request.user, serializer.validated_data["reason"])
        return success_response(self.get_serializer(self.get_queryset().get(pk=promise.pk)).data, "Promesa cancelada.")

    @action(detail=True, methods=("post",), url_path="fulfill")
    def fulfill(self, request, pk=None):
        require(request.user, "resolve_promise", "No tienes permiso para resolver promesas.")
        serializer = FulfillPromiseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_object_or_404(scope_payments(Payment.objects.all(), request.user), pk=serializer.validated_data["payment"].pk)
        promise = fulfill_promise(self.get_object(), payment, request.user)
        return success_response(self.get_serializer(self.get_queryset().get(pk=promise.pk)).data, "Promesa marcada como cumplida.")

    @action(detail=True, methods=("post",), url_path="break")
    def break_promise(self, request, pk=None):
        require(request.user, "resolve_promise", "No tienes permiso para resolver promesas.")
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        promise = acknowledge_broken_promise(self.get_object(), request.user, serializer.validated_data["reason"])
        return success_response(self.get_serializer(self.get_queryset().get(pk=promise.pk)).data, "Promesa marcada como incumplida.")


class FollowUpAgendaView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_action", "No tienes permiso para ver la agenda.")
        today = timezone.localdate()
        queryset = actions_queryset(request.user).filter(
            status=CollectionActionStatus.ACTIVE, next_follow_up_date__isnull=False,
        ).prefetch_related("audits__actor", "payment_promise__audits__actor")
        groups = {
            "overdue": queryset.filter(next_follow_up_date__lt=today),
            "today": queryset.filter(next_follow_up_date=today),
            "upcoming": queryset.filter(next_follow_up_date__gt=today, next_follow_up_date__lte=today + timedelta(days=7)),
        }
        return success_response({key: CollectionActionSerializer(value[:100], many=True).data for key, value in groups.items()}, "Agenda de seguimiento obtenida.")


class CollectionOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permissions = get_collection_permissions(request.user)
        if not permissions.view_portfolio:
            raise PermissionDenied("No tienes permiso para ver cartera.")
        branches = Branch.objects.filter(is_active=True)
        plans = FuneralPlan.objects.filter(is_active=True)
        sellers = CustomUser.objects.filter(is_active=True)
        if not permissions.global_access:
            branches = branches.filter(organization_id=request.user.organization_id)
            plans = plans.filter(organization_id=request.user.organization_id)
            sellers = sellers.filter(organization_id=request.user.organization_id)
        return success_response({
            "statuses": [{"value": value, "label": label} for value, label in CollectionStatus.choices],
            "priorities": [{"value": value, "label": label} for value, label in CollectionPriority.choices],
            "action_types": [{"value": value, "label": label} for value, label in CollectionActionType.choices],
            "outcomes": [{"value": value, "label": label} for value, label in CollectionOutcome.choices],
            "aging_buckets": [{"value": value, "label": label} for value, label, _, _ in AGING_BUCKETS],
            "branches": [{"id": item.pk, "name": item.name} for item in branches.order_by("name")],
            "plans": [{"id": item.pk, "name": item.name} for item in plans.order_by("name")],
            "sellers": [{"id": item.pk, "name": item.get_full_name().strip() or item.username} for item in sellers.order_by("first_name", "last_name")],
            "permissions": permissions.as_dict(),
        }, "Opciones de cobranza obtenidas.")


class PortfolioExportView(APIView):
    permission_classes = (IsAuthenticated,)
    format_name = None
    maximum_rows = 10000

    def get(self, request):
        require(request.user, "export_portfolio", "No tienes permiso para exportar cartera.")
        queryset = filtered_portfolio(request, include_paid=request.query_params.get("status") == CollectionStatus.PAID)
        totals = filtered_totals(queryset)
        rows = [portfolio_row(item) for item in queryset[:self.maximum_rows]]
        generated_at = timezone.localtime()
        description = filter_description(request.query_params)
        if self.format_name == "xlsx":
            content = build_portfolio_excel(rows, totals, description, generated_at)
            content_type, extension = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
        else:
            rows = rows[:500]
            content = build_portfolio_pdf(rows, totals, description, generated_at)
            content_type, extension = "application/pdf", "pdf"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="Cartera_Memora_{timezone.localdate():%Y%m%d}.{extension}"'
        response["Content-Length"] = len(content)
        return response


class PortfolioExcelView(PortfolioExportView):
    format_name = "xlsx"


class PortfolioPDFView(PortfolioExportView):
    format_name = "pdf"
