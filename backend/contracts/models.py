from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.models import TimeStampedModel

from .choices import ContractActivityAction, ContractStatus, IdempotencyOperation, PaymentFrequency


class ContractSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="contract_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class Contract(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="contracts"
    )
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="contracts")
    contract_number = models.CharField(max_length=20, editable=False)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="contracts")
    beneficiary = models.ForeignKey(
        "customers.Beneficiary", on_delete=models.PROTECT, related_name="contracts", blank=True, null=True
    )
    plan = models.ForeignKey("plans.FuneralPlan", on_delete=models.PROTECT, related_name="contracts")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sold_contracts"
    )
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    sale_date = models.DateField()
    start_date = models.DateField()

    plan_name_snapshot = models.CharField(max_length=160, blank=True)
    plan_description_snapshot = models.TextField(blank=True)
    customer_name_snapshot = models.CharField(max_length=340, blank=True)
    customer_identity_snapshot = models.CharField(max_length=30, blank=True)
    customer_address_snapshot = models.TextField(blank=True)
    customer_phone_snapshot = models.CharField(max_length=25, blank=True)
    beneficiary_name_snapshot = models.CharField(max_length=340, blank=True)
    beneficiary_identity_snapshot = models.CharField(max_length=30, blank=True)
    beneficiary_relationship_snapshot = models.CharField(max_length=80, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    initial_payment_agreed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    financed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allow_financing = models.BooleanField(default=False)
    payment_frequency = models.CharField(max_length=20, choices=PaymentFrequency.choices, blank=True)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    first_due_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_contracts",
        blank=True,
        null=True,
    )
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_contracts"
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "contract_number"), name="unique_contract_number_per_org"
            ),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="contract_subtotal_gte_zero"),
            models.CheckConstraint(condition=Q(discount__gte=0), name="contract_discount_gte_zero"),
            models.CheckConstraint(condition=Q(discount__lte=F("subtotal")), name="contract_discount_lte_subtotal"),
            models.CheckConstraint(condition=Q(total_price__gte=0), name="contract_total_gte_zero"),
            models.CheckConstraint(
                condition=Q(initial_payment_agreed__gte=0), name="contract_initial_payment_gte_zero"
            ),
            models.CheckConstraint(
                condition=Q(initial_payment_agreed__lte=F("total_price")),
                name="contract_initial_payment_lte_total",
            ),
            models.CheckConstraint(condition=Q(financed_amount__gte=0), name="contract_financed_gte_zero"),
            models.CheckConstraint(
                condition=Q(allow_financing=True) | Q(financed_amount=0), name="contract_cash_financed_zero"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="ctr_org_status_idx"),
            models.Index(fields=("branch", "sale_date"), name="ctr_branch_sale_idx"),
            models.Index(fields=("customer", "created_at"), name="ctr_customer_idx"),
            models.Index(fields=("plan",), name="ctr_plan_idx"),
            models.Index(fields=("seller", "sale_date"), name="ctr_seller_sale_idx"),
            models.Index(fields=("created_at",), name="ctr_created_idx"),
        ]

    def __str__(self):
        return f"{self.contract_number} · {self.customer_name_snapshot or self.customer.full_name}"


class ContractPlanItem(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="plan_items")
    original_plan_item = models.ForeignKey(
        "plans.FuneralPlanItem", on_delete=models.SET_NULL, blank=True, null=True, related_name="contract_snapshots"
    )
    service = models.ForeignKey(
        "plans.FuneralServiceItem", on_delete=models.SET_NULL, blank=True, null=True,
        related_name="contract_snapshots",
    )
    service_code_snapshot = models.CharField(max_length=30)
    service_name_snapshot = models.CharField(max_length=160)
    service_description_snapshot = models.TextField(blank=True)
    category_snapshot = models.CharField(max_length=80)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_snapshot = models.CharField(max_length=80)
    notes_snapshot = models.CharField(max_length=240, blank=True)
    estimated_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="contract_item_quantity_gt_zero"),
            models.CheckConstraint(
                condition=Q(estimated_cost_snapshot__gte=0), name="contract_item_cost_gte_zero"
            ),
        ]
        indexes = [models.Index(fields=("contract", "sort_order"), name="ctr_item_order_idx")]


class ContractActivity(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="activities")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="contract_activities",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=40, choices=ContractActivityAction.choices)
    description = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("contract", "created_at"), name="ctr_activity_idx")]


class ContractIdempotencyKey(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="contract_idempotency_keys"
    )
    key = models.CharField(max_length=128)
    operation = models.CharField(max_length=20, choices=IdempotencyOperation.choices)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="idempotency_keys")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="idempotency_records",
    )
    payload_hash = models.CharField(max_length=64, blank=True)
    resource_type = models.CharField(max_length=30, default="contract")
    resource_id = models.PositiveBigIntegerField(blank=True, null=True)
    response_status = models.PositiveSmallIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "key", "operation"), name="unique_contract_idempotency_operation"
            )
        ]
        indexes = [models.Index(fields=("organization", "key"), name="ctr_idempotency_idx")]
