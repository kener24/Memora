from django.contrib import admin

from .models import Payment, PaymentApplication, Receipt


class PaymentApplicationInline(admin.TabularInline):
    model = PaymentApplication
    extra = 0
    can_delete = False
    readonly_fields = ("installment", "amount_applied", "created_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_number", "contract", "amount", "payment_method", "payment_type", "status", "payment_date")
    list_filter = ("status", "payment_method", "payment_type", "organization", "branch")
    search_fields = ("payment_number", "contract__contract_number", "customer__first_name", "customer__last_name", "reference")
    readonly_fields = tuple(field.name for field in Payment._meta.fields)
    inlines = (PaymentApplicationInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "payment", "status", "issued_at", "amount_snapshot")
    search_fields = ("receipt_number", "payment__payment_number", "contract_number_snapshot", "customer_name_snapshot")
    readonly_fields = tuple(field.name for field in Receipt._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
