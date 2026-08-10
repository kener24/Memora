from django.contrib import admin

from .models import Contract, ContractActivity, ContractIdempotencyKey, ContractPlanItem, ContractSequence


class ContractPlanItemInline(admin.TabularInline):
    model = ContractPlanItem
    extra = 0
    readonly_fields = (
        "service_code_snapshot", "service_name_snapshot", "category_snapshot", "quantity",
        "unit_snapshot", "estimated_cost_snapshot",
    )


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("contract_number", "customer_name_snapshot", "organization", "branch", "total_price", "status")
    list_filter = ("organization", "branch", "status", "allow_financing")
    search_fields = ("contract_number", "customer_name_snapshot", "customer_identity_snapshot")
    inlines = (ContractPlanItemInline,)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != "draft":
            return tuple(field.name for field in obj._meta.fields)
        return super().get_readonly_fields(request, obj)


admin.site.register(ContractActivity)
admin.site.register(ContractIdempotencyKey)
admin.site.register(ContractSequence)
