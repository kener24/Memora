from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel

from .choices import ActivityAction, Gender, HondurasDepartment, MaritalStatus, Relationship
from .normalization import normalize_email, normalize_identity, normalize_phone, normalize_text


class CustomerSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="customer_sequence",
    )
    next_value = models.PositiveBigIntegerField(default=1)


class Customer(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="customers"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="customers", blank=True, null=True
    )
    customer_code = models.CharField(max_length=20, editable=False)
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    second_last_name = models.CharField(max_length=80, blank=True)
    identity_number = models.CharField(max_length=30, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    marital_status = models.CharField(max_length=20, choices=MaritalStatus.choices, blank=True)
    phone = models.CharField(max_length=25)
    secondary_phone = models.CharField(max_length=25, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=30, choices=HondurasDepartment.choices, blank=True)
    country = models.CharField(max_length=80, default="Honduras", blank=True)
    occupation = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_customers",
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "customer_code"), name="unique_customer_code_per_organization"
            ),
            models.UniqueConstraint(
                fields=("organization", "identity_number"),
                condition=Q(identity_number__isnull=False, is_active=True),
                name="unique_active_customer_identity_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active"), name="cust_org_active_idx"),
            models.Index(fields=("phone",), name="cust_phone_idx"),
            models.Index(fields=("created_at",), name="cust_created_idx"),
        ]

    @property
    def full_name(self):
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name, self.second_last_name) if part
        )

    def clean(self):
        super().clean()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "La sucursal debe pertenecer a la organización del cliente."})

    def save(self, *args, **kwargs):
        for field in (
            "first_name", "middle_name", "last_name", "second_last_name", "address", "city",
            "country", "occupation", "notes",
        ):
            setattr(self, field, normalize_text(getattr(self, field)))
        self.email = normalize_email(self.email)
        self.phone = normalize_phone(self.phone)
        self.secondary_phone = normalize_phone(self.secondary_phone)
        self.identity_number = normalize_identity(self.identity_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_code} · {self.full_name}"


class Beneficiary(TimeStampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="beneficiaries")
    is_customer = models.BooleanField(default=False)
    first_name = models.CharField(max_length=80, blank=True)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    second_last_name = models.CharField(max_length=80, blank=True)
    identity_number = models.CharField(max_length=30, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    phone = models.CharField(max_length=25, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("first_name", "last_name", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("customer",),
                condition=Q(is_customer=True, is_active=True),
                name="unique_active_self_beneficiary",
            )
        ]

    @property
    def full_name(self):
        if self.is_customer:
            return self.customer.full_name
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name, self.second_last_name) if part
        )

    def clean(self):
        super().clean()
        if self.is_customer and self.relationship != Relationship.SELF:
            raise ValidationError({"relationship": "El beneficiario titular debe usar el parentesco Titular."})
        if not self.is_customer and self.relationship == Relationship.SELF:
            raise ValidationError({"is_customer": "Indica que este beneficiario es el titular."})
        if not self.is_customer and (not normalize_text(self.first_name) or not normalize_text(self.last_name)):
            raise ValidationError("Nombre y apellido son obligatorios para un beneficiario distinto del titular.")

    def save(self, *args, **kwargs):
        for field in ("first_name", "middle_name", "last_name", "second_last_name", "address", "notes"):
            setattr(self, field, normalize_text(getattr(self, field)))
        self.phone = normalize_phone(self.phone)
        self.identity_number = normalize_identity(self.identity_number)
        if self.is_customer:
            self.relationship = Relationship.SELF
            self.first_name = self.middle_name = self.last_name = self.second_last_name = ""
            self.identity_number = None
            self.birth_date = None
            self.phone = self.address = ""
        super().save(*args, **kwargs)


class CustomerContact(TimeStampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="contacts")
    name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=25)
    secondary_phone = models.CharField(max_length=25, blank=True)
    notes = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-is_primary", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("customer",),
                condition=Q(is_primary=True, is_active=True),
                name="unique_active_primary_contact",
            )
        ]

    def save(self, *args, **kwargs):
        self.name = normalize_text(self.name)
        self.relationship = normalize_text(self.relationship)
        self.phone = normalize_phone(self.phone)
        self.secondary_phone = normalize_phone(self.secondary_phone)
        self.notes = normalize_text(self.notes)
        super().save(*args, **kwargs)


class CustomerActivity(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="activities")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="customer_activities",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=40, choices=ActivityAction.choices)
    description = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("customer", "created_at"), name="cust_activity_idx")]
