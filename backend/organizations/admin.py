from django.contrib import admin

from .models import Branch, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "tax_id", "email", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "legal_name", "tax_id", "email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "phone", "is_active")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "code", "organization__name")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")

