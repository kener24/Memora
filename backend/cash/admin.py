from django.contrib import admin

from .models import (
    CashAudit, CashCount, CashCountDenomination, CashIdempotencyKey, CashMovement,
    CashRegister, CashSequence, CashSession, CollectorSettlementReception,
)


class CashCountDenominationInline(admin.TabularInline):
    model = CashCountDenomination
    extra = 0
    readonly_fields = ("denomination", "quantity", "subtotal")


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "branch", "is_active")
    list_filter = ("organization", "branch", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("code", "created_by", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = ("session_number", "cash_register", "cashier", "opened_at", "closed_at", "status")
    list_filter = ("organization", "branch", "status")
    search_fields = ("session_number", "cash_register__code", "cashier__username")
    readonly_fields = (
        "session_number", "opened_at", "closed_at", "opening_cash", "status",
        "cash_in_snapshot", "cash_out_snapshot", "expected_cash_snapshot",
        "counted_cash_snapshot", "difference_snapshot", "method_totals_snapshot",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_number", "cash_session", "movement_type", "direction", "amount",
        "payment_method", "status", "created_at",
    )
    list_filter = ("organization", "branch", "movement_type", "direction", "payment_method", "status")
    search_fields = ("movement_number", "description", "reference", "payment__payment_number")
    readonly_fields = [field.name for field in CashMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CollectorSettlementReception)
class SettlementReceptionAdmin(admin.ModelAdmin):
    list_display = (
        "reception_number", "collector_settlement", "cash_session",
        "cash_received_by_cashier", "total_difference_vs_expected", "received_at",
    )
    list_filter = ("organization", "branch", "status")
    search_fields = ("reception_number", "collector_settlement__settlement_number")
    readonly_fields = [field.name for field in CollectorSettlementReception._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashCount)
class CashCountAdmin(admin.ModelAdmin):
    list_display = ("cash_session", "expected_cash", "counted_cash", "difference", "counted_at")
    readonly_fields = [field.name for field in CashCount._meta.fields]
    inlines = (CashCountDenominationInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashAudit)
class CashAuditAdmin(admin.ModelAdmin):
    list_display = ("event", "organization", "actor", "created_at")
    list_filter = ("organization", "event")
    readonly_fields = [field.name for field in CashAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashSequence)
class CashSequenceAdmin(admin.ModelAdmin):
    list_display = ("organization", "next_register", "next_session", "next_movement", "next_reception")
    readonly_fields = [field.name for field in CashSequence._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashIdempotencyKey)
class CashIdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("organization", "operation", "key", "created_by", "created_at")
    search_fields = ("operation", "key", "resource_type", "resource_id")
    readonly_fields = [field.name for field in CashIdempotencyKey._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
