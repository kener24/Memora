from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel

from .choices import PlanActivityAction, ServiceCategory, ServiceUnit


class PlanSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="plan_sequence"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class FuneralServiceItem(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="service_catalog_items"
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=ServiceCategory.choices)
    unit = models.CharField(max_length=20, choices=ServiceUnit.choices, default=ServiceUnit.SERVICE)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_service_catalog_items"
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "code"), name="unique_service_code_per_org"),
            models.CheckConstraint(condition=Q(estimated_cost__gte=0), name="service_estimated_cost_gte_zero"),
            models.CheckConstraint(condition=Q(default_sale_price__gte=0), name="service_sale_price_gte_zero"),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="svc_org_active_idx"),
            models.Index(fields=("organization", "category"), name="svc_org_category_idx"),
            models.Index(fields=("name",), name="svc_name_idx"),
            models.Index(fields=("created_at",), name="svc_created_idx"),
        ]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.name = " ".join(self.name.split())
        self.description = self.description.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.name}"


class FuneralPlan(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="funeral_plans"
    )
    code = models.CharField(max_length=20, editable=False)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    initial_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allow_financing = models.BooleanField(default=False)
    available_all_branches = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_funeral_plans"
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "code"), name="unique_plan_code_per_org"),
            models.CheckConstraint(condition=Q(base_price__gte=0), name="plan_base_price_gte_zero"),
            models.CheckConstraint(condition=Q(initial_payment__gte=0), name="plan_initial_payment_gte_zero"),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="plan_org_active_idx"),
            models.Index(fields=("name",), name="plan_name_idx"),
            models.Index(fields=("created_at",), name="plan_created_idx"),
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.description = self.description.strip()
        super().save(*args, **kwargs)

    @property
    def estimated_plan_cost(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("items")
        items = prefetched if prefetched is not None else self.items.select_related("service").all()
        return sum(
            (item.service.estimated_cost * item.quantity for item in items if item.included),
            Decimal("0.00"),
        )

    @property
    def estimated_margin(self):
        return self.base_price - self.estimated_plan_cost

    @property
    def estimated_margin_percent(self):
        if self.base_price == 0:
            return None
        return (self.estimated_margin / self.base_price * Decimal("100")).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.code} · {self.name}"


class FuneralPlanItem(TimeStampedModel):
    plan = models.ForeignKey(FuneralPlan, on_delete=models.PROTECT, related_name="items")
    service = models.ForeignKey(FuneralServiceItem, on_delete=models.PROTECT, related_name="plan_items")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    included = models.BooleanField(default=True)
    notes = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("plan", "service"), name="unique_service_per_plan"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="plan_item_quantity_gt_zero"),
        ]
        indexes = [models.Index(fields=("plan", "sort_order"), name="plan_item_order_idx")]

    def clean(self):
        super().clean()
        if self.plan_id and self.service_id and self.plan.organization_id != self.service.organization_id:
            raise ValidationError({"service": "La prestación debe pertenecer a la organización del plan."})

    def save(self, *args, **kwargs):
        self.notes = self.notes.strip()
        super().save(*args, **kwargs)


class PlanBranchAvailability(models.Model):
    plan = models.ForeignKey(FuneralPlan, on_delete=models.CASCADE, related_name="branch_availabilities")
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="available_funeral_plans"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan", "branch"), name="unique_plan_branch_availability")
        ]

    def clean(self):
        super().clean()
        if self.plan_id and self.branch_id and self.plan.organization_id != self.branch.organization_id:
            raise ValidationError({"branch": "La sucursal debe pertenecer a la organización del plan."})


class PlanActivity(models.Model):
    plan = models.ForeignKey(FuneralPlan, on_delete=models.PROTECT, related_name="activities")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="plan_activities",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=40, choices=PlanActivityAction.choices)
    description = models.CharField(max_length=240)
    old_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    new_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("plan", "created_at"), name="plan_activity_idx")]
