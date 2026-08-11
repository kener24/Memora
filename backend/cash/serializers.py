from decimal import Decimal

from rest_framework import serializers

from collection_management.models import CollectorSettlement
from organizations.models import Branch
from payments.choices import PaymentMethod

from .choices import (
    CashMovementCategory, CashMovementDirection, CashMovementStatus, CashMovementType,
    CashSessionStatus,
)
from .models import (
    CashCount, CashCountDenomination, CashMovement, CashRegister, CashSession,
    CollectorSettlementReception,
)
from .services import CASH_DENOMINATIONS, session_summary, user_name


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return user_name(obj)


class CashRegisterSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    open_session = serializers.SerializerMethodField()

    class Meta:
        model = CashRegister
        fields = (
            "id", "organization", "branch", "branch_name", "code", "name",
            "description", "is_active", "open_session", "created_at", "updated_at",
        )
        read_only_fields = ("organization", "code", "created_at", "updated_at")

    def get_open_session(self, obj):
        session = next((item for item in obj.sessions.all() if item.status == CashSessionStatus.OPEN), None)
        if not session:
            return None
        return {
            "id": session.pk, "session_number": session.session_number,
            "cashier": user_name(session.cashier), "opened_at": session.opened_at,
        }


class CashRegisterInputSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    name = serializers.CharField(max_length=180, trim_whitespace=True)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class CashRegisterUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180, required=False, trim_whitespace=True)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Envía al menos un cambio.")
        return attrs


class CashCountDenominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashCountDenomination
        fields = ("denomination", "quantity", "subtotal")


class CashCountSerializer(serializers.ModelSerializer):
    counted_by_name = serializers.SerializerMethodField()
    denominations = CashCountDenominationSerializer(many=True, read_only=True)

    class Meta:
        model = CashCount
        fields = (
            "id", "cash_session", "expected_cash", "counted_cash", "difference",
            "difference_reason", "counted_by", "counted_by_name", "counted_at", "denominations",
        )

    def get_counted_by_name(self, obj):
        return user_name(obj.counted_by)


class CashSessionSerializer(serializers.ModelSerializer):
    cash_register_code = serializers.CharField(source="cash_register.code", read_only=True)
    cash_register_name = serializers.CharField(source="cash_register.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    cashier_name = serializers.SerializerMethodField()
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    summary = serializers.SerializerMethodField()
    latest_count = serializers.SerializerMethodField()

    class Meta:
        model = CashSession
        fields = (
            "id", "organization", "branch", "branch_name", "cash_register",
            "cash_register_code", "cash_register_name", "cashier", "cashier_name",
            "session_number", "opened_at", "closed_at", "opening_cash", "status",
            "status_label", "opened_by", "opened_by_name", "closed_by", "closed_by_name",
            "notes", "summary", "latest_count", "created_at", "updated_at",
        )

    def get_cashier_name(self, obj):
        return user_name(obj.cashier)

    def get_opened_by_name(self, obj):
        return user_name(obj.opened_by)

    def get_closed_by_name(self, obj):
        return user_name(obj.closed_by) if obj.closed_by_id else ""

    def get_summary(self, obj):
        if obj.status == CashSessionStatus.CLOSED:
            return {
                "opening_cash": obj.opening_cash,
                "cash_in": obj.cash_in_snapshot,
                "cash_out": obj.cash_out_snapshot,
                "expected_cash": obj.expected_cash_snapshot,
                "method_totals": obj.method_totals_snapshot,
                "counted_cash": obj.counted_cash_snapshot,
                "difference": obj.difference_snapshot,
            }
        if self.context.get("include_live_summary") is False:
            return {
                "opening_cash": obj.opening_cash, "cash_in": None, "cash_out": None,
                "expected_cash": None, "method_totals": {}, "counted_cash": None,
                "difference": None,
            }
        data = session_summary(obj)
        data.pop("latest_count", None)
        return data

    def get_latest_count(self, obj):
        rows = list(obj.cash_counts.all())
        if not rows:
            return None
        item = max(rows, key=lambda count: (count.counted_at, count.pk))
        return CashCountSerializer(item).data


class CashSessionOpenSerializer(serializers.Serializer):
    cash_register = serializers.PrimaryKeyRelatedField(queryset=CashRegister.objects.all())
    opening_cash = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class CashSessionCloseSerializer(serializers.Serializer):
    cash_count = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class DenominationInputSerializer(serializers.Serializer):
    denomination = serializers.DecimalField(max_digits=8, decimal_places=2)
    quantity = serializers.IntegerField(min_value=0, max_value=100000)


class CashCountInputSerializer(serializers.Serializer):
    denominations = DenominationInputSerializer(many=True, required=False)
    counted_cash = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    difference_reason = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("denominations") and attrs.get("counted_cash") is None:
            raise serializers.ValidationError("Ingresa denominaciones o el total contado.")
        return attrs


class CashMovementSerializer(serializers.ModelSerializer):
    movement_type_label = serializers.CharField(source="get_movement_type_display", read_only=True)
    direction_label = serializers.CharField(source="get_direction_display", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    cash_register_name = serializers.CharField(source="cash_session.cash_register.name", read_only=True)
    session_number = serializers.CharField(source="cash_session.session_number", read_only=True)
    session_status = serializers.CharField(source="cash_session.status", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()

    class Meta:
        model = CashMovement
        fields = (
            "id", "organization", "branch", "branch_name", "cash_session", "session_number", "session_status",
            "cash_register_name", "movement_number", "movement_type", "movement_type_label",
            "direction", "direction_label", "category", "category_label", "amount",
            "payment_method", "payment_method_label", "affects_cash", "description", "reference",
            "payment", "settlement_reception", "source", "created_by", "created_by_name",
            "status", "status_label", "voided_at", "void_reason", "created_at",
        )

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)

    def get_source(self, obj):
        if obj.payment_id:
            return {"type": "payment", "id": obj.payment_id, "label": obj.payment.payment_number}
        if obj.settlement_reception_id:
            return {
                "type": "collector_settlement", "id": obj.settlement_reception_id,
                "label": obj.settlement_reception.reception_number,
            }
        return {"type": "manual", "id": None, "label": "Movimiento manual"}


class CashMovementInputSerializer(serializers.Serializer):
    cash_session = serializers.PrimaryKeyRelatedField(queryset=CashSession.objects.all())
    direction = serializers.ChoiceField(choices=CashMovementDirection.choices)
    category = serializers.ChoiceField(choices=CashMovementCategory.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    reference = serializers.CharField(max_length=160, required=False, allow_blank=True)


class VoidMovementSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=2000, trim_whitespace=True)


class SettlementReceptionSerializer(serializers.ModelSerializer):
    collector_name = serializers.SerializerMethodField()
    settlement_number = serializers.CharField(source="collector_settlement.settlement_number", read_only=True)
    work_date = serializers.DateField(source="collector_settlement.work_session.work_date", read_only=True)
    received_by_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    session_number = serializers.CharField(source="cash_session.session_number", read_only=True)
    movement_number = serializers.SerializerMethodField()

    class Meta:
        model = CollectorSettlementReception
        fields = (
            "id", "organization", "branch", "branch_name", "cash_session", "session_number",
            "collector_settlement", "settlement_number", "work_date", "collector_name",
            "reception_number", "expected_cash", "reported_cash_by_collector",
            "cash_received_by_cashier", "collector_difference", "delivery_difference",
            "total_difference_vs_expected", "transfer_total", "card_total", "check_total",
            "other_total", "received_by", "received_by_name", "received_at", "notes",
            "status", "movement_number",
        )

    def get_collector_name(self, obj):
        return user_name(obj.collector_settlement.collector)

    def get_received_by_name(self, obj):
        return user_name(obj.received_by)

    def get_movement_number(self, obj):
        movement = getattr(obj, "cash_movement", None)
        return movement.movement_number if movement else ""


class SettlementReceptionInputSerializer(serializers.Serializer):
    cash_session = serializers.PrimaryKeyRelatedField(queryset=CashSession.objects.all())
    collector_settlement = serializers.PrimaryKeyRelatedField(queryset=CollectorSettlement.objects.all())
    cash_received_by_cashier = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class PendingSettlementSerializer(serializers.ModelSerializer):
    collector_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    work_date = serializers.DateField(source="work_session.work_date", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CollectorSettlement
        fields = (
            "id", "settlement_number", "collector", "collector_name", "branch", "branch_name",
            "work_session", "work_date", "total_collected", "expected_cash", "reported_cash",
            "difference", "transfer_total", "card_total", "check_total", "other_total",
            "status", "status_label", "submitted_at", "notes", "review_notes",
        )

    def get_collector_name(self, obj):
        return user_name(obj.collector)


def cash_options_payload(permissions, branches, registers):
    return {
        "permissions": permissions.as_dict(),
        "branches": [{"id": item.pk, "name": item.name, "code": item.code} for item in branches],
        "registers": CashRegisterSerializer(registers, many=True).data,
        "session_statuses": [{"value": value, "label": label} for value, label in CashSessionStatus.choices],
        "movement_statuses": [{"value": value, "label": label} for value, label in CashMovementStatus.choices],
        "movement_types": [{"value": value, "label": label} for value, label in CashMovementType.choices],
        "directions": [{"value": value, "label": label} for value, label in CashMovementDirection.choices],
        "categories": [{"value": value, "label": label} for value, label in CashMovementCategory.choices],
        "payment_methods": [{"value": value, "label": label} for value, label in PaymentMethod.choices],
        "denominations": [str(value) for value in reversed(CASH_DENOMINATIONS)],
    }
