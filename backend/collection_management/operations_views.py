from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import CustomUser, RoleCode
from contracts.access import scope_contracts
from contracts.models import Contract
from core.responses import success_response
from customers.models import Customer
from organizations.models import Branch

from .access import get_collection_permissions, role_code, scope_operations, scope_settlements
from .choices import AssignmentStatus, DayOfWeek, RouteVisitStatus, SettlementStatus, WorkSessionStatus
from .models import (
    CollectionAssignment, CollectionRoute, CollectionRouteStop, CollectionZone, CollectorSettlement,
    CollectorWorkSession, CustomerCollectionZone, RouteVisit,
)
from .operations import (
    assign_contract, bulk_assign_contracts, bulk_collector_metrics, close_work_session, collector_metrics, collector_portfolio,
    collector_today_portfolio, collector_users, decide_settlement, ensure_collector_profile,
    record_route_visit, reassign_contract, settlement_preview, start_work_session, submit_settlement,
    user_name, validate_collector,
)
from .operations_serializers import (
    AssignmentInputSerializer, AssignmentSerializer, BulkAssignmentInputSerializer,
    CustomerZoneInputSerializer, CustomerZoneSerializer, NotesSerializer, ReassignmentInputSerializer,
    RouteInputSerializer, RouteReorderSerializer, RouteSerializer, RouteStopInputSerializer,
    RouteVisitInputSerializer, SettlementDecisionSerializer, SettlementPreviewInputSerializer,
    SettlementSerializer, SettlementSubmitInputSerializer, WorkSessionSerializer, ZoneInputSerializer,
    ZoneSerializer,
)
from .excel import build_portfolio_excel
from .operations_exports import build_productivity_excel, build_settlement_pdf, build_settlements_excel
from .pagination import PortfolioPagination
from .services import apply_portfolio_filters, filtered_totals, portfolio_row


def require(user, permission, message):
    if not getattr(get_collection_permissions(user), permission):
        raise PermissionDenied(message)


def idempotency_key(request):
    key = request.headers.get("Idempotency-Key", "").strip()
    if len(key) < 8 or len(key) > 128:
        raise ValidationError({"idempotency_key": "Envía una clave de idempotencia válida (8 a 128 caracteres)."})
    return key


def scoped_branch(user, pk):
    queryset = Branch.objects.select_related("organization").filter(is_active=True)
    permissions = get_collection_permissions(user)
    if not permissions.global_access:
        queryset = queryset.filter(organization_id=user.organization_id)
    return get_object_or_404(queryset, pk=pk)


def scoped_customer(user, pk, branch=None):
    queryset = Customer.objects.filter(is_active=True)
    permissions = get_collection_permissions(user)
    if not permissions.global_access:
        queryset = queryset.filter(organization_id=user.organization_id)
    if branch:
        queryset = queryset.filter(Q(branch=branch) | Q(branch__isnull=True))
    return get_object_or_404(queryset, pk=pk)


def scoped_collector(user, pk, branch=None):
    collector = get_object_or_404(collector_users(user), pk=pk)
    validate_collector(collector, branch=branch)
    return collector


def serialize_portfolio(request, queryset, message):
    queryset = apply_portfolio_filters(queryset, request.query_params)
    totals = filtered_totals(queryset)
    paginator = PortfolioPagination()
    page = paginator.paginate_queryset(queryset, request)
    return success_response(paginator.payload([portfolio_row(item) for item in page], totals), message)


def route_queryset(user, *, own=False):
    visits = RouteVisit.objects.filter(visit_date=timezone.localdate())
    stops = CollectionRouteStop.objects.filter(is_active=True).select_related("customer").prefetch_related(
        Prefetch("visits", queryset=visits, to_attr="today_visits")
    )
    queryset = CollectionRoute.objects.select_related(
        "organization", "branch", "zone", "collector"
    ).prefetch_related(Prefetch("stops", queryset=stops))
    if own:
        if role_code(user) != RoleCode.COLLECTOR:
            return queryset.none()
        return queryset.filter(
            organization_id=user.organization_id, branch_id=user.branch_id, is_active=True,
        ).filter(Q(collector=user) | Q(collector__isnull=True))
    return scope_operations(queryset, user, "manage_routes")


class CollectorViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    pagination_class = PortfolioPagination
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self):
        return collector_users(self.request.user)

    def _data(self, collector, include_metrics=True, metrics=None):
        profile = getattr(collector, "collector_profile", None)
        data = {
            "id": collector.pk,
            "username": collector.username,
            "name": user_name(collector),
            "email": collector.email,
            "branch": collector.branch_id,
            "branch_name": collector.branch.name if collector.branch_id else None,
            "employee_code": profile.employee_code if profile else None,
            "is_available": profile.is_available if profile else True,
            "notes": profile.notes if profile else "",
            "is_active": collector.is_active,
        }
        if include_metrics:
            data["metrics"] = metrics if metrics is not None else collector_metrics(self.request.user, collector)
        return data

    def list(self, request):
        require(request.user, "view_collector_metrics", "No tienes permiso para ver cobradores.")
        queryset = self.get_queryset()
        if request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=request.query_params["branch"])
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(collector_profile__employee_code__icontains=search)
            )
        page = list(self.paginate_queryset(queryset.order_by("first_name", "last_name", "username")))
        metrics = bulk_collector_metrics(request.user, page)
        return success_response(
            self.paginator.payload([self._data(item, metrics=metrics[item.pk]) for item in page]), "Cobradores obtenidos.",
        )

    def retrieve(self, request, pk=None):
        require(request.user, "view_collector_metrics", "No tienes permiso para ver cobradores.")
        collector = get_object_or_404(self.get_queryset(), pk=pk)
        return success_response(self._data(collector), "Cobrador obtenido.")

    def partial_update(self, request, pk=None):
        require(request.user, "manage_collectors", "No tienes permiso para administrar cobradores.")
        collector = get_object_or_404(self.get_queryset(), pk=pk)
        profile = ensure_collector_profile(collector, request.user)
        allowed = {"is_available", "notes"}
        unknown = set(request.data) - allowed
        if unknown:
            raise ValidationError({"detail": f"Campos no permitidos: {', '.join(sorted(unknown))}."})
        if "is_available" in request.data:
            if not isinstance(request.data["is_available"], bool):
                raise ValidationError({"is_available": "Envía verdadero o falso."})
            profile.is_available = request.data["is_available"]
        if "notes" in request.data:
            profile.notes = str(request.data["notes"]).strip()[:1000]
        profile.save(update_fields=("is_available", "notes", "updated_at"))
        collector = self.get_queryset().get(pk=collector.pk)
        return success_response(self._data(collector), "Perfil del cobrador actualizado.")

    @action(detail=True, methods=("get",), url_path="portfolio")
    def portfolio(self, request, pk=None):
        require(request.user, "view_collector_metrics", "No tienes permiso para ver esta cartera.")
        collector = get_object_or_404(self.get_queryset(), pk=pk)
        return serialize_portfolio(request, collector_portfolio(request.user, collector), "Cartera del cobrador obtenida.")

    @action(detail=True, methods=("get",), url_path="metrics")
    def metrics(self, request, pk=None):
        require(request.user, "view_collector_metrics", "No tienes permiso para ver productividad.")
        collector = get_object_or_404(self.get_queryset(), pk=pk)
        return success_response(collector_metrics(request.user, collector), "Productividad obtenida.")


class OwnCollectorPortfolioView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_own_portfolio", "Este espacio es exclusivo para cobradores.")
        return serialize_portfolio(request, collector_portfolio(request.user, request.user), "Mi cartera obtenida.")


class OwnCollectorTodayView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_own_portfolio", "Este espacio es exclusivo para cobradores.")
        return serialize_portfolio(
            request, collector_today_portfolio(request.user, request.user), "Agenda de cobro obtenida.",
        )


class OwnCollectorMetricsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_own_portfolio", "Este espacio es exclusivo para cobradores.")
        return success_response(collector_metrics(request.user, request.user), "Mis indicadores obtenidos.")


class OwnCollectorRoutesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "view_own_portfolio", "Este espacio es exclusivo para cobradores.")
        queryset = route_queryset(request.user, own=True)
        day = request.query_params.get("day")
        if day not in (None, ""):
            try:
                day = int(day)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"day": "El día de la semana no es válido."}) from exc
            queryset = queryset.filter(Q(day_of_week=day) | Q(day_of_week__isnull=True))
        return success_response(RouteSerializer(queryset, many=True).data, "Mis rutas obtenidas.")


class AssignmentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = AssignmentSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = CollectionAssignment.objects.select_related(
            "organization", "branch", "contract", "collector", "assigned_by", "previous_assignment",
        )
        queryset = scope_operations(queryset, self.request.user, "assign_portfolio")
        params = self.request.query_params
        if params.get("collector"):
            queryset = queryset.filter(collector_id=params["collector"])
        if params.get("contract"):
            queryset = queryset.filter(contract_id=params["contract"])
        if params.get("status") in AssignmentStatus.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def list(self, request, *args, **kwargs):
        require(request.user, "assign_portfolio", "No tienes permiso para ver asignaciones.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Asignaciones obtenidas.")

    def retrieve(self, request, *args, **kwargs):
        require(request.user, "assign_portfolio", "No tienes permiso para ver asignaciones.")
        return success_response(self.get_serializer(self.get_object()).data, "Asignación obtenida.")

    def create(self, request, *args, **kwargs):
        require(request.user, "assign_portfolio", "No tienes permiso para asignar cartera.")
        payload = AssignmentInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contract = get_object_or_404(scope_contracts(Contract.objects.all(), request.user), pk=payload.validated_data["contract"])
        collector = scoped_collector(request.user, payload.validated_data["collector"], contract.branch)
        item = assign_contract(contract, collector, request.user, payload.validated_data.get("reason", ""))
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Cartera asignada.", status=status.HTTP_201_CREATED)

    @action(detail=False, methods=("post",), url_path="bulk")
    def bulk(self, request):
        require(request.user, "assign_portfolio", "No tienes permiso para asignar cartera.")
        payload = BulkAssignmentInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        requested_ids = set(payload.validated_data["contracts"])
        contracts = list(scope_contracts(Contract.objects.all(), request.user).filter(pk__in=requested_ids))
        if {contract.pk for contract in contracts} != requested_ids:
            raise ValidationError({"contracts": "Uno o más contratos no existen o están fuera de tu alcance."})
        collector = scoped_collector(request.user, payload.validated_data["collector"])
        items = bulk_assign_contracts(contracts, collector, request.user, payload.validated_data.get("reason", ""))
        data = self.get_serializer(self.get_queryset().filter(pk__in=[item.pk for item in items]), many=True).data
        return success_response(data, f"Se asignaron {len(items)} contratos.", status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="reassign")
    def reassign(self, request, pk=None):
        require(request.user, "reassign_portfolio", "No tienes permiso para reasignar cartera.")
        payload = ReassignmentInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        current = self.get_object()
        collector = scoped_collector(request.user, payload.validated_data["collector"], current.branch)
        replacement = reassign_contract(current, collector, request.user, payload.validated_data["reason"])
        return success_response(self.get_serializer(self.get_queryset().get(pk=replacement.pk)).data, "Cartera reasignada.")


class ZoneViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = ZoneSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        queryset = CollectionZone.objects.select_related("organization", "branch").annotate(
            customer_count=Count("customer_links", filter=Q(customer_links__customer__is_active=True))
        )
        queryset = scope_operations(queryset, self.request.user, "manage_zones")
        if self.request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=self.request.query_params["branch"])
        if self.request.query_params.get("active") in {"true", "false"}:
            queryset = queryset.filter(is_active=self.request.query_params["active"] == "true")
        return queryset

    def list(self, request):
        require(request.user, "manage_zones", "No tienes permiso para ver zonas.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Zonas obtenidas.")

    def retrieve(self, request, pk=None):
        require(request.user, "manage_zones", "No tienes permiso para ver zonas.")
        return success_response(self.get_serializer(get_object_or_404(self.get_queryset(), pk=pk)).data, "Zona obtenida.")

    def create(self, request):
        require(request.user, "manage_zones", "No tienes permiso para crear zonas.")
        payload = ZoneInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        branch = scoped_branch(request.user, payload.validated_data["branch"])
        try:
            item = CollectionZone.objects.create(
                organization=branch.organization, branch=branch, created_by=request.user,
                code=payload.validated_data["code"].strip().upper(), name=payload.validated_data["name"].strip(),
                description=payload.validated_data.get("description", "").strip(),
            )
        except IntegrityError as exc:
            raise ValidationError({"code": "Ya existe una zona con este código."}) from exc
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Zona creada.", status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        require(request.user, "manage_zones", "No tienes permiso para actualizar zonas.")
        item = get_object_or_404(self.get_queryset(), pk=pk)
        for field in ("name", "description", "is_active"):
            if field in request.data:
                setattr(item, field, request.data[field])
        item.full_clean()
        item.save()
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Zona actualizada.")

    @action(detail=True, methods=("post",), url_path="assign-customer")
    def assign_customer(self, request, pk=None):
        require(request.user, "manage_zones", "No tienes permiso para asignar zonas.")
        payload = CustomerZoneInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        zone = get_object_or_404(self.get_queryset(), pk=pk, is_active=True)
        customer = scoped_customer(request.user, payload.validated_data["customer"], zone.branch)
        assignment, _ = CustomerCollectionZone.objects.update_or_create(
            customer=customer, defaults={"zone": zone, "assigned_by": request.user},
        )
        return success_response(CustomerZoneSerializer(assignment).data, "Zona asignada al cliente.")


class RouteViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = RouteSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        queryset = route_queryset(self.request.user)
        if self.request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=self.request.query_params["branch"])
        if self.request.query_params.get("collector"):
            queryset = queryset.filter(collector_id=self.request.query_params["collector"])
        return queryset

    def list(self, request):
        require(request.user, "manage_routes", "No tienes permiso para ver rutas.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Rutas obtenidas.")

    def retrieve(self, request, pk=None):
        require(request.user, "manage_routes", "No tienes permiso para ver rutas.")
        return success_response(self.get_serializer(get_object_or_404(self.get_queryset(), pk=pk)).data, "Ruta obtenida.")

    def create(self, request):
        require(request.user, "manage_routes", "No tienes permiso para crear rutas.")
        payload = RouteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        branch = scoped_branch(request.user, payload.validated_data["branch"])
        zone = None
        if payload.validated_data.get("zone"):
            zone = get_object_or_404(CollectionZone, pk=payload.validated_data["zone"], branch=branch, is_active=True)
        collector = None
        if payload.validated_data.get("collector"):
            collector = scoped_collector(request.user, payload.validated_data["collector"], branch)
        item = CollectionRoute.objects.create(
            organization=branch.organization, branch=branch, zone=zone, collector=collector,
            day_of_week=payload.validated_data.get("day_of_week"), name=payload.validated_data["name"].strip(),
            description=payload.validated_data.get("description", "").strip(), created_by=request.user,
        )
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Ruta creada.", status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        require(request.user, "manage_routes", "No tienes permiso para actualizar rutas.")
        item = get_object_or_404(self.get_queryset(), pk=pk)
        for field in ("name", "description", "day_of_week", "is_active"):
            if field in request.data:
                setattr(item, field, request.data[field])
        if "collector" in request.data:
            item.collector = scoped_collector(request.user, request.data["collector"], item.branch) if request.data["collector"] else None
        if "zone" in request.data:
            item.zone = get_object_or_404(CollectionZone, pk=request.data["zone"], branch=item.branch) if request.data["zone"] else None
        item.full_clean()
        item.save()
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Ruta actualizada.")

    @action(detail=True, methods=("post",), url_path="stops")
    def add_stop(self, request, pk=None):
        require(request.user, "manage_routes", "No tienes permiso para actualizar rutas.")
        payload = RouteStopInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        route = get_object_or_404(self.get_queryset(), pk=pk)
        customer = scoped_customer(request.user, payload.validated_data["customer"], route.branch)
        position = (route.stops.filter(is_active=True).aggregate(value=Count("id"))["value"] or 0) + 1
        try:
            CollectionRouteStop.objects.create(
                route=route, customer=customer, position=position,
                notes=payload.validated_data.get("notes", "").strip(), is_primary=True,
            )
        except IntegrityError as exc:
            raise ValidationError({"customer": "Este cliente ya pertenece a una ruta activa."}) from exc
        return success_response(self.get_serializer(self.get_queryset().get(pk=route.pk)).data, "Parada agregada.", status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="reorder")
    def reorder(self, request, pk=None):
        require(request.user, "manage_routes", "No tienes permiso para reordenar rutas.")
        payload = RouteReorderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        route = get_object_or_404(self.get_queryset(), pk=pk)
        requested = payload.validated_data["stops"]
        with transaction.atomic():
            stops = list(CollectionRouteStop.objects.select_for_update().filter(route=route, is_active=True))
            if len(requested) != len(set(requested)) or set(requested) != {item.pk for item in stops}:
                raise ValidationError({"stops": "Envía todas las paradas activas una sola vez."})
            by_id = {item.pk: item for item in stops}
            for offset, stop_id in enumerate(requested, start=1):
                CollectionRouteStop.objects.filter(pk=stop_id).update(position=100000 + offset)
            for position, stop_id in enumerate(requested, start=1):
                by_id[stop_id].position = position
            CollectionRouteStop.objects.bulk_update(by_id.values(), ("position",))
        return success_response(self.get_serializer(self.get_queryset().get(pk=route.pk)).data, "Ruta reordenada.")

    @action(detail=True, methods=("post",), url_path=r"stops/(?P<stop_id>[^/.]+)/remove")
    def remove_stop(self, request, pk=None, stop_id=None):
        require(request.user, "manage_routes", "No tienes permiso para actualizar rutas.")
        route = get_object_or_404(self.get_queryset(), pk=pk)
        stop = get_object_or_404(CollectionRouteStop, route=route, pk=stop_id, is_active=True)
        stop.is_active = False
        stop.is_primary = False
        stop.save(update_fields=("is_active", "is_primary", "updated_at"))
        active = list(route.stops.filter(is_active=True))
        for position, item in enumerate(active, start=1):
            item.position = position
        CollectionRouteStop.objects.bulk_update(active, ("position",))
        return success_response(self.get_serializer(self.get_queryset().get(pk=route.pk)).data, "Parada retirada.")


class RouteVisitView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, stop_id):
        require(request.user, "view_own_portfolio", "Solo un cobrador puede registrar visitas de ruta.")
        payload = RouteVisitInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        stop = get_object_or_404(
            CollectionRouteStop.objects.select_related("route"), pk=stop_id, is_active=True,
            route__organization_id=request.user.organization_id, route__branch_id=request.user.branch_id,
        )
        visit = record_route_visit(
            stop, request.user, payload.validated_data["status"], payload.validated_data.get("notes", ""),
        )
        return success_response({
            "id": visit.pk, "status": visit.status, "status_label": visit.get_status_display(),
            "notes": visit.notes, "collection_action": visit.collection_action_id,
        }, "Visita registrada.")


class WorkSessionViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = WorkSessionSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = CollectorWorkSession.objects.select_related(
            "organization", "branch", "collector", "opened_by", "closed_by",
        )
        permissions = get_collection_permissions(self.request.user)
        if role_code(self.request.user) == RoleCode.COLLECTOR:
            return queryset.filter(collector=self.request.user)
        if not (permissions.start_work_session or permissions.view_settlement):
            return queryset.none()
        return scope_operations(queryset, self.request.user, "view_collector_metrics")

    def list(self, request):
        require(request.user, "view_collector_metrics", "No tienes permiso para ver jornadas.")
        queryset = self.get_queryset()
        if request.query_params.get("collector"):
            queryset = queryset.filter(collector_id=request.query_params["collector"])
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context={"include_summary": False})
        return success_response(self.paginator.payload(serializer.data), "Jornadas obtenidas.")

    def retrieve(self, request, pk=None):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        return success_response(self.get_serializer(session).data, "Jornada obtenida.")

    @action(detail=False, methods=("get",), url_path="current")
    def current(self, request):
        require(request.user, "start_work_session", "No tienes permiso para gestionar jornadas.")
        collector_id = request.query_params.get("collector")
        collector = request.user if role_code(request.user) == RoleCode.COLLECTOR else scoped_collector(request.user, collector_id)
        session = self.get_queryset().filter(collector=collector, status=WorkSessionStatus.OPEN).first()
        return success_response(self.get_serializer(session).data if session else None, "Jornada actual obtenida.")

    @action(detail=False, methods=("post",), url_path="start")
    def start(self, request):
        require(request.user, "start_work_session", "No tienes permiso para iniciar jornadas.")
        payload = NotesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        collector_id = request.data.get("collector")
        collector = request.user if role_code(request.user) == RoleCode.COLLECTOR else scoped_collector(request.user, collector_id)
        session = start_work_session(collector, request.user, payload.validated_data.get("notes", ""))
        return success_response(self.get_serializer(session).data, "Jornada iniciada.", status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="close")
    def close(self, request, pk=None):
        require(request.user, "close_work_session", "No tienes permiso para cerrar jornadas.")
        payload = NotesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = get_object_or_404(self.get_queryset(), pk=pk)
        if role_code(request.user) == RoleCode.COLLECTOR and session.collector_id != request.user.pk:
            raise PermissionDenied("No puedes cerrar la jornada de otro cobrador.")
        session = close_work_session(session, request.user, payload.validated_data.get("notes", ""))
        return success_response(self.get_serializer(session).data, "Jornada cerrada.")


class SettlementViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = SettlementSerializer
    pagination_class = PortfolioPagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        queryset = CollectorSettlement.objects.select_related(
            "organization", "branch", "collector", "work_session", "submitted_by", "reviewed_by",
        ).prefetch_related("payment_items__payment", "operations_audits__actor")
        queryset = scope_settlements(queryset, self.request.user)
        params = self.request.query_params
        if params.get("collector"):
            queryset = queryset.filter(collector_id=params["collector"])
        if params.get("status") in SettlementStatus.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def list(self, request):
        require(request.user, "view_settlement", "No tienes permiso para ver liquidaciones.")
        page = self.paginate_queryset(self.get_queryset())
        return success_response(self.paginator.payload(self.get_serializer(page, many=True).data), "Liquidaciones obtenidas.")

    def retrieve(self, request, pk=None):
        require(request.user, "view_settlement", "No tienes permiso para ver liquidaciones.")
        return success_response(self.get_serializer(self.get_object()).data, "Liquidación obtenida.")

    @action(detail=False, methods=("post",), url_path="preview")
    def preview(self, request):
        require(request.user, "submit_settlement", "No tienes permiso para liquidar jornadas.")
        payload = SettlementPreviewInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        queryset = CollectorWorkSession.objects.filter(collector=request.user)
        if payload.validated_data.get("work_session"):
            queryset = queryset.filter(pk=payload.validated_data["work_session"])
        else:
            queryset = queryset.filter(status=WorkSessionStatus.CLOSED, settlement__isnull=True)
        session = queryset.first()
        if not session:
            raise ValidationError({"work_session": "No existe una jornada cerrada pendiente de liquidar."})
        return success_response({"work_session": session.pk, **settlement_preview(session)}, "Vista previa calculada.")

    @action(detail=False, methods=("post",), url_path="submit")
    def submit(self, request):
        require(request.user, "submit_settlement", "No tienes permiso para presentar liquidaciones.")
        payload = SettlementSubmitInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = get_object_or_404(
            CollectorWorkSession, pk=payload.validated_data["work_session"], collector=request.user,
        )
        item, created = submit_settlement(
            session, request.user, payload.validated_data["reported_cash"],
            payload.validated_data.get("notes", ""), payload.validated_data["payment_fingerprint"],
            idempotency_key(request),
        )
        item = self.get_queryset().get(pk=item.pk)
        return success_response(
            self.get_serializer(item).data,
            "Liquidación presentada." if created else "Liquidación recuperada de forma idempotente.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=("post",), url_path="review")
    def review(self, request, pk=None):
        require(request.user, "review_settlement", "No tienes permiso para revisar liquidaciones.")
        payload = SettlementDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        from .operations import review_settlement
        item = review_settlement(self.get_object(), request.user, payload.validated_data.get("reason", ""))
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Liquidación revisada.")

    @action(detail=True, methods=("post",), url_path="accept")
    def accept(self, request, pk=None):
        require(request.user, "accept_settlement", "No tienes permiso para aceptar liquidaciones.")
        payload = SettlementDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = decide_settlement(self.get_object(), request.user, accept=True, reason=payload.validated_data.get("reason", ""))
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Liquidación aceptada.")

    @action(detail=True, methods=("post",), url_path="reject")
    def reject(self, request, pk=None):
        require(request.user, "reject_settlement", "No tienes permiso para rechazar liquidaciones.")
        payload = SettlementDecisionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = decide_settlement(self.get_object(), request.user, accept=False, reason=payload.validated_data.get("reason", ""))
        return success_response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data, "Liquidación rechazada.")


class OperationsOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permissions = get_collection_permissions(request.user)
        if not (permissions.view_collector_metrics or permissions.view_own_portfolio):
            raise PermissionDenied("No tienes permiso para ver la operación de cobranza.")
        branches = Branch.objects.filter(is_active=True)
        if not permissions.global_access:
            branches = branches.filter(organization_id=request.user.organization_id)
        collectors = collector_users(request.user).order_by("first_name", "last_name", "username")
        zones = CollectionZone.objects.filter(is_active=True)
        if not permissions.global_access:
            zones = zones.filter(organization_id=request.user.organization_id)
        return success_response({
            "collectors": [{"id": item.pk, "name": user_name(item), "branch": item.branch_id} for item in collectors],
            "branches": [{"id": item.pk, "name": item.name} for item in branches],
            "zones": [{"id": item.pk, "name": item.name, "branch": item.branch_id} for item in zones],
            "days": [{"value": value, "label": label} for value, label in DayOfWeek.choices],
            "visit_statuses": [{"value": value, "label": label} for value, label in RouteVisitStatus.choices],
            "settlement_statuses": [{"value": value, "label": label} for value, label in SettlementStatus.choices],
            "permissions": permissions.as_dict(),
        }, "Opciones operativas obtenidas.")


class CollectorPortfolioExcelView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, collector_id):
        require(request.user, "export_collections", "No tienes permiso para exportar cartera de cobradores.")
        collector = scoped_collector(request.user, collector_id)
        queryset = apply_portfolio_filters(collector_portfolio(request.user, collector), request.query_params)
        totals = filtered_totals(queryset)
        rows = [portfolio_row(item) for item in queryset[:10000]]
        content = build_portfolio_excel(
            rows, totals, f"Cobrador: {user_name(collector)}", timezone.localtime(),
        )
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="Cartera_{collector.pk}_{timezone.localdate():%Y%m%d}.xlsx"'
        response["Content-Length"] = len(content)
        return response


class ProductivityExcelView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "export_collections", "No tienes permiso para exportar productividad.")
        rows = []
        queryset = collector_users(request.user)
        if request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=request.query_params["branch"])
        for collector in queryset.order_by("first_name", "last_name", "username"):
            profile = getattr(collector, "collector_profile", None)
            rows.append({
                "employee_code": profile.employee_code if profile else "",
                "name": user_name(collector), "branch_name": collector.branch.name if collector.branch_id else "",
                **collector_metrics(request.user, collector),
            })
        content = build_productivity_excel(rows, timezone.localtime())
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="Productividad_Cobradores_{timezone.localdate():%Y%m%d}.xlsx"'
        response["Content-Length"] = len(content)
        return response


class SettlementsExcelView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        require(request.user, "export_collections", "No tienes permiso para exportar liquidaciones.")
        queryset = scope_settlements(CollectorSettlement.objects.select_related(
            "branch", "collector", "reviewed_by",
        ), request.user)
        if request.query_params.get("collector"):
            queryset = queryset.filter(collector_id=request.query_params["collector"])
        if request.query_params.get("status") in SettlementStatus.values:
            queryset = queryset.filter(status=request.query_params["status"])
        rows = [{
            "settlement_number": item.settlement_number, "submitted_at": timezone.localtime(item.submitted_at),
            "collector_name": user_name(item.collector), "branch_name": item.branch.name,
            "total_collected": item.total_collected, "expected_cash": item.expected_cash,
            "reported_cash": item.reported_cash, "transfer_total": item.transfer_total,
            "card_total": item.card_total, "check_total": item.check_total, "other_total": item.other_total,
            "difference": item.difference, "status_label": item.get_status_display(),
            "reviewed_by_name": user_name(item.reviewed_by) if item.reviewed_by else "",
        } for item in queryset[:10000]]
        content = build_settlements_excel(rows, timezone.localtime())
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="Liquidaciones_Cobradores_{timezone.localdate():%Y%m%d}.xlsx"'
        response["Content-Length"] = len(content)
        return response


class SettlementPDFView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, settlement_id):
        require(request.user, "view_settlement", "No tienes permiso para imprimir esta liquidación.")
        queryset = scope_settlements(CollectorSettlement.objects.select_related(
            "organization", "branch", "collector", "work_session", "submitted_by", "reviewed_by",
        ).prefetch_related("payment_items__payment"), request.user)
        item = get_object_or_404(queryset, pk=settlement_id)
        content = build_settlement_pdf(item)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="Liquidacion_{item.settlement_number}.pdf"'
        response["Content-Length"] = len(content)
        return response
