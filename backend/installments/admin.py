from django.contrib import admin

from .models import Installment, InstallmentSchedule


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    can_delete = False
    readonly_fields = tuple(field.name for field in Installment._meta.fields)


@admin.register(InstallmentSchedule)
class InstallmentScheduleAdmin(admin.ModelAdmin):
    list_display = ("contract", "version", "total_financed", "total_installments", "status", "generated_at")
    list_filter = ("organization", "branch", "status", "frequency")
    search_fields = ("contract__contract_number", "contract__customer_name_snapshot")
    readonly_fields = tuple(field.name for field in InstallmentSchedule._meta.fields)
    inlines = (InstallmentInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ("contract", "installment_number", "due_date", "current_amount", "status")
    list_filter = ("organization", "branch", "status", "due_date")
    search_fields = ("contract__contract_number", "contract__customer_name_snapshot")
    readonly_fields = tuple(field.name for field in Installment._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
