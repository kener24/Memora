from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from accounts.models import CustomUser
from customers.models import Beneficiary, Customer
from organizations.models import Branch, Organization
from plans.models import FuneralPlan

from .access import (
    get_contract_permissions, is_branch_restricted, is_global_contract_user, role_code,
)
from .choices import ContractStatus, PaymentFrequency
from .models import Contract, ContractActivity, ContractPlanItem
from .services import SELLER_ROLE_CODES, calculate_contract_amounts, plan_is_available


def can_view_costs(context):
    request = context.get("request")
    return bool(request and get_contract_permissions(request.user).view_costs)


class ContractPlanItemSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_view_costs(self.context):
            data.pop("estimated_cost_snapshot", None)
        return data

    class Meta:
        model = ContractPlanItem
        fields = (
            "id", "service_code_snapshot", "service_name_snapshot", "service_description_snapshot",
            "category_snapshot", "quantity", "unit_snapshot", "notes_snapshot",
            "estimated_cost_snapshot", "sort_order",
        )


class ContractActivitySerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = ContractActivity
        fields = ("id", "action", "action_label", "description", "user", "created_at")

    def get_user(self, obj):
        if not obj.user:
            return None
        return {"id": obj.user_id, "name": obj.user.get_full_name().strip() or obj.user.username}


class ContractListSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    beneficiary_name = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Contract
        fields = (
            "id", "contract_number", "customer_name", "beneficiary_name", "plan_name", "seller_name",
            "branch_name", "sale_date", "total_price", "allow_financing", "status", "status_label",
            "created_at", "updated_at",
        )

    def get_customer_name(self, obj):
        return obj.customer_name_snapshot or obj.customer.full_name

    def get_beneficiary_name(self, obj):
        if obj.beneficiary_name_snapshot:
            return obj.beneficiary_name_snapshot
        return obj.beneficiary.full_name if obj.beneficiary else obj.customer.full_name

    def get_plan_name(self, obj):
        return obj.plan_name_snapshot or obj.plan.name

    def get_seller_name(self, obj):
        return obj.seller.get_full_name().strip() or obj.seller.username


class ContractDetailSerializer(ContractListSerializer):
    organization = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    beneficiary = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    cancelled_by = serializers.SerializerMethodField()
    payment_frequency_label = serializers.CharField(source="get_payment_frequency_display", read_only=True)
    plan_items = ContractPlanItemSerializer(many=True, read_only=True)
    activities = ContractActivitySerializer(many=True, read_only=True)
    financial_summary = serializers.SerializerMethodField()

    class Meta(ContractListSerializer.Meta):
        fields = ContractListSerializer.Meta.fields + (
            "organization", "branch", "customer", "beneficiary", "plan", "seller", "start_date",
            "plan_name_snapshot", "plan_description_snapshot", "customer_name_snapshot",
            "customer_identity_snapshot", "customer_address_snapshot", "customer_phone_snapshot",
            "beneficiary_name_snapshot", "beneficiary_identity_snapshot", "beneficiary_relationship_snapshot",
            "subtotal", "discount", "initial_payment_agreed", "financed_amount", "payment_frequency",
            "payment_frequency_label", "installment_amount", "first_due_date", "notes", "cancelled_at",
            "cancelled_by", "cancellation_reason", "created_by", "financial_summary", "plan_items", "activities",
        )

    def get_financial_summary(self, obj):
        from payments.services import financial_summary

        return financial_summary(obj)

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_branch(self, obj):
        return {"id": obj.branch_id, "name": obj.branch.name, "code": obj.branch.code}

    def get_customer(self, obj):
        return {"id": obj.customer_id, "code": obj.customer.customer_code, "name": obj.customer.full_name}

    def get_beneficiary(self, obj):
        if not obj.beneficiary:
            return None
        return {"id": obj.beneficiary_id, "name": obj.beneficiary.full_name}

    def get_plan(self, obj):
        return {"id": obj.plan_id, "code": obj.plan.code, "name": obj.plan.name}

    def get_seller(self, obj):
        return {"id": obj.seller_id, "name": obj.seller.get_full_name().strip() or obj.seller.username}

    def get_created_by(self, obj):
        return {"id": obj.created_by_id, "name": obj.created_by.get_full_name().strip() or obj.created_by.username}

    def get_cancelled_by(self, obj):
        if not obj.cancelled_by:
            return None
        return {"id": obj.cancelled_by_id, "name": obj.cancelled_by.get_full_name().strip() or obj.cancelled_by.username}


class ContractDraftSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True), required=False, write_only=True
    )
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True))
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.filter(is_active=True))
    beneficiary = serializers.PrimaryKeyRelatedField(
        queryset=Beneficiary.objects.filter(is_active=True), required=False, allow_null=True
    )
    plan = serializers.PrimaryKeyRelatedField(queryset=FuneralPlan.objects.filter(is_active=True))
    seller = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.filter(is_active=True))
    sale_date = serializers.DateField(required=False, default=timezone.localdate)
    start_date = serializers.DateField(required=False)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=0)
    initial_payment_agreed = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=0
    )
    installment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"), default=0
    )

    class Meta:
        model = Contract
        fields = (
            "organization", "branch", "customer", "beneficiary", "plan", "seller", "sale_date",
            "start_date", "discount", "allow_financing", "initial_payment_agreed",
            "payment_frequency", "installment_amount", "first_due_date", "notes",
        )

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        if self.instance and self.instance.status != ContractStatus.DRAFT:
            raise serializers.ValidationError({"detail": "Un contrato confirmado no puede modificarse."})

        submitted_org = attrs.get("organization")
        if self.instance:
            organization = self.instance.organization
            if submitted_org and submitted_org.pk != organization.pk:
                raise serializers.ValidationError({"organization": "La organización no puede cambiarse."})
            attrs.pop("organization", None)
        elif is_global_contract_user(user):
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

        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        branch = current("branch")
        customer = current("customer")
        beneficiary = current("beneficiary")
        plan = current("plan")
        seller = current("seller")
        if not all((branch, customer, plan, seller)):
            raise serializers.ValidationError({"detail": "Completa cliente, plan, sucursal y vendedor."})
        if branch.organization_id != organization.pk:
            raise serializers.ValidationError({"branch": "La sucursal no pertenece a la organización."})
        if is_branch_restricted(user) and branch.pk != user.branch_id:
            raise serializers.ValidationError({"branch": "Tu usuario solo puede vender en su sucursal."})
        if customer.organization_id != organization.pk:
            raise serializers.ValidationError({"customer": "El cliente no pertenece a la organización."})
        if is_branch_restricted(user) and customer.branch_id != branch.pk:
            raise serializers.ValidationError({"customer": "El cliente no pertenece a tu sucursal."})
        if beneficiary and (beneficiary.customer_id != customer.pk or not beneficiary.is_active):
            raise serializers.ValidationError({"beneficiary": "El beneficiario no pertenece al cliente."})
        if plan.organization_id != organization.pk:
            raise serializers.ValidationError({"plan": "El plan no pertenece a la organización."})
        if not plan_is_available(plan, branch):
            raise serializers.ValidationError({"plan": "Este plan ya no está disponible para nuevas ventas en la sucursal."})
        if seller.organization_id != organization.pk or not seller.role_id or seller.role.code not in SELLER_ROLE_CODES:
            raise serializers.ValidationError({"seller": "Selecciona un vendedor válido de la organización."})
        if role_code(user) == "seller" and seller.pk != user.pk:
            raise serializers.ValidationError({"seller": "El vendedor se determina desde tu sesión."})

        subtotal = plan.base_price
        discount = attrs.get("discount", getattr(self.instance, "discount", Decimal("0.00")))
        permissions = get_contract_permissions(user)
        if discount > 0 and not permissions.apply_discount:
            raise serializers.ValidationError({"discount": "Tu rol no tiene permiso para aplicar descuentos."})
        if discount > subtotal:
            raise serializers.ValidationError({"discount": "El descuento no puede superar el precio del plan."})
        allow_financing = attrs.get(
            "allow_financing", getattr(self.instance, "allow_financing", False)
        )
        initial_payment = attrs.get(
            "initial_payment_agreed", getattr(self.instance, "initial_payment_agreed", Decimal("0.00"))
        )
        total, financed = calculate_contract_amounts(subtotal, discount, allow_financing, initial_payment)
        if allow_financing:
            if not plan.allow_financing:
                raise serializers.ValidationError({"allow_financing": "El plan no admite financiamiento."})
            if initial_payment >= total:
                raise serializers.ValidationError({"initial_payment_agreed": "La prima debe ser menor que el total financiado."})
            frequency = attrs.get("payment_frequency", getattr(self.instance, "payment_frequency", ""))
            installment = attrs.get(
                "installment_amount", getattr(self.instance, "installment_amount", Decimal("0.00"))
            )
            first_due = attrs.get("first_due_date", getattr(self.instance, "first_due_date", None))
            if frequency not in PaymentFrequency.values:
                raise serializers.ValidationError({"payment_frequency": "Selecciona una frecuencia válida."})
            if installment <= 0:
                raise serializers.ValidationError({"installment_amount": "La cuota esperada debe ser mayor que cero."})
            if not first_due:
                raise serializers.ValidationError({"first_due_date": "Selecciona el primer vencimiento."})
            start_date = attrs.get("start_date", getattr(self.instance, "start_date", None)) or attrs.get("sale_date", timezone.localdate())
            if first_due < start_date:
                raise serializers.ValidationError({"first_due_date": "El vencimiento no puede ser anterior al inicio."})
        else:
            attrs["initial_payment_agreed"] = Decimal("0.00")
            attrs["payment_frequency"] = ""
            attrs["installment_amount"] = Decimal("0.00")
            attrs["first_due_date"] = None
            total, financed = calculate_contract_amounts(subtotal, discount, False, 0)

        sale_date = attrs.get("sale_date", getattr(self.instance, "sale_date", timezone.localdate()))
        attrs.setdefault("start_date", getattr(self.instance, "start_date", None) or sale_date)
        attrs["subtotal"] = subtotal
        attrs["total_price"] = total
        attrs["financed_amount"] = financed
        return attrs


class CancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)
