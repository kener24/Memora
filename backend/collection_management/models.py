from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel

from .choices import (
    AuditEvent, CollectionActionStatus, CollectionActionType, CollectionOutcome, PromiseStatus,
)


class CollectionAction(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_actions"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collection_actions"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="collection_actions"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="collection_actions"
    )
    action_type = models.CharField(max_length=20, choices=CollectionActionType.choices)
    outcome = models.CharField(max_length=20, choices=CollectionOutcome.choices)
    notes = models.CharField(max_length=2000)
    contact_date = models.DateTimeField(default=timezone.now)
    next_follow_up_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=CollectionActionStatus.choices, default=CollectionActionStatus.ACTIVE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_collection_actions"
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voided_collection_actions",
        blank=True, null=True,
    )
    voided_at = models.DateTimeField(blank=True, null=True)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-contact_date", "-id")
        indexes = [
            models.Index(fields=("organization", "contact_date"), name="coll_action_org_date_idx"),
            models.Index(fields=("branch", "contact_date"), name="coll_action_branch_date_idx"),
            models.Index(fields=("customer", "contact_date"), name="coll_action_customer_idx"),
            models.Index(fields=("contract", "contact_date"), name="coll_action_contract_idx"),
            models.Index(fields=("status", "next_follow_up_date"), name="coll_action_follow_idx"),
        ]

    def __str__(self):
        return f"{self.contract.contract_number} · {self.get_action_type_display()}"


class PaymentPromise(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payment_promises"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="payment_promises"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="payment_promises"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="payment_promises"
    )
    collection_action = models.OneToOneField(
        CollectionAction, on_delete=models.PROTECT, related_name="payment_promise", blank=True, null=True
    )
    promised_amount = models.DecimalField(max_digits=12, decimal_places=2)
    promised_date = models.DateField()
    status = models.CharField(max_length=20, choices=PromiseStatus.choices, default=PromiseStatus.PENDING)
    fulfilled_payment = models.ForeignKey(
        "payments.Payment", on_delete=models.PROTECT, related_name="fulfilled_promises", blank=True, null=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_payment_promises"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="resolved_payment_promises",
        blank=True, null=True,
    )
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("status", "promised_date", "id")
        constraints = [
            models.CheckConstraint(condition=Q(promised_amount__gt=0), name="promise_amount_gt_zero"),
            models.UniqueConstraint(
                fields=("contract",), condition=Q(status=PromiseStatus.PENDING),
                name="unique_pending_promise_per_contract",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status", "promised_date"), name="promise_org_status_date_idx"),
            models.Index(fields=("branch", "status", "promised_date"), name="promise_branch_status_idx"),
            models.Index(fields=("customer", "promised_date"), name="promise_customer_date_idx"),
            models.Index(fields=("contract", "status"), name="promise_contract_status_idx"),
        ]

    @property
    def effective_status(self):
        if self.status == PromiseStatus.PENDING and self.promised_date < timezone.localdate():
            return PromiseStatus.BROKEN
        return self.status

    def __str__(self):
        return f"{self.contract.contract_number} · L {self.promised_amount} · {self.promised_date}"


class CollectionAudit(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_audits"
    )
    action = models.ForeignKey(
        CollectionAction, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    promise = models.ForeignKey(
        PaymentPromise, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    event = models.CharField(max_length=30, choices=AuditEvent.choices)
    description = models.CharField(max_length=500)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collection_audits"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(action__isnull=False) | Q(promise__isnull=False), name="collection_audit_has_target"
            )
        ]
        indexes = [models.Index(fields=("organization", "created_at"), name="collection_audit_org_idx")]
