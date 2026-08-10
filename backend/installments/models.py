from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from contracts.choices import PaymentFrequency
from core.models import TimeStampedModel

from .choices import InstallmentStatus, ScheduleStatus


class InstallmentSchedule(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="installment_schedules"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="installment_schedules"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="installment_schedules"
    )
    previous_schedule = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="replacement_schedules", blank=True, null=True
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=ScheduleStatus.choices, default=ScheduleStatus.ACTIVE)
    total_financed = models.DecimalField(max_digits=12, decimal_places=2)
    regular_installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=PaymentFrequency.choices)
    first_due_date = models.DateField()
    last_due_date = models.DateField()
    total_installments = models.PositiveIntegerField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generated_installment_schedules"
    )
    generated_at = models.DateTimeField(default=timezone.now)
    reprogramming_reason = models.TextField(blank=True)
    reprogrammed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reprogrammed_installment_schedules",
        blank=True,
        null=True,
    )
    reprogrammed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "version"), name="unique_schedule_version_per_contract"
            ),
            models.UniqueConstraint(
                fields=("contract",), condition=Q(status=ScheduleStatus.ACTIVE),
                name="unique_active_schedule_per_contract",
            ),
            models.CheckConstraint(condition=Q(version__gt=0), name="schedule_version_gt_zero"),
            models.CheckConstraint(condition=Q(total_financed__gt=0), name="schedule_total_gt_zero"),
            models.CheckConstraint(
                condition=Q(regular_installment_amount__gt=0), name="schedule_regular_amount_gt_zero"
            ),
            models.CheckConstraint(
                condition=Q(total_installments__gt=0), name="schedule_installment_count_gt_zero"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="sch_org_status_idx"),
            models.Index(fields=("contract", "status"), name="sch_contract_status_idx"),
            models.Index(fields=("branch", "status"), name="sch_branch_status_idx"),
        ]

    def __str__(self):
        return f"{self.contract.contract_number} · calendario v{self.version}"


class Installment(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="installments"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="installments"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="installments"
    )
    schedule = models.ForeignKey(
        InstallmentSchedule, on_delete=models.PROTECT, related_name="installments"
    )
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=InstallmentStatus.choices, default=InstallmentStatus.PENDING
    )
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("due_date", "installment_number")
        constraints = [
            models.UniqueConstraint(
                fields=("schedule", "installment_number"), name="unique_installment_number_per_schedule"
            ),
            models.CheckConstraint(condition=Q(installment_number__gt=0), name="installment_number_gt_zero"),
            models.CheckConstraint(condition=Q(original_amount__gt=0), name="installment_original_gt_zero"),
            models.CheckConstraint(condition=Q(current_amount__gte=0), name="installment_current_gte_zero"),
            models.CheckConstraint(condition=Q(paid_amount__gte=0), name="installment_paid_gte_zero"),
            models.CheckConstraint(
                condition=Q(paid_amount__lte=F("current_amount")), name="installment_paid_lte_current"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "due_date"), name="inst_org_due_idx"),
            models.Index(fields=("organization", "status"), name="inst_org_status_idx"),
            models.Index(fields=("branch", "due_date"), name="inst_branch_due_idx"),
            models.Index(fields=("contract", "due_date"), name="inst_contract_due_idx"),
            models.Index(fields=("schedule", "installment_number"), name="inst_schedule_num_idx"),
        ]

    @property
    def pending_amount(self):
        return max(self.current_amount - self.paid_amount, Decimal("0.00"))

    @property
    def effective_status(self):
        from .services import effective_installment_status

        return effective_installment_status(self)

    def __str__(self):
        return f"{self.contract.contract_number} · cuota {self.installment_number}"
