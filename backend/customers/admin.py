from django.contrib import admin

from .models import Beneficiary, Customer, CustomerActivity, CustomerContact


class BeneficiaryInline(admin.TabularInline):
    model = Beneficiary
    extra = 0
    can_delete = False


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 0
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_code", "full_name", "organization", "branch", "phone", "is_active", "created_at")
    list_filter = ("is_active", "organization", "branch", "department")
    search_fields = ("customer_code", "first_name", "last_name", "identity_number", "phone", "email")
    readonly_fields = ("customer_code", "created_by", "created_at", "updated_at")
    autocomplete_fields = ("organization", "branch")
    inlines = (BeneficiaryInline, CustomerContactInline)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "customer", "relationship", "is_active")
    list_filter = ("is_active", "relationship")
    search_fields = ("first_name", "last_name", "identity_number", "customer__customer_code")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "phone", "is_primary", "is_active")
    list_filter = ("is_primary", "is_active")
    search_fields = ("name", "phone", "customer__customer_code")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerActivity)
class CustomerActivityAdmin(admin.ModelAdmin):
    list_display = ("customer", "action", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("customer__customer_code", "description")
    readonly_fields = ("customer", "user", "action", "description", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
