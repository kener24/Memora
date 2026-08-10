from decimal import Decimal

from rest_framework import serializers

from organizations.models import Branch, Organization

from .access import get_plan_permissions, is_global_plan_user
from .models import (
    FuneralPlan, FuneralPlanItem, FuneralServiceItem, PlanActivity, PlanBranchAvailability,
)


def user_can_view_costs(context):
    request = context.get("request")
    return bool(request and get_plan_permissions(request.user).view_costs)


class CostProtectedSerializer(serializers.ModelSerializer):
    cost_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not user_can_view_costs(self.context):
            for field in self.cost_fields:
                self.fields.pop(field, None)


class ServiceListSerializer(CostProtectedSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    unit_label = serializers.CharField(source="get_unit_display", read_only=True)
    cost_fields = ("estimated_cost",)

    class Meta:
        model = FuneralServiceItem
        fields = (
            "id", "code", "name", "description", "category", "category_label", "unit", "unit_label",
            "estimated_cost", "default_sale_price", "is_active", "created_at", "updated_at",
        )


class ServiceDetailSerializer(ServiceListSerializer):
    organization = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta(ServiceListSerializer.Meta):
        fields = ServiceListSerializer.Meta.fields + ("organization", "created_by")

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_created_by(self, obj):
        name = obj.created_by.get_full_name().strip() or obj.created_by.username
        return {"id": obj.created_by_id, "name": name}


class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True), required=False, write_only=True
    )
    estimated_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))
    default_sale_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))

    class Meta:
        model = FuneralServiceItem
        fields = (
            "organization", "code", "name", "description", "category", "unit",
            "estimated_cost", "default_sale_price",
        )
        validators = []

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("El código es obligatorio.")
        return value

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        submitted_org = attrs.get("organization")
        if self.instance:
            organization = self.instance.organization
            if submitted_org and submitted_org.pk != organization.pk:
                raise serializers.ValidationError({"organization": "La organización no puede cambiarse."})
            attrs.pop("organization", None)
        elif is_global_plan_user(user):
            organization = submitted_org or user.organization
            if not organization:
                raise serializers.ValidationError({"organization": "Selecciona la organización."})
            attrs["organization"] = organization
        else:
            if not user.organization_id:
                raise serializers.ValidationError({"organization": "Tu usuario no tiene organización asignada."})
            if submitted_org and submitted_org.pk != user.organization_id:
                raise serializers.ValidationError({"organization": "La organización se determina desde tu sesión."})
            organization = user.organization
            attrs["organization"] = organization

        code = attrs.get("code", getattr(self.instance, "code", ""))
        duplicate = FuneralServiceItem.objects.filter(organization=organization, code=code)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"code": "Ya existe un servicio con este código."})
        return attrs


class PlanItemInputSerializer(serializers.Serializer):
    service_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    included = serializers.BooleanField(default=True)
    notes = serializers.CharField(max_length=240, required=False, allow_blank=True)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class FuneralPlanItemSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()

    class Meta:
        model = FuneralPlanItem
        fields = ("id", "service", "quantity", "included", "notes", "sort_order", "created_at", "updated_at")

    def get_service(self, obj):
        data = {
            "id": obj.service_id,
            "code": obj.service.code,
            "name": obj.service.name,
            "category": obj.service.category,
            "category_label": obj.service.get_category_display(),
            "unit": obj.service.unit,
            "unit_label": obj.service.get_unit_display(),
            "is_active": obj.service.is_active,
        }
        if user_can_view_costs(self.context):
            data["estimated_cost"] = f"{obj.service.estimated_cost:.2f}"
        return data


class PlanActivitySerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = PlanActivity
        fields = ("id", "action", "action_label", "description", "old_value", "new_value", "user", "created_at")

    def get_user(self, obj):
        if not obj.user:
            return None
        return {"id": obj.user_id, "name": obj.user.get_full_name().strip() or obj.user.username}


class FuneralPlanListSerializer(CostProtectedSerializer):
    items_count = serializers.SerializerMethodField()
    estimated_plan_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    estimated_margin = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    estimated_margin_percent = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True, allow_null=True)
    availability = serializers.SerializerMethodField()
    cost_fields = ("estimated_plan_cost", "estimated_margin", "estimated_margin_percent")

    class Meta:
        model = FuneralPlan
        fields = (
            "id", "code", "name", "description", "base_price", "initial_payment", "allow_financing",
            "available_all_branches", "availability", "items_count", "estimated_plan_cost", "estimated_margin",
            "estimated_margin_percent", "is_active", "created_at", "updated_at",
        )

    def get_availability(self, obj):
        if obj.available_all_branches:
            return {"all_branches": True, "branches": []}
        branches = [availability.branch for availability in obj.branch_availabilities.all()]
        return {
            "all_branches": False,
            "branches": [{"id": branch.pk, "name": branch.name, "code": branch.code} for branch in branches],
        }

    def get_items_count(self, obj):
        annotated = getattr(obj, "items_count", None)
        if annotated is not None:
            return annotated
        return sum(1 for item in obj.items.all() if item.included)


class FuneralPlanDetailSerializer(FuneralPlanListSerializer):
    organization = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    items = FuneralPlanItemSerializer(many=True, read_only=True)
    activities = PlanActivitySerializer(many=True, read_only=True)

    class Meta(FuneralPlanListSerializer.Meta):
        fields = FuneralPlanListSerializer.Meta.fields + ("organization", "created_by", "items", "activities")

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_created_by(self, obj):
        return {"id": obj.created_by_id, "name": obj.created_by.get_full_name().strip() or obj.created_by.username}


class FuneralPlanCreateUpdateSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True), required=False, write_only=True
    )
    items = PlanItemInputSerializer(many=True, required=False, write_only=True)
    available_branch_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, write_only=True
    )
    base_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))
    initial_payment = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))

    class Meta:
        model = FuneralPlan
        fields = (
            "organization", "name", "description", "base_price", "initial_payment", "allow_financing",
            "available_all_branches", "items", "available_branch_ids",
        )

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        submitted_org = attrs.get("organization")
        if self.instance:
            organization = self.instance.organization
            if submitted_org and submitted_org.pk != organization.pk:
                raise serializers.ValidationError({"organization": "La organización no puede cambiarse."})
            attrs.pop("organization", None)
        elif is_global_plan_user(user):
            organization = submitted_org or user.organization
            if not organization:
                raise serializers.ValidationError({"organization": "Selecciona la organización."})
            attrs["organization"] = organization
        else:
            if not user.organization_id:
                raise serializers.ValidationError({"organization": "Tu usuario no tiene organización asignada."})
            if submitted_org and submitted_org.pk != user.organization_id:
                raise serializers.ValidationError({"organization": "La organización se determina desde tu sesión."})
            organization = user.organization
            attrs["organization"] = organization

        base_price = attrs.get("base_price", getattr(self.instance, "base_price", Decimal("0")))
        initial_payment = attrs.get("initial_payment", getattr(self.instance, "initial_payment", Decimal("0")))
        if initial_payment > base_price:
            raise serializers.ValidationError({"initial_payment": "La prima sugerida no puede superar el precio."})

        items = attrs.get("items")
        if (not self.instance and not items) or (self.instance and items is not None and not items):
            raise serializers.ValidationError({"items": "Agrega al menos una prestación al plan."})
        if items is not None:
            service_ids = [item["service_id"] for item in items]
            if len(service_ids) != len(set(service_ids)):
                raise serializers.ValidationError({"items": "No repitas la misma prestación dentro del plan."})
            services = {
                service.pk: service for service in FuneralServiceItem.objects.filter(pk__in=service_ids)
            }
            existing_ids = set(self.instance.items.values_list("service_id", flat=True)) if self.instance else set()
            for item in items:
                service = services.get(item["service_id"])
                if not service or service.organization_id != organization.pk:
                    raise serializers.ValidationError({"items": "Una prestación no pertenece a la organización permitida."})
                if not service.is_active and service.pk not in existing_ids:
                    raise serializers.ValidationError({"items": f"{service.name} está inactivo y no puede agregarse."})
                item["service"] = service

        all_branches = attrs.get(
            "available_all_branches", getattr(self.instance, "available_all_branches", True)
        )
        branch_ids = attrs.get("available_branch_ids")
        if not all_branches:
            if branch_ids is None and self.instance:
                branch_ids = list(self.instance.branch_availabilities.values_list("branch_id", flat=True))
            if not branch_ids:
                raise serializers.ValidationError({"available_branch_ids": "Selecciona al menos una sucursal."})
            if len(branch_ids) != len(set(branch_ids)):
                raise serializers.ValidationError({"available_branch_ids": "No repitas sucursales."})
            valid_count = Branch.objects.filter(
                pk__in=branch_ids, organization=organization, is_active=True
            ).count()
            if valid_count != len(branch_ids):
                raise serializers.ValidationError({"available_branch_ids": "Una sucursal no pertenece a la organización."})
        return attrs

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        branch_ids = validated_data.pop("available_branch_ids", [])
        plan = FuneralPlan.objects.create(**validated_data)
        self._replace_items(plan, items)
        self._replace_branches(plan, branch_ids)
        return plan

    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        branch_ids = validated_data.pop("available_branch_ids", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if items is not None:
            self._replace_items(instance, items)
        if instance.available_all_branches:
            instance.branch_availabilities.all().delete()
        elif branch_ids is not None:
            self._replace_branches(instance, branch_ids)
        return instance

    @staticmethod
    def _replace_items(plan, items):
        plan.items.all().delete()
        FuneralPlanItem.objects.bulk_create([
            FuneralPlanItem(
                plan=plan,
                service=item["service"],
                quantity=item["quantity"],
                included=item.get("included", True),
                notes=item.get("notes", "").strip(),
                sort_order=item.get("sort_order", index),
            )
            for index, item in enumerate(items)
        ])

    @staticmethod
    def _replace_branches(plan, branch_ids):
        plan.branch_availabilities.all().delete()
        if not plan.available_all_branches:
            PlanBranchAvailability.objects.bulk_create([
                PlanBranchAvailability(plan=plan, branch_id=branch_id) for branch_id in branch_ids
            ])
