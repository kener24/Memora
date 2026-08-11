from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from core.models import TimeStampedModel
from payments.choices import PaymentMethod

from .choices import (
    CashAuditEvent, CashIdempotencyOperation, CashMovementCategory, CashMovementDirection,
    CashMovementStatus, CashMovementType, CashReceptionStatus, CashSessionStatus,
)


class CashSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="cash_sequence"
    )
    next_register = models.PositiveBigIntegerField(default=1)
    next_session = models.PositiveBigIntegerField(default=1)
    next_movement = models.PositiveBigIntegerField(default=1)
    next_reception = models.PositiveBigIntegerField(default=1)


class CashRegister(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cash_registers"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="cash_registers"
    )
    code = models.CharField(max_length=20, editable=False)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_cash_registers"
    )

    class Meta:
        ordering = ("branch__name", "name", "id")
        constraints = [models.UniqueConstraint(
            fields=("organization", "code"), name="unique_cash_register_code_org"
        )]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="cash_reg_org_active_idx"),
            models.Index(fields=("branch", "is_active"), name="cash_reg_branch_active_idx"),
        ]

    def clean(self):
        super().clean()
        if self.branch_id and self.organization_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "La sucursal debe pertenecer a la organización de la caja."})

    def __str__(self):
        return f"{self.code} · {self.name}"


class CashSession(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cash_sessions"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="cash_sessions"
    )
    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.PROTECT, related_name="sessions"
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_sessions"
    )
    session_number = models.CharField(max_length=20, editable=False)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(blank=True, null=True)
    opening_cash = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=CashSessionStatus.choices, default=CashSessionStatus.OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_cash_sessions"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="closed_cash_sessions",
        blank=True, null=True,
    )
    notes = models.TextField(blank=True)
    cash_in_snapshot = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    cash_out_snapshot = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    expected_cash_snapshot = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    counted_cash_snapshot = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    difference_snapshot = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    method_totals_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-opened_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "session_number"), name="unique_cash_session_number_org"
            ),
            models.UniqueConstraint(
                fields=("cash_register",), condition=Q(status=CashSessionStatus.OPEN),
                name="unique_open_session_register",
            ),
            models.UniqueConstraint(
                fields=("branch", "cashier"), condition=Q(status=CashSessionStatus.OPEN),
                name="unique_open_session_cashier",
            ),
            models.CheckConstraint(condition=Q(opening_cash__gte=0), name="cash_session_opening_gte_zero"),
        ]
        indexes = [
            models.Index(fields=("organization", "status", "opened_at"), name="cash_session_org_status_idx"),
            models.Index(fields=("branch", "status", "opened_at"), name="cash_session_branch_idx"),
            models.Index(fields=("cash_register", "status"), name="cash_session_register_idx"),
            models.Index(fields=("cashier", "status"), name="cash_session_cashier_idx"),
        ]

    def clean(self):
        super().clean()
        if self.cash_register_id:
            if self.cash_register.organization_id != self.organization_id:
                raise ValidationError({"cash_register": "La caja pertenece a otra organización."})
            if self.cash_register.branch_id != self.branch_id:
                raise ValidationError({"cash_register": "La caja pertenece a otra sucursal."})
        if self.cashier_id and self.organization_id and self.cashier.organization_id != self.organization_id:
            raise ValidationError({"cashier": "El cajero pertenece a otra organización."})

    def __str__(self):
        return f"{self.session_number} · {self.cash_register.name}"


class CollectorSettlementReception(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="settlement_receptions"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="settlement_receptions"
    )
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="settlement_receptions"
    )
    collector_settlement = models.OneToOneField(
        "collection_management.CollectorSettlement", on_delete=models.PROTECT,
        related_name="cash_reception",
    )
    reception_number = models.CharField(max_length=20, editable=False)
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2)
    reported_cash_by_collector = models.DecimalField(max_digits=14, decimal_places=2)
    cash_received_by_cashier = models.DecimalField(max_digits=14, decimal_places=2)
    collector_difference = models.DecimalField(max_digits=14, decimal_places=2)
    delivery_difference = models.DecimalField(max_digits=14, decimal_places=2)
    total_difference_vs_expected = models.DecimalField(max_digits=14, decimal_places=2)
    transfer_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    card_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    check_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_collector_settlements"
    )
    received_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=CashReceptionStatus.choices, default=CashReceptionStatus.CONFIRMED
    )

    class Meta:
        ordering = ("-received_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reception_number"), name="unique_reception_number_org"
            ),
            models.CheckConstraint(condition=Q(expected_cash__gte=0), name="reception_expected_gte_zero"),
            models.CheckConstraint(
                condition=Q(reported_cash_by_collector__gte=0), name="reception_reported_gte_zero"
            ),
            models.CheckConstraint(
                condition=Q(cash_received_by_cashier__gte=0), name="reception_received_gte_zero"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "received_at"), name="reception_org_date_idx"),
            models.Index(fields=("branch", "received_at"), name="reception_branch_date_idx"),
            models.Index(fields=("cash_session", "status"), name="reception_session_idx"),
        ]


class CashMovement(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cash_movements"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="cash_movements"
    )
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="movements"
    )
    movement_number = models.CharField(max_length=20, editable=False)
    movement_type = models.CharField(max_length=30, choices=CashMovementType.choices)
    direction = models.CharField(max_length=10, choices=CashMovementDirection.choices)
    category = models.CharField(max_length=40, choices=CashMovementCategory.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    affects_cash = models.BooleanField(default=True, editable=False)
    description = models.TextField()
    reference = models.CharField(max_length=160, blank=True)
    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.PROTECT, related_name="cash_movement", blank=True, null=True
    )
    settlement_reception = models.OneToOneField(
        CollectorSettlementReception, on_delete=models.PROTECT, related_name="cash_movement",
        blank=True, null=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_cash_movements"
    )
    status = models.CharField(
        max_length=20, choices=CashMovementStatus.choices, default=CashMovementStatus.CONFIRMED
    )
    voided_at = models.DateTimeField(blank=True, null=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voided_cash_movements",
        blank=True, null=True,
    )
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "movement_number"), name="unique_cash_movement_number_org"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="cash_movement_amount_gt_zero"),
        ]
        indexes = [
            models.Index(fields=("organization", "created_at"), name="cash_move_org_date_idx"),
            models.Index(fields=("branch", "created_at"), name="cash_move_branch_date_idx"),
            models.Index(fields=("cash_session", "status"), name="cash_move_session_idx"),
            models.Index(fields=("movement_type", "direction"), name="cash_move_type_dir_idx"),
            models.Index(fields=("payment_method", "status"), name="cash_move_method_idx"),
            models.Index(fields=("payment",), name="cash_move_payment_idx"),
        ]

    def clean(self):
        super().clean()
        if self.cash_session_id:
            if self.cash_session.organization_id != self.organization_id:
                raise ValidationError({"cash_session": "La sesión pertenece a otra organización."})
            if self.cash_session.branch_id != self.branch_id:
                raise ValidationError({"cash_session": "La sesión pertenece a otra sucursal."})
        if self.payment_id and self.payment.organization_id != self.organization_id:
            raise ValidationError({"payment": "El pago pertenece a otra organización."})

    def __str__(self):
        return f"{self.movement_number} · {self.get_direction_display()} L {self.amount}"


class CashCount(TimeStampedModel):
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="cash_counts"
    )
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2)
    counted_cash = models.DecimalField(max_digits=14, decimal_places=2)
    difference = models.DecimalField(max_digits=14, decimal_places=2)
    difference_reason = models.TextField(blank=True)
    movement_fingerprint = models.CharField(max_length=64)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_counts"
    )
    counted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-counted_at", "-id")
        constraints = [
            models.CheckConstraint(condition=Q(expected_cash__gte=0), name="cash_count_expected_gte_zero"),
            models.CheckConstraint(condition=Q(counted_cash__gte=0), name="cash_count_counted_gte_zero"),
        ]
        indexes = [models.Index(fields=("counted_at",), name="cash_count_date_idx")]


class CashCountDenomination(models.Model):
    cash_count = models.ForeignKey(CashCount, on_delete=models.PROTECT, related_name="denominations")
    denomination = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("-denomination",)
        constraints = [
            models.UniqueConstraint(
                fields=("cash_count", "denomination"), name="unique_cash_count_denomination"
            ),
            models.CheckConstraint(condition=Q(denomination__gt=0), name="cash_denomination_gt_zero"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="cash_denomination_subtotal_gte"),
            models.CheckConstraint(
                condition=Q(subtotal=F("denomination") * F("quantity")),
                name="cash_denomination_equation",
            ),
        ]


class CashIdempotencyKey(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cash_idempotency_keys"
    )
    key = models.CharField(max_length=128)
    operation = models.CharField(max_length=40, choices=CashIdempotencyOperation.choices)
    payload_hash = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=40)
    resource_id = models.PositiveBigIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_idempotency_keys"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("organization", "key"), name="unique_cash_idempotency_org"
        )]
        indexes = [models.Index(fields=("organization", "created_at"), name="cash_idem_org_date_idx")]


class CashAudit(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cash_audits"
    )
    event = models.CharField(max_length=40, choices=CashAuditEvent.choices)
    description = models.CharField(max_length=1000)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_audits"
    )
    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    cash_movement = models.ForeignKey(
        CashMovement, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    settlement_reception = models.ForeignKey(
        CollectorSettlementReception, on_delete=models.PROTECT, related_name="audits",
        blank=True, null=True,
    )
    cash_count = models.ForeignKey(
        CashCount, on_delete=models.PROTECT, related_name="audits", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("organization", "created_at"), name="cash_audit_org_date_idx")]
