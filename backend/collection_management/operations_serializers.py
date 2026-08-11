from decimal import Decimal

from rest_framework import serializers

from .choices import DayOfWeek, RouteVisitStatus
from .models import (
    CollectionAssignment, CollectionOperationsAudit, CollectionRoute, CollectionRouteStop,
    CollectionZone, CollectorSettlement, CollectorSettlementPayment, CollectorWorkSession,
    CustomerCollectionZone, RouteVisit,
)
from .operations import user_name, work_session_summary


class AssignmentSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    customer_name = serializers.CharField(source="contract.customer_name_snapshot", read_only=True)
    collector_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CollectionAssignment
        fields = (
            "id", "organization", "branch", "contract", "contract_number", "customer_name",
            "collector", "collector_name", "assigned_by_name", "assigned_at", "effective_from",
            "effective_until", "status", "status_label", "reason", "previous_assignment", "created_at",
        )
        read_only_fields = fields

    def get_collector_name(self, obj):
        return user_name(obj.collector)

    def get_assigned_by_name(self, obj):
        return user_name(obj.assigned_by)


class ZoneSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CollectionZone
        fields = (
            "id", "organization", "branch", "branch_name", "code", "name", "description",
            "is_active", "customer_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization", "branch_name", "customer_count", "created_at", "updated_at")


class CustomerZoneSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model = CustomerCollectionZone
        fields = ("id", "customer", "customer_name", "zone", "zone_name", "created_at", "updated_at")
        read_only_fields = fields


class RouteVisitSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RouteVisit
        fields = ("id", "visit_date", "status", "status_label", "notes", "collection_action", "created_at")
        read_only_fields = fields


class RouteStopSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_address = serializers.CharField(source="customer.address", read_only=True)
    today_visit = serializers.SerializerMethodField()

    class Meta:
        model = CollectionRouteStop
        fields = (
            "id", "customer", "customer_name", "customer_phone", "customer_address", "position",
            "notes", "is_active", "is_primary", "today_visit", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_today_visit(self, obj):
        visits = getattr(obj, "today_visits", None)
        visit = visits[0] if visits else None
        return RouteVisitSerializer(visit).data if visit else None


class RouteSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    collector_name = serializers.SerializerMethodField()
    day_of_week_label = serializers.CharField(source="get_day_of_week_display", read_only=True)
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = CollectionRoute
        fields = (
            "id", "organization", "branch", "branch_name", "zone", "zone_name", "name", "description",
            "collector", "collector_name", "day_of_week", "day_of_week_label", "is_active", "stops",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization", "branch_name", "zone_name", "collector_name", "day_of_week_label", "stops", "created_at", "updated_at")

    def get_collector_name(self, obj):
        return user_name(obj.collector) if obj.collector else None


class WorkSessionSerializer(serializers.ModelSerializer):
    collector_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = CollectorWorkSession
        fields = (
            "id", "organization", "branch", "collector", "collector_name", "work_date", "started_at",
            "ended_at", "status", "status_label", "opened_by_name", "closed_by_name", "notes", "summary",
        )
        read_only_fields = fields

    def get_collector_name(self, obj):
        return user_name(obj.collector)

    def get_opened_by_name(self, obj):
        return user_name(obj.opened_by)

    def get_closed_by_name(self, obj):
        return user_name(obj.closed_by) if obj.closed_by else None

    def get_summary(self, obj):
        if not self.context.get("include_summary", True):
            return None
        return work_session_summary(obj)


class SettlementPaymentSerializer(serializers.ModelSerializer):
    payment_date = serializers.DateTimeField(source="payment.payment_date", read_only=True)
    payment_method_label = serializers.CharField(source="payment.get_payment_method_display", read_only=True)

    class Meta:
        model = CollectorSettlementPayment
        fields = (
            "id", "payment", "payment_number_snapshot", "receipt_number_snapshot", "customer_name_snapshot",
            "contract_number_snapshot", "payment_method_snapshot", "payment_method_label", "amount_snapshot",
            "payment_date", "included_at",
        )
        read_only_fields = fields


class OperationsAuditSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_display", read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = CollectionOperationsAudit
        fields = ("id", "event", "event_label", "description", "actor_name", "created_at")
        read_only_fields = fields

    def get_actor_name(self, obj):
        return user_name(obj.actor)


class SettlementSerializer(serializers.ModelSerializer):
    collector_name = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    payments = SettlementPaymentSerializer(source="payment_items", many=True, read_only=True)
    audits = OperationsAuditSerializer(source="operations_audits", many=True, read_only=True)

    class Meta:
        model = CollectorSettlement
        fields = (
            "id", "settlement_number", "organization", "branch", "branch_name", "collector",
            "collector_name", "work_session", "total_collected", "expected_cash", "reported_cash",
            "transfer_total", "card_total", "check_total", "other_total", "difference", "status",
            "status_label", "submitted_by_name", "submitted_at", "reviewed_by_name", "reviewed_at",
            "notes", "review_notes", "payments", "audits", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_collector_name(self, obj):
        return user_name(obj.collector)

    def get_submitted_by_name(self, obj):
        return user_name(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return user_name(obj.reviewed_by) if obj.reviewed_by else None


class AssignmentInputSerializer(serializers.Serializer):
    contract = serializers.IntegerField(min_value=1)
    collector = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BulkAssignmentInputSerializer(serializers.Serializer):
    contracts = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=500)
    collector = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReassignmentInputSerializer(serializers.Serializer):
    collector = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(min_length=5, max_length=500)


class ZoneInputSerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1)
    code = serializers.CharField(max_length=30)
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class CustomerZoneInputSerializer(serializers.Serializer):
    customer = serializers.IntegerField(min_value=1)
    zone = serializers.IntegerField(min_value=1, allow_null=True, required=False)


class RouteInputSerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1)
    zone = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    collector = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    day_of_week = serializers.ChoiceField(choices=DayOfWeek.choices, allow_null=True, required=False)
    name = serializers.CharField(max_length=180)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class RouteStopInputSerializer(serializers.Serializer):
    customer = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RouteReorderSerializer(serializers.Serializer):
    stops = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=500)


class RouteVisitInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RouteVisitStatus.choices)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class NotesSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class SettlementPreviewInputSerializer(serializers.Serializer):
    work_session = serializers.IntegerField(min_value=1, required=False)


class SettlementSubmitInputSerializer(serializers.Serializer):
    work_session = serializers.IntegerField(min_value=1)
    reported_cash = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"))
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    payment_fingerprint = serializers.CharField(min_length=64, max_length=64)


class SettlementDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
