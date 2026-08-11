from decimal import Decimal

from rest_framework import serializers

from payments.models import Payment

from .choices import CollectionActionStatus, CollectionActionType, CollectionOutcome, PromiseStatus
from .models import CollectionAction, CollectionAudit, PaymentPromise


def user_name(user):
    if not user:
        return None
    return user.get_full_name().strip() or user.username


class CollectionAuditSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_display", read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = CollectionAudit
        fields = ("id", "event", "event_label", "description", "actor_name", "created_at")

    def get_actor_name(self, obj):
        return user_name(obj.actor)


class PaymentPromiseSerializer(serializers.ModelSerializer):
    effective_status = serializers.CharField(read_only=True)
    status_label = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    fulfilled_payment_number = serializers.CharField(source="fulfilled_payment.payment_number", read_only=True)
    audits = CollectionAuditSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentPromise
        fields = (
            "id", "customer", "customer_name", "contract", "contract_number", "collection_action",
            "promised_amount", "promised_date", "status", "effective_status", "status_label",
            "fulfilled_payment", "fulfilled_payment_number", "created_by_name", "created_at",
            "resolved_by_name", "resolved_at", "resolution_reason", "audits",
        )
        read_only_fields = fields

    def get_status_label(self, obj):
        return PromiseStatus(obj.effective_status).label

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)

    def get_resolved_by_name(self, obj):
        return user_name(obj.resolved_by)


class CollectionActionSerializer(serializers.ModelSerializer):
    action_type_label = serializers.CharField(source="get_action_type_display", read_only=True)
    outcome_label = serializers.CharField(source="get_outcome_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    voided_by_name = serializers.SerializerMethodField()
    payment_promise = PaymentPromiseSerializer(read_only=True)
    audits = CollectionAuditSerializer(many=True, read_only=True)

    class Meta:
        model = CollectionAction
        fields = (
            "id", "customer", "customer_name", "customer_phone", "contract", "contract_number",
            "action_type", "action_type_label", "outcome", "outcome_label", "notes", "contact_date",
            "next_follow_up_date", "status", "status_label", "created_by_name", "created_at",
            "voided_by_name", "voided_at", "void_reason", "payment_promise", "audits",
        )
        read_only_fields = fields

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)

    def get_voided_by_name(self, obj):
        return user_name(obj.voided_by)


class CollectionActionInputSerializer(serializers.Serializer):
    contract = serializers.IntegerField(min_value=1)
    action_type = serializers.ChoiceField(choices=CollectionActionType.choices)
    outcome = serializers.ChoiceField(choices=CollectionOutcome.choices)
    notes = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)
    contact_date = serializers.DateTimeField(required=False)
    next_follow_up_date = serializers.DateField(required=False, allow_null=True)
    promised_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    promised_date = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs["outcome"] == CollectionOutcome.PROMISE_TO_PAY:
            missing = [field for field in ("promised_amount", "promised_date") if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError({field: "Este dato es obligatorio para una promesa." for field in missing})
        return attrs


class PaymentPromiseInputSerializer(serializers.Serializer):
    contract = serializers.IntegerField(min_value=1)
    promised_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    promised_date = serializers.DateField()


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=500, trim_whitespace=True)


class FulfillPromiseSerializer(serializers.Serializer):
    payment = serializers.PrimaryKeyRelatedField(queryset=Payment.objects.all())
