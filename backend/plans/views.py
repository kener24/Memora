from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from core.responses import success_response
from organizations.models import Branch, Organization

from .access import get_plan_permissions, is_global_plan_user, scope_plans, scope_services
from .choices import PlanActivityAction, ServiceCategory, ServiceUnit
from .models import FuneralPlan, FuneralPlanItem, FuneralServiceItem, PlanBranchAvailability
from .pagination import PlansPagination
from .permissions import PlanPermission, ServicePermission
from .serializers import (
    FuneralPlanCreateUpdateSerializer, FuneralPlanDetailSerializer, FuneralPlanListSerializer,
    ServiceCreateUpdateSerializer, ServiceDetailSerializer, ServiceListSerializer,
)
from .services import allocate_plan_code, record_plan_activity


class ServiceViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (ServicePermission,)
    pagination_class = PlansPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = ("code", "name", "description")
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        queryset = scope_services(
            FuneralServiceItem.objects.select_related("organization", "created_by"), self.request.user
        )
        params = self.request.query_params
        if params.get("is_active") in {"true", "false"}:
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        if params.get("category"):
            queryset = queryset.filter(category=params["category"])
        if params.get("organization") and is_global_plan_user(self.request.user):
            queryset = queryset.filter(organization_id=params["organization"])
        ordering = {
            "name": ("name",), "-name": ("-name",), "code": ("code",),
            "-created_at": ("-created_at",), "created_at": ("created_at",),
        }.get(params.get("ordering"), ("name",))
        return queryset.order_by(*ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return ServiceListSerializer
        if self.action in {"create", "partial_update", "update"}:
            return ServiceCreateUpdateSerializer
        return ServiceDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        return success_response(ServiceDetailSerializer(self.get_object(), context={"request": request}).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            service = serializer.save(created_by=request.user)
        return success_response(
            ServiceDetailSerializer(service, context={"request": request}).data,
            "Servicio agregado al catálogo.", status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            service = serializer.save()
        return success_response(
            ServiceDetailSerializer(service, context={"request": request}).data, "Servicio actualizado."
        )

    @action(detail=True, methods=("post",))
    def activate(self, request, pk=None):
        service = self.get_object()
        service.is_active = True
        service.save(update_fields=("is_active", "updated_at"))
        return success_response(ServiceDetailSerializer(service, context={"request": request}).data, "Servicio reactivado.")

    @action(detail=True, methods=("post",))
    def deactivate(self, request, pk=None):
        service = self.get_object()
        service.is_active = False
        service.save(update_fields=("is_active", "updated_at"))
        return success_response(ServiceDetailSerializer(service, context={"request": request}).data, "Servicio inactivado.")


class FuneralPlanViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    permission_classes = (PlanPermission,)
    pagination_class = PlansPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = ("code", "name", "description")
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        items = FuneralPlanItem.objects.select_related("service")
        queryset = FuneralPlan.objects.select_related("organization", "created_by").prefetch_related(
            Prefetch("items", queryset=items), "branch_availabilities__branch", "activities__user"
        )
        queryset = scope_plans(queryset, self.request.user)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("is_active") in {"true", "false"}:
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        if params.get("allow_financing") in {"true", "false"}:
            queryset = queryset.filter(allow_financing=params["allow_financing"] == "true")
        if params.get("branch"):
            queryset = queryset.filter(
                Q(available_all_branches=True) | Q(branch_availabilities__branch_id=params["branch"])
            ).distinct()
        for parameter, lookup in (("min_price", "base_price__gte"), ("max_price", "base_price__lte")):
            if params.get(parameter):
                try:
                    queryset = queryset.filter(**{lookup: Decimal(params[parameter])})
                except InvalidOperation:
                    raise ValidationError({parameter: "Ingresa un precio válido."})
        ordering = {
            "name": ("name",), "-name": ("-name",), "base_price": ("base_price",),
            "-base_price": ("-base_price",), "created_at": ("created_at",),
            "-created_at": ("-created_at",), "code": ("code",),
        }.get(params.get("ordering"), ("-created_at",))
        return queryset.annotate(
            items_count=Count("items", filter=Q(items__included=True), distinct=True)
        ).order_by(*ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return FuneralPlanListSerializer
        if self.action in {"create", "partial_update", "update"}:
            return FuneralPlanCreateUpdateSerializer
        return FuneralPlanDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        return success_response(
            FuneralPlanDetailSerializer(self.get_object(), context={"request": request}).data,
            "Plan obtenido correctamente.",
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                organization = serializer.validated_data["organization"]
                plan = serializer.save(code=allocate_plan_code(organization), created_by=request.user)
                record_plan_activity(plan, request.user, PlanActivityAction.CREATED)
        except IntegrityError as exc:
            raise ValidationError({"detail": "No fue posible guardar el plan completo."}) from exc
        return success_response(
            FuneralPlanDetailSerializer(plan, context={"request": request}).data,
            "Plan funerario creado.", status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        plan = self.get_object()
        old_price = plan.base_price
        old_services = set(plan.items.values_list("service_id", flat=True))
        serializer = self.get_serializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            plan = serializer.save()
            new_services = set(plan.items.values_list("service_id", flat=True))
            record_plan_activity(plan, request.user, PlanActivityAction.UPDATED)
            for _ in new_services - old_services:
                record_plan_activity(plan, request.user, PlanActivityAction.SERVICE_ADDED)
            for _ in old_services - new_services:
                record_plan_activity(plan, request.user, PlanActivityAction.SERVICE_REMOVED)
            if old_price != plan.base_price:
                record_plan_activity(
                    plan, request.user, PlanActivityAction.PRICE_CHANGED,
                    "Precio de venta actualizado.", old_price, plan.base_price,
                )
        return success_response(
            FuneralPlanDetailSerializer(plan, context={"request": request}).data, "Plan actualizado."
        )

    @action(detail=True, methods=("post",))
    def activate(self, request, pk=None):
        plan = self.get_object()
        if not plan.is_active:
            with transaction.atomic():
                plan.is_active = True
                plan.save(update_fields=("is_active", "updated_at"))
                record_plan_activity(plan, request.user, PlanActivityAction.ACTIVATED)
        return success_response(FuneralPlanDetailSerializer(plan, context={"request": request}).data, "Plan reactivado.")

    @action(detail=True, methods=("post",))
    def deactivate(self, request, pk=None):
        plan = self.get_object()
        if plan.is_active:
            with transaction.atomic():
                plan.is_active = False
                plan.save(update_fields=("is_active", "updated_at"))
                record_plan_activity(plan, request.user, PlanActivityAction.DEACTIVATED)
        return success_response(FuneralPlanDetailSerializer(plan, context={"request": request}).data, "Plan inactivado.")

    @action(detail=True, methods=("post",))
    def duplicate(self, request, pk=None):
        source = self.get_object()
        try:
            with transaction.atomic():
                duplicate = FuneralPlan.objects.create(
                    organization=source.organization,
                    code=allocate_plan_code(source.organization),
                    name=f"Copia de {source.name}"[:160],
                    description=source.description,
                    base_price=source.base_price,
                    initial_payment=source.initial_payment,
                    allow_financing=source.allow_financing,
                    available_all_branches=source.available_all_branches,
                    is_active=True,
                    created_by=request.user,
                )
                FuneralPlanItem.objects.bulk_create([
                    FuneralPlanItem(
                        plan=duplicate, service=item.service, quantity=item.quantity,
                        included=item.included, notes=item.notes, sort_order=item.sort_order,
                    ) for item in source.items.all()
                ])
                if not source.available_all_branches:
                    PlanBranchAvailability.objects.bulk_create([
                        PlanBranchAvailability(plan=duplicate, branch_id=item.branch_id)
                        for item in source.branch_availabilities.all()
                    ])
                record_plan_activity(
                    duplicate, request.user, PlanActivityAction.DUPLICATED,
                    f"Plan duplicado desde {source.code}.",
                )
        except IntegrityError as exc:
            raise ValidationError({"detail": "No fue posible duplicar el plan completo."}) from exc
        return success_response(
            FuneralPlanDetailSerializer(duplicate, context={"request": request}).data,
            "Plan duplicado correctamente.", status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=("get",), url_path="options")
    def module_options(self, request):
        permissions = get_plan_permissions(request.user)
        if permissions.global_access:
            branches = Branch.objects.filter(is_active=True).select_related("organization").order_by("name")
            organizations = Organization.objects.filter(is_active=True).order_by("name")
        else:
            branches = Branch.objects.filter(
                organization_id=request.user.organization_id, is_active=True
            ).order_by("name")
            organizations = []
        return success_response({
            "categories": [{"value": value, "label": label} for value, label in ServiceCategory.choices],
            "units": [{"value": value, "label": label} for value, label in ServiceUnit.choices],
            "branches": [
                {"id": branch.pk, "name": branch.name, "code": branch.code, "organization_id": branch.organization_id}
                for branch in branches
            ],
            "organizations": [{"id": org.pk, "name": org.name} for org in organizations],
            "permissions": permissions.as_dict(),
        }, "Opciones del módulo obtenidas.")
