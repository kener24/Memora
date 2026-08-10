from django.contrib import admin

from .models import (
    FuneralPlan, FuneralPlanItem, FuneralServiceItem, PlanActivity, PlanBranchAvailability, PlanSequence,
)


class PlanItemInline(admin.TabularInline):
    model = FuneralPlanItem
    extra = 0


class BranchAvailabilityInline(admin.TabularInline):
    model = PlanBranchAvailability
    extra = 0


@admin.register(FuneralServiceItem)
class FuneralServiceItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "category", "unit", "is_active")
    list_filter = ("organization", "category", "is_active")
    search_fields = ("code", "name")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FuneralPlan)
class FuneralPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "base_price", "is_active")
    list_filter = ("organization", "allow_financing", "is_active")
    search_fields = ("code", "name")
    inlines = (PlanItemInline, BranchAvailabilityInline)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PlanSequence)
admin.site.register(PlanActivity)
