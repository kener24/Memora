from decimal import Decimal

from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import RoleCode
from contracts.access import is_branch_restricted
from core.responses import success_response
from organizations.models import Branch

from .access import get_cash_permissions, role_code, scope_cash
from .choices import CashMovementDirection, CashSessionStatus
from .excel import build_cash_movements_excel
from .filters import filter_movements, filter_sessions
from .models import (
    CashCount, CashMovement, CashRegister, CashSession, CollectorSettlementReception,
)
from .pagination import CashPagination
from .pdf import build_cash_closing_pdf
from .permissions import CashPermission
from .serializers import (
    CashCountInputSerializer, CashCountSerializer, CashMovementInputSerializer,
    CashMovementSerializer, CashRegisterInputSerializer, CashRegisterSerializer,
    CashRegisterUpdateSerializer, CashSessionCloseSerializer, CashSessionOpenSerializer,
    CashSessionSerializer, PendingSettlementSerializer, SettlementReceptionInputSerializer,
    SettlementReceptionSerializer, VoidMovementSerializer, cash_options_payload,
)
from .services import (
    cash_dashboard, cash_settlements_for_user, close_cash_session, create_cash_register, create_manual_movement,
    current_cash_session, movement_totals, open_cash_session, pending_settlements_for_user,
    perform_cash_count, receive_collector_settlement, update_cash_register,
    void_manual_movement,
)


def require(user, permission, message):
    if not getattr(get_cash_permissions(user), permission):
        raise PermissionDenied(message)


def idempotency_key(request):
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise ValidationError({"idempotency_key": "Envía una clave de idempotencia."})
    if len(key) < 8 or len(key) > 128:
        raise ValidationError({"idempotency_key": "La clave de idempotencia no es válida."})
    return key


def scoped_branches(user):
    queryset = Branch.objects.filter(is_active=True).select_related("organization")
    permissions = get_cash_permissions(user)
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        queryset = queryset.filter(pk=user.branch_id) if user.branch_id else queryset.none()
    return queryset


def cash_register_queryset():
    return CashRegister.objects.select_related("organization", "branch", "created_by").prefetch_related(
        Prefetch(
            "sessions",
            queryset=CashSession.objects.filter(status=CashSessionStatus.OPEN).select_related("cashier"),
        )
    )


def cash_session_queryset():
    return CashSession.objects.select_related(
        "organization", "branch", "cash_register", "cashier", "opened_by", "closed_by"
    ).prefetch_related(
        Prefetch(
            "cash_counts",
            queryset=CashCount.objects.select_related("counted_by").prefetch_related("denominations"),
        )
    )


def cash_movement_queryset():
    return CashMovement.objects.select_related(
        "organization", "branch", "cash_session__cash_register", "created_by", "voided_by",
        "payment", "settlement_reception",
    )


def reception_queryset():
    return CollectorSettlementReception.objects.select_related(
        "organization", "branch", "cash_session", "cash_session__cash_register",
        "collector_settlement__collector", "collector_settlement__work_session", "received_by",
    ).prefetch_related("cash_movement")


class CashRegisterViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = CashRegisterSerializer
    pagination_class = CashPagination
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        queryset = scope_cash(
            cash_register_queryset(), self.request.user, "view_cash_register"
        )
        if self.request.query_params.get("is_active") in {"true", "false"}:
            queryset = queryset.filter(is_active=self.request.query_params["is_active"] == "true")
        if self.request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=self.request.query_params["branch"])
        return queryset

    def list(self, request):
        require(request.user, "view_cash_register", "No tienes permiso para ver cajas.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(
            self.paginator.payload(self.get_serializer(page, many=True).data), "Cajas obtenidas."
        )

    def retrieve(self, request, pk=None):
        require(request.user, "view_cash_register", "No tienes permiso para ver cajas.")
        return success_response(self.get_serializer(self.get_object()).data, "Caja obtenida.")

    def create(self, request):
        require(request.user, "manage_cash_register", "No tienes permiso para crear cajas.")
        payload = CashRegisterInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        branch = get_object_or_404(scoped_branches(request.user), pk=payload.validated_data["branch"].pk)
        item = create_cash_register(
            branch.organization, branch, request.user, payload.validated_data["name"],
            payload.validated_data.get("description", ""),
        )
        return success_response(
            self.get_serializer(self.get_queryset().get(pk=item.pk)).data,
            "Caja creada correctamente.", status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        require(request.user, "manage_cash_register", "No tienes permiso para modificar cajas.")
        payload = CashRegisterUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = update_cash_register(self.get_object(), request.user, **payload.validated_data)
        return success_response(
            self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Caja actualizada."
        )


class CashSessionViewSet(viewsets.GenericViewSet):
    permission_classes = (CashPermission,)
    serializer_class = CashSessionSerializer
    pagination_class = CashPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        return filter_sessions(
            scope_cash(cash_session_queryset(), self.request.user, "view_session"),
            self.request.query_params,
        )

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return success_response(
            self.paginator.payload(self.get_serializer(
                page, many=True, context={"request": request, "include_live_summary": False}
            ).data), "Sesiones obtenidas."
        )

    def retrieve(self, request, pk=None):
        return success_response(self.get_serializer(self.get_object()).data, "Sesión obtenida.")

    @action(detail=False, methods=("get",), url_path="current")
    def current(self, request):
        require(request.user, "view_session", "No tienes permiso para ver sesiones.")
        item = current_cash_session(request.user)
        return success_response(
            self.get_serializer(item).data if item else None,
            "Sesión actual obtenida." if item else "No hay una caja abierta.",
        )

    @action(detail=False, methods=("post",), url_path="open")
    def open(self, request):
        require(request.user, "open_session", "No tienes permiso para abrir cajas.")
        payload = CashSessionOpenSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        register = get_object_or_404(
            scope_cash(cash_register_queryset(), request.user, "view_cash_register"),
            pk=payload.validated_data["cash_register"].pk,
        )
        item, created = open_cash_session(
            register, request.user, payload.validated_data["opening_cash"],
            payload.validated_data.get("notes", ""), idempotency_key(request),
        )
        item = cash_session_queryset().get(pk=item.pk)
        return success_response(
            self.get_serializer(item).data,
            "Caja abierta correctamente." if created else "Esta apertura ya fue procesada.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=("post",), url_path="count")
    def count(self, request, pk=None):
        require(request.user, "perform_cash_count", "No tienes permiso para realizar arqueos.")
        payload = CashCountInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item, created = perform_cash_count(
            self.get_object(), request.user,
            denominations=payload.validated_data.get("denominations", []),
            counted_cash=payload.validated_data.get("counted_cash"),
            difference_reason=payload.validated_data.get("difference_reason", ""),
            idempotency_key=idempotency_key(request),
        )
        item = CashCount.objects.select_related("counted_by").prefetch_related("denominations").get(pk=item.pk)
        return success_response(
            CashCountSerializer(item).data,
            "Arqueo registrado." if created else "Este arqueo ya fue procesado.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=("post",), url_path="close")
    def close(self, request, pk=None):
        require(request.user, "close_session", "No tienes permiso para cerrar cajas.")
        payload = CashSessionCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item, created = close_cash_session(
            self.get_object(), request.user, payload.validated_data["cash_count"],
            payload.validated_data.get("notes", ""), idempotency_key(request),
        )
        item = cash_session_queryset().get(pk=item.pk)
        return success_response(
            self.get_serializer(item).data,
            "Caja cerrada correctamente." if created else "Este cierre ya fue procesado.",
        )

    @action(detail=True, methods=("get",), url_path="closing-pdf")
    def closing_pdf(self, request, pk=None):
        require(request.user, "view_cash_history", "No tienes permiso para descargar cierres.")
        item = self.get_object()
        if item.status != CashSessionStatus.CLOSED:
            raise ValidationError({"cash_session": "Cierra la caja antes de generar el reporte final."})
        content = build_cash_closing_pdf(item)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="Cierre_Caja_{item.session_number}.pdf"'
        response["Content-Length"] = len(content)
        return response


class CashMovementViewSet(viewsets.GenericViewSet):
    permission_classes = (CashPermission,)
    serializer_class = CashMovementSerializer
    pagination_class = CashPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        "movement_number", "description", "reference", "payment__payment_number",
        "settlement_reception__reception_number", "cash_session__session_number",
    )
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = scope_cash(cash_movement_queryset(), self.request.user, "view_session")
        return filter_movements(self.filter_queryset(queryset), self.request.query_params)

    def list(self, request):
        queryset = self.get_queryset()
        totals = movement_totals(queryset)
        page = self.paginate_queryset(queryset)
        return success_response(
            self.paginator.payload(self.get_serializer(page, many=True).data, totals),
            "Movimientos obtenidos.",
        )

    def retrieve(self, request, pk=None):
        return success_response(self.get_serializer(self.get_object()).data, "Movimiento obtenido.")

    def create(self, request):
        payload = CashMovementInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        direction = payload.validated_data["direction"]
        permission = "create_income" if direction == CashMovementDirection.IN else "create_expense"
        require(request.user, permission, "No tienes permiso para registrar este movimiento.")
        session = get_object_or_404(
            scope_cash(cash_session_queryset(), request.user, "view_session"),
            pk=payload.validated_data["cash_session"].pk,
        )
        item, created = create_manual_movement(
            session, request.user, direction=direction,
            category=payload.validated_data["category"], amount=payload.validated_data["amount"],
            payment_method=payload.validated_data["payment_method"],
            description=payload.validated_data["description"],
            reference=payload.validated_data.get("reference", ""),
            idempotency_key=idempotency_key(request),
        )
        item = cash_movement_queryset().get(pk=item.pk)
        return success_response(
            self.get_serializer(item).data,
            "Movimiento registrado." if created else "Este movimiento ya fue procesado.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=("post",), url_path="void")
    def void(self, request, pk=None):
        require(request.user, "void_movement", "No tienes permiso para anular movimientos.")
        payload = VoidMovementSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = void_manual_movement(self.get_object(), request.user, payload.validated_data["reason"])
        return success_response(
            self.get_serializer(cash_movement_queryset().get(pk=item.pk)).data,
            "Movimiento anulado.",
        )


class SettlementReceptionViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = SettlementReceptionSerializer
    pagination_class = CashPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = scope_cash(reception_queryset(), self.request.user, "view_session")
        if self.request.query_params.get("session"):
            queryset = queryset.filter(cash_session_id=self.request.query_params["session"])
        return queryset

    def list(self, request):
        require(request.user, "view_session", "No tienes permiso para ver recepciones.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(
            self.paginator.payload(self.get_serializer(page, many=True).data),
            "Recepciones obtenidas.",
        )

    def retrieve(self, request, pk=None):
        require(request.user, "view_session", "No tienes permiso para ver recepciones.")
        return success_response(self.get_serializer(self.get_object()).data, "Recepción obtenida.")

    def create(self, request):
        require(
            request.user, "receive_collector_settlement",
            "No tienes permiso para recibir liquidaciones.",
        )
        payload = SettlementReceptionInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = get_object_or_404(
            scope_cash(cash_session_queryset(), request.user, "view_session"),
            pk=payload.validated_data["cash_session"].pk,
        )
        settlement = get_object_or_404(
            cash_settlements_for_user(request.user),
            pk=payload.validated_data["collector_settlement"].pk,
        )
        item, created = receive_collector_settlement(
            session, settlement, request.user,
            payload.validated_data["cash_received_by_cashier"],
            payload.validated_data.get("notes", ""), idempotency_key(request),
        )
        item = reception_queryset().get(pk=item.pk)
        return success_response(
            self.get_serializer(item).data,
            "Liquidación recibida correctamente." if created else "Esta recepción ya fue procesada.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=("get",), url_path="pending")
    def pending(self, request):
        require(
            request.user, "receive_collector_settlement",
            "No tienes permiso para recibir liquidaciones.",
        )
        queryset = pending_settlements_for_user(request.user)
        page = self.paginate_queryset(queryset)
        return success_response(
            self.paginator.payload(PendingSettlementSerializer(page, many=True).data),
            "Liquidaciones pendientes obtenidas.",
        )


class CashDashboardView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_session", "No tienes permiso para ver el dashboard de caja.")
        return success_response(cash_dashboard(request.user), "Indicadores de caja obtenidos.")


class CashOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permissions = get_cash_permissions(request.user)
        if not permissions.view_cash_register:
            raise PermissionDenied("No tienes acceso al módulo de caja.")
        branches = scoped_branches(request.user)
        registers = scope_cash(
            cash_register_queryset(), request.user, "view_cash_register"
        )
        return success_response(
            cash_options_payload(permissions, branches, registers), "Opciones de caja obtenidas."
        )


class CashMovementExcelView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "export_cash", "No tienes permiso para exportar movimientos.")
        queryset = filter_movements(
            scope_cash(cash_movement_queryset(), request.user, "view_session"),
            request.query_params,
        )
        totals = movement_totals(queryset)
        filters_text = ", ".join(
            f"{key}={value}" for key, value in request.query_params.items() if value
        )
        content = build_cash_movements_excel(
            list(queryset.order_by("created_at", "id")), totals, filters_text,
            timezone.localtime(),
        )
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="Movimientos_Caja.xlsx"'
        response["Content-Length"] = len(content)
        return response
