from django.contrib import admin

from .models import (
    CollectionAction, CollectionAssignment, CollectionAudit, CollectionOperationsAudit,
    CollectionRoute, CollectionRouteStop, CollectionZone, CollectorProfile, CollectorSettlement,
    CollectorSettlementPayment, CollectorWorkSession, CustomerCollectionZone, PaymentPromise,
    RouteVisit,
)


@admin.register(CollectionAction)
class CollectionActionAdmin(admin.ModelAdmin):
    list_display = ("contract", "action_type", "outcome", "contact_date", "status", "created_by")
    list_filter = ("status", "action_type", "outcome", "organization", "branch")
    search_fields = ("contract__contract_number", "customer__first_name", "customer__last_name", "notes")
    readonly_fields = tuple(field.name for field in CollectionAction._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(PaymentPromise)
class PaymentPromiseAdmin(admin.ModelAdmin):
    list_display = ("contract", "promised_amount", "promised_date", "status", "created_by")
    list_filter = ("status", "organization", "branch")
    readonly_fields = tuple(field.name for field in PaymentPromise._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(CollectionAudit)
class CollectionAuditAdmin(admin.ModelAdmin):
    list_display = ("event", "organization", "actor", "created_at")
    readonly_fields = tuple(field.name for field in CollectionAudit._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(CollectorProfile)
class CollectorProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "is_available", "created_at")
    list_filter = ("is_available", "user__organization", "user__branch")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
    readonly_fields = ("employee_code", "created_at", "updated_at")


@admin.register(CollectionAssignment)
class CollectionAssignmentAdmin(admin.ModelAdmin):
    list_display = ("contract", "collector", "branch", "status", "assigned_at", "effective_until")
    list_filter = ("status", "organization", "branch", "collector")
    search_fields = ("contract__contract_number", "collector__username", "reason")
    readonly_fields = tuple(field.name for field in CollectionAssignment._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(CollectionZone)
class CollectionZoneAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "branch", "is_active")
    list_filter = ("is_active", "organization", "branch")
    search_fields = ("code", "name")


@admin.register(CustomerCollectionZone)
class CustomerCollectionZoneAdmin(admin.ModelAdmin):
    list_display = ("customer", "zone", "assigned_by", "updated_at")
    list_filter = ("zone__organization", "zone__branch", "zone")
    autocomplete_fields = ("customer", "zone", "assigned_by")


class CollectionRouteStopInline(admin.TabularInline):
    model = CollectionRouteStop
    extra = 0


@admin.register(CollectionRoute)
class CollectionRouteAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "zone", "collector", "day_of_week", "is_active")
    list_filter = ("is_active", "organization", "branch", "day_of_week")
    search_fields = ("name", "collector__username")
    inlines = (CollectionRouteStopInline,)


@admin.register(RouteVisit)
class RouteVisitAdmin(admin.ModelAdmin):
    list_display = ("route", "route_stop", "collector", "visit_date", "status")
    list_filter = ("status", "visit_date", "route__organization", "route__branch")
    readonly_fields = tuple(field.name for field in RouteVisit._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(CollectorWorkSession)
class CollectorWorkSessionAdmin(admin.ModelAdmin):
    list_display = ("collector", "branch", "work_date", "started_at", "ended_at", "status")
    list_filter = ("status", "organization", "branch", "work_date")
    readonly_fields = tuple(field.name for field in CollectorWorkSession._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


class CollectorSettlementPaymentInline(admin.TabularInline):
    model = CollectorSettlementPayment
    extra = 0
    can_delete = False
    readonly_fields = tuple(field.name for field in CollectorSettlementPayment._meta.fields)


@admin.register(CollectorSettlement)
class CollectorSettlementAdmin(admin.ModelAdmin):
    list_display = (
        "settlement_number", "collector", "branch", "total_collected", "expected_cash",
        "reported_cash", "difference", "status", "submitted_at",
    )
    list_filter = ("status", "organization", "branch")
    search_fields = ("settlement_number", "collector__username")
    readonly_fields = tuple(field.name for field in CollectorSettlement._meta.fields)
    inlines = (CollectorSettlementPaymentInline,)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(CollectionOperationsAudit)
class CollectionOperationsAuditAdmin(admin.ModelAdmin):
    list_display = ("event", "organization", "actor", "created_at")
    list_filter = ("event", "organization")
    search_fields = ("description",)
    readonly_fields = tuple(field.name for field in CollectionOperationsAudit._meta.fields)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
