from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from core.models import TimeStampedModel

from .choices import PaymentMethod, PaymentStatus, PaymentType, ReceiptStatus


class PaymentSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="payment_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class ReceiptSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="receipt_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class Payment(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payments"
    )
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="payments")
    contract = models.ForeignKey("contracts.Contract", on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="payments")
    payment_number = models.CharField(max_length=20, editable=False)
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=120, blank=True)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.CONFIRMED)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_payments"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_payments"
    )
    idempotency_key = models.CharField(max_length=128)
    initial_amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    direct_amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    voided_at = models.DateTimeField(blank=True, null=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voided_payments",
        blank=True, null=True,
    )
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-payment_date", "-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "payment_number"), name="unique_payment_number_per_org"
            ),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"), name="unique_payment_idempotency_per_org"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_gt_zero"),
            models.CheckConstraint(condition=Q(initial_amount_applied__gte=0), name="payment_initial_gte_zero"),
            models.CheckConstraint(condition=Q(direct_amount_applied__gte=0), name="payment_direct_gte_zero"),
            models.CheckConstraint(
                condition=Q(initial_amount_applied__lte=F("amount")), name="payment_initial_lte_amount"
            ),
            models.CheckConstraint(
                condition=Q(direct_amount_applied__lte=F("amount")), name="payment_direct_lte_amount"
            ),
            models.CheckConstraint(
                condition=Q(initial_amount_applied__lte=F("amount") - F("direct_amount_applied")),
                name="payment_components_lte_amount",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "payment_date"), name="pay_org_date_idx"),
            models.Index(fields=("organization", "status"), name="pay_org_status_idx"),
            models.Index(fields=("branch", "payment_date"), name="pay_branch_date_idx"),
            models.Index(fields=("contract", "payment_date"), name="pay_contract_date_idx"),
            models.Index(fields=("customer", "payment_date"), name="pay_customer_date_idx"),
            models.Index(fields=("payment_method",), name="pay_method_idx"),
            models.Index(fields=("received_by", "payment_date"), name="pay_receiver_date_idx"),
            models.Index(fields=("idempotency_key",), name="pay_idempotency_idx"),
        ]

    @property
    def applied_to_installments(self):
        return sum((item.amount_applied for item in self.applications.all()), Decimal("0.00"))

    def __str__(self):
        return f"{self.payment_number} · {self.contract.contract_number}"


class PaymentApplication(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="applications")
    installment = models.ForeignKey(
        "installments.Installment", on_delete=models.PROTECT, related_name="payment_applications"
    )
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("installment__due_date", "installment__installment_number")
        constraints = [
            models.UniqueConstraint(
                fields=("payment", "installment"), name="unique_payment_application_installment"
            ),
            models.CheckConstraint(condition=Q(amount_applied__gt=0), name="payment_application_gt_zero"),
        ]
        indexes = [
            models.Index(fields=("payment",), name="pay_app_payment_idx"),
            models.Index(fields=("installment",), name="pay_app_installment_idx"),
        ]


class Receipt(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="receipts"
    )
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="receipts")
    receipt_number = models.CharField(max_length=20, editable=False)
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="receipt")
    issued_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=ReceiptStatus.choices, default=ReceiptStatus.ISSUED)
    organization_name_snapshot = models.CharField(max_length=180)
    organization_address_snapshot = models.TextField(blank=True)
    organization_phone_snapshot = models.CharField(max_length=30, blank=True)
    customer_name_snapshot = models.CharField(max_length=340)
    customer_code_snapshot = models.CharField(max_length=20)
    customer_identity_snapshot = models.CharField(max_length=30, blank=True)
    contract_number_snapshot = models.CharField(max_length=20)
    concept_snapshot = models.CharField(max_length=160)
    method_snapshot = models.CharField(max_length=80)
    reference_snapshot = models.CharField(max_length=120, blank=True)
    received_by_snapshot = models.CharField(max_length=180)
    amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    applications_snapshot = models.JSONField(default=list)

    class Meta:
        ordering = ("-issued_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "receipt_number"), name="unique_receipt_number_per_org"
            ),
            models.CheckConstraint(condition=Q(amount_snapshot__gt=0), name="receipt_amount_gt_zero"),
            models.CheckConstraint(condition=Q(balance_before__gte=0), name="receipt_balance_before_gte_zero"),
            models.CheckConstraint(condition=Q(balance_after__gte=0), name="receipt_balance_after_gte_zero"),
            models.CheckConstraint(
                condition=Q(balance_after=F("balance_before") - F("amount_snapshot")),
                name="receipt_balance_equation",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "receipt_number"), name="receipt_org_num_idx"),
            models.Index(fields=("branch", "issued_at"), name="receipt_branch_date_idx"),
            models.Index(fields=("status",), name="receipt_status_idx"),
        ]

    def __str__(self):
        return self.receipt_number
