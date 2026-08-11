from django.contrib import admin

from .models import CollectionAction, CollectionAudit, PaymentPromise


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
