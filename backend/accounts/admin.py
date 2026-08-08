from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Role


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Memora", {"fields": ("phone", "role", "organization", "branch")}),
        ("Auditoría básica", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos de Memora", {"fields": ("email", "first_name", "last_name", "phone", "role", "organization", "branch")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "organization", "branch", "is_active")
    list_filter = ("is_active", "is_staff", "role", "organization")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    autocomplete_fields = ("organization", "branch", "role")
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")

