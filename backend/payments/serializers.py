from rest_framework import serializers

from contracts.models import Contract

from .choices import PaymentMethod, PaymentStatus, PaymentType, ReceiptStatus
from .models import Payment, PaymentApplication, Receipt
from .services import financial_summary


class PaymentInputSerializer(serializers.Serializer):
    contract = serializers.PrimaryKeyRelatedField(queryset=Contract.objects.all(), required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_type = serializers.ChoiceField(choices=PaymentType.choices)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    payment_date = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if attrs["payment_method"] in {
            PaymentMethod.TRANSFER, PaymentMethod.CARD, PaymentMethod.CHECK,
        } and not attrs.get("reference", "").strip():
            raise serializers.ValidationError({"reference": "La referencia es obligatoria para este método."})
        return attrs


class PaymentPreviewSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_type = serializers.ChoiceField(choices=PaymentType.choices)


class SettlementSerializer(serializers.Serializer):
    expected_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    payment_date = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if attrs["payment_method"] in {
            PaymentMethod.TRANSFER, PaymentMethod.CARD, PaymentMethod.CHECK,
        } and not attrs.get("reference", "").strip():
            raise serializers.ValidationError({"reference": "La referencia es obligatoria para este método."})
        return attrs


class VoidPaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)


class PaymentApplicationSerializer(serializers.ModelSerializer):
    installment_number = serializers.IntegerField(source="installment.installment_number", read_only=True)
    due_date = serializers.DateField(source="installment.due_date", read_only=True)
    schedule_version = serializers.IntegerField(source="installment.schedule.version", read_only=True)

    class Meta:
        model = PaymentApplication
        fields = ("id", "installment", "installment_number", "schedule_version", "due_date", "amount_applied", "created_at")


class ReceiptSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Receipt
        fields = (
            "id", "receipt_number", "payment", "issued_at", "status", "status_label",
            "organization_name_snapshot", "organization_address_snapshot", "organization_phone_snapshot",
            "customer_name_snapshot", "customer_code_snapshot", "customer_identity_snapshot",
            "contract_number_snapshot", "concept_snapshot", "method_snapshot", "reference_snapshot",
            "received_by_snapshot", "amount_snapshot", "balance_before", "balance_after",
            "applications_snapshot", "created_at", "updated_at",
        )


class PaymentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_type_label = serializers.CharField(source="get_payment_type_display", read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.CharField(source="customer.customer_code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    received_by = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    voided_by = serializers.SerializerMethodField()
    receipt = ReceiptSerializer(read_only=True)
    applications = PaymentApplicationSerializer(many=True, read_only=True)
    financial_summary = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id", "organization", "branch", "branch_name", "contract", "contract_number",
            "customer", "customer_name", "customer_code", "payment_number", "payment_date", "amount",
            "payment_method", "payment_method_label", "reference", "payment_type", "payment_type_label",
            "status", "status_label", "notes", "received_by", "created_by", "idempotency_key",
            "initial_amount_applied", "direct_amount_applied", "voided_at", "voided_by", "void_reason",
            "receipt", "applications", "financial_summary", "created_at", "updated_at",
        )

    def _user(self, user):
        if not user:
            return None
        return {"id": user.pk, "name": user.get_full_name().strip() or user.username}

    def get_customer_name(self, obj):
        return obj.contract.customer_name_snapshot or obj.customer.full_name

    def get_received_by(self, obj):
        return self._user(obj.received_by)

    def get_created_by(self, obj):
        return self._user(obj.created_by)

    def get_voided_by(self, obj):
        return self._user(obj.voided_by)

    def get_financial_summary(self, obj):
        if self.context.get("include_financial_summary") is False:
            return None
        return financial_summary(obj.contract)
