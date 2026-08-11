from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel

from .choices import (
    AssignmentStatus, AuditEvent, CollectionActionStatus, CollectionActionType, CollectionOutcome,
    DayOfWeek, OperationsAuditEvent, PromiseStatus, RouteVisitStatus, SettlementStatus,
    WorkSessionStatus,
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


class CollectorSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="collector_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class SettlementSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="settlement_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class CollectorProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collector_profile"
    )
    employee_code = models.CharField(max_length=20, unique=True, editable=False)
    is_available = models.BooleanField(default=True)
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("user__first_name", "user__last_name", "employee_code")
        indexes = [models.Index(fields=("is_available",), name="collector_available_idx")]

    def __str__(self):
        return f"{self.employee_code} · {self.user.get_full_name().strip() or self.user.username}"


class CollectionZone(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_zones"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collection_zones"
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=1000, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_collection_zones"
    )

    class Meta:
        ordering = ("branch__name", "name")
        constraints = [models.UniqueConstraint(
            fields=("organization", "code"), name="unique_collection_zone_code_per_org"
        )]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="zone_org_active_idx"),
            models.Index(fields=("branch", "is_active"), name="zone_branch_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"


class CustomerCollectionZone(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="customer_zone_links"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="customer_zone_links"
    )
    customer = models.OneToOneField(
        "customers.Customer", on_delete=models.PROTECT, related_name="collection_zone_link"
    )
    zone = models.ForeignKey(
        CollectionZone, on_delete=models.PROTECT, related_name="customer_links"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_customer_zones"
    )

    class Meta:
        indexes = [models.Index(fields=("organization", "zone"), name="cust_zone_org_zone_idx")]


class CollectionAssignment(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_assignments"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collection_assignments"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="collection_assignments"
    )
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="portfolio_assignments"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_portfolios"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    effective_from = models.DateField(default=timezone.localdate)
    effective_until = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.ACTIVE)
    reason = models.CharField(max_length=500, blank=True)
    previous_assignment = models.OneToOneField(
        "self", on_delete=models.PROTECT, related_name="replacement_assignment", blank=True, null=True
    )

    class Meta:
        ordering = ("-assigned_at", "-id")
        constraints = [models.UniqueConstraint(
            fields=("contract",), condition=Q(status=AssignmentStatus.ACTIVE),
            name="unique_active_collection_assignment",
        )]
        indexes = [
            models.Index(fields=("organization", "status"), name="assign_org_status_idx"),
            models.Index(fields=("branch", "status"), name="assign_branch_status_idx"),
            models.Index(fields=("collector", "status"), name="assign_collector_status_idx"),
            models.Index(fields=("contract", "status"), name="assign_contract_status_idx"),
        ]


class CollectionRoute(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_routes"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collection_routes"
    )
    zone = models.ForeignKey(
        CollectionZone, on_delete=models.PROTECT, related_name="routes", blank=True, null=True
    )
    name = models.CharField(max_length=180)
    description = models.CharField(max_length=1000, blank=True)
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collection_routes",
        blank=True, null=True,
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_collection_routes"
    )

    class Meta:
        ordering = ("day_of_week", "name")
        constraints = [models.UniqueConstraint(
            fields=("organization", "branch", "name"), name="unique_collection_route_name"
        )]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="route_org_active_idx"),
            models.Index(fields=("branch", "day_of_week"), name="route_branch_day_idx"),
            models.Index(fields=("collector", "is_active"), name="route_collector_active_idx"),
            models.Index(fields=("zone", "is_active"), name="route_zone_active_idx"),
        ]

    def __str__(self):
        return self.name


class CollectionRouteStop(TimeStampedModel):
    route = models.ForeignKey(CollectionRoute, on_delete=models.PROTECT, related_name="stops")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="collection_route_stops"
    )
    position = models.PositiveIntegerField()
    notes = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("route", "position"), name="unique_route_stop_position"),
            models.UniqueConstraint(
                fields=("customer",), condition=Q(is_active=True, is_primary=True),
                name="unique_active_primary_route_per_customer",
            ),
            models.CheckConstraint(condition=Q(position__gt=0), name="route_stop_position_gt_zero"),
        ]
        indexes = [
            models.Index(fields=("route", "is_active", "position"), name="route_stop_order_idx"),
            models.Index(fields=("customer", "is_active"), name="route_stop_customer_idx"),
        ]


class RouteVisit(TimeStampedModel):
    route = models.ForeignKey(CollectionRoute, on_delete=models.PROTECT, related_name="visits")
    route_stop = models.ForeignKey(CollectionRouteStop, on_delete=models.PROTECT, related_name="visits")
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="route_visits"
    )
    visit_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=RouteVisitStatus.choices, default=RouteVisitStatus.PENDING)
    collection_action = models.OneToOneField(
        CollectionAction, on_delete=models.PROTECT, related_name="route_visit", blank=True, null=True
    )
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("-visit_date", "route_stop__position")
        constraints = [models.UniqueConstraint(
            fields=("route_stop", "collector", "visit_date"), name="unique_route_visit_per_day"
        )]
        indexes = [
            models.Index(fields=("collector", "visit_date"), name="route_visit_collector_idx"),
            models.Index(fields=("route", "visit_date"), name="route_visit_route_idx"),
        ]


class CollectorWorkSession(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collector_work_sessions"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collector_work_sessions"
    )
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collector_work_sessions"
    )
    work_date = models.DateField(default=timezone.localdate)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=WorkSessionStatus.choices, default=WorkSessionStatus.OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_collector_sessions"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="closed_collector_sessions",
        blank=True, null=True,
    )
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("-work_date", "-started_at")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "branch", "collector"), condition=Q(status=WorkSessionStatus.OPEN),
                name="unique_open_collector_work_session",
            ),
            models.UniqueConstraint(
                fields=("organization", "branch", "collector", "work_date"),
                name="unique_collector_session_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "work_date"), name="session_org_date_idx"),
            models.Index(fields=("branch", "work_date"), name="session_branch_date_idx"),
            models.Index(fields=("collector", "status"), name="session_collector_status_idx"),
        ]


class CollectorSettlement(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collector_settlements"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="collector_settlements"
    )
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collector_settlements"
    )
    work_session = models.OneToOneField(
        CollectorWorkSession, on_delete=models.PROTECT, related_name="settlement"
    )
    settlement_number = models.CharField(max_length=20, editable=False)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2)
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2)
    reported_cash = models.DecimalField(max_digits=14, decimal_places=2)
    transfer_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    card_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    check_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=14, decimal_places=2)
    payment_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=SettlementStatus.choices, default=SettlementStatus.SUBMITTED)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_collector_settlements"
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviewed_collector_settlements",
        blank=True, null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    notes = models.CharField(max_length=1000, blank=True)
    review_notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("-submitted_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "settlement_number"), name="unique_settlement_number_per_org"
            ),
            models.CheckConstraint(condition=Q(total_collected__gte=0), name="settlement_total_gte_zero"),
            models.CheckConstraint(condition=Q(expected_cash__gte=0), name="settlement_expected_cash_gte_zero"),
            models.CheckConstraint(condition=Q(reported_cash__gte=0), name="settlement_reported_cash_gte_zero"),
            models.CheckConstraint(condition=Q(transfer_total__gte=0), name="settlement_transfer_gte_zero"),
            models.CheckConstraint(condition=Q(card_total__gte=0), name="settlement_card_gte_zero"),
            models.CheckConstraint(condition=Q(check_total__gte=0), name="settlement_check_gte_zero"),
            models.CheckConstraint(condition=Q(other_total__gte=0), name="settlement_other_gte_zero"),
        ]
        indexes = [
            models.Index(fields=("organization", "status"), name="settlement_org_status_idx"),
            models.Index(fields=("branch", "status"), name="settlement_branch_status_idx"),
            models.Index(fields=("collector", "submitted_at"), name="settlement_collector_idx"),
        ]


class CollectorSettlementPayment(models.Model):
    settlement = models.ForeignKey(CollectorSettlement, on_delete=models.PROTECT, related_name="payment_items")
    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.PROTECT, related_name="collector_settlement_item"
    )
    payment_number_snapshot = models.CharField(max_length=20)
    receipt_number_snapshot = models.CharField(max_length=20)
    customer_name_snapshot = models.CharField(max_length=340)
    contract_number_snapshot = models.CharField(max_length=20)
    payment_method_snapshot = models.CharField(max_length=20)
    amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    included_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("payment__payment_date", "payment_id")
        constraints = [models.CheckConstraint(
            condition=Q(amount_snapshot__gt=0), name="settlement_payment_amount_gt_zero"
        )]
        indexes = [models.Index(fields=("settlement", "payment"), name="settlement_payment_idx")]


class SettlementSubmissionKey(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="settlement_submission_keys"
    )
    key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64)
    settlement = models.ForeignKey(
        CollectorSettlement, on_delete=models.PROTECT, related_name="submission_keys", blank=True, null=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="settlement_submission_keys"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("organization", "key"), name="unique_settlement_submission_key"
        )]


class CollectionOperationsAudit(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="collection_operations_audits"
    )
    event = models.CharField(max_length=40, choices=OperationsAuditEvent.choices)
    description = models.CharField(max_length=1000)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collection_operations_audits"
    )
    assignment = models.ForeignKey(
        CollectionAssignment, on_delete=models.PROTECT, related_name="operations_audits", blank=True, null=True
    )
    route = models.ForeignKey(
        CollectionRoute, on_delete=models.PROTECT, related_name="operations_audits", blank=True, null=True
    )
    work_session = models.ForeignKey(
        CollectorWorkSession, on_delete=models.PROTECT, related_name="operations_audits", blank=True, null=True
    )
    settlement = models.ForeignKey(
        CollectorSettlement, on_delete=models.PROTECT, related_name="operations_audits", blank=True, null=True
    )
    payment = models.ForeignKey(
        "payments.Payment", on_delete=models.PROTECT, related_name="collection_operations_audits",
        blank=True, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("organization", "created_at"), name="operations_audit_org_idx")]
