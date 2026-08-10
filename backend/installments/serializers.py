from rest_framework import serializers

from contracts.choices import PaymentFrequency

from .choices import InstallmentStatus, ScheduleStatus
from .models import Installment, InstallmentSchedule
from .services import build_preview


class ManualInstallmentInputSerializer(serializers.Serializer):
    due_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class ScheduleConditionsSerializer(serializers.Serializer):
    frequency = serializers.ChoiceField(choices=PaymentFrequency.choices)
    installment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    first_due_date = serializers.DateField(required=False, allow_null=True)
    manual_installments = ManualInstallmentInputSerializer(many=True, required=False)

    def validate(self, attrs):
        contract = self.context["contract"]
        preview = build_preview(
            contract, frequency=attrs["frequency"],
            installment_amount=attrs.get("installment_amount"),
            first_due_date=attrs.get("first_due_date"),
            manual_installments=attrs.get("manual_installments"),
        )
        attrs["preview"] = preview
        return attrs


class ReprogramScheduleSerializer(ScheduleConditionsSerializer):
    reason = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)


class GenerateScheduleSerializer(serializers.Serializer):
    manual_installments = ManualInstallmentInputSerializer(many=True, required=False)


class InstallmentSerializer(serializers.ModelSerializer):
    effective_status = serializers.CharField(read_only=True)
    effective_status_label = serializers.SerializerMethodField()
    pending_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.CharField(source="contract.customer.customer_code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    seller_name = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    schedule_version = serializers.IntegerField(source="schedule.version", read_only=True)

    class Meta:
        model = Installment
        fields = (
            "id", "contract", "contract_number", "customer_name", "customer_code", "branch_name",
            "seller_name", "plan_name", "schedule", "schedule_version", "installment_number",
            "due_date", "original_amount", "current_amount", "paid_amount", "pending_amount",
            "status", "effective_status", "effective_status_label", "generated_at", "created_at",
        )

    def get_effective_status_label(self, obj):
        return dict(InstallmentStatus.choices).get(obj.effective_status, obj.effective_status)

    def get_customer_name(self, obj):
        return obj.contract.customer_name_snapshot or obj.contract.customer.full_name

    def get_seller_name(self, obj):
        return obj.contract.seller.get_full_name().strip() or obj.contract.seller.username

    def get_plan_name(self, obj):
        return obj.contract.plan_name_snapshot or obj.contract.plan.name


class ScheduleSummarySerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    frequency_label = serializers.CharField(source="get_frequency_display", read_only=True)
    generated_by = serializers.SerializerMethodField()
    reprogrammed_by = serializers.SerializerMethodField()

    class Meta:
        model = InstallmentSchedule
        fields = (
            "id", "contract", "previous_schedule", "version", "status", "status_label",
            "total_financed", "regular_installment_amount", "frequency", "frequency_label",
            "first_due_date", "last_due_date", "total_installments", "generated_by",
            "generated_at", "reprogramming_reason", "reprogrammed_by", "reprogrammed_at",
            "created_at", "updated_at",
        )

    def _user(self, user):
        if not user:
            return None
        return {"id": user.pk, "name": user.get_full_name().strip() or user.username}

    def get_generated_by(self, obj):
        return self._user(obj.generated_by)

    def get_reprogrammed_by(self, obj):
        return self._user(obj.reprogrammed_by)


def preview_data(preview):
    return {
        "total": str(preview.total),
        "frequency": preview.frequency,
        "frequency_label": dict(PaymentFrequency.choices)[preview.frequency],
        "regular_installment_amount": str(preview.regular_installment_amount),
        "first_due_date": preview.first_due_date,
        "last_due_date": preview.last_due_date,
        "total_installments": preview.total_installments,
        "items": [
            {"installment_number": item.installment_number, "due_date": item.due_date, "amount": str(item.amount)}
            for item in preview.items
        ],
    }
