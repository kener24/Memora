from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel


class Organization(TimeStampedModel):
    name = models.CharField("nombre", max_length=180)
    legal_name = models.CharField("razón social", max_length=220, blank=True)
    tax_id = models.CharField("identificación fiscal", max_length=50, blank=True, null=True, unique=True)
    phone = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("correo electrónico", blank=True)
    address = models.TextField("dirección", blank=True)
    logo = models.ImageField("logotipo", upload_to="organizations/logos/", blank=True, null=True)
    is_active = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "organización"
        verbose_name_plural = "organizaciones"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Branch(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="branches",
        verbose_name="organización",
    )
    name = models.CharField("nombre", max_length=180)
    code = models.CharField("código", max_length=30)
    phone = models.CharField("teléfono", max_length=30, blank=True)
    address = models.TextField("dirección", blank=True)
    is_active = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "sucursal"
        verbose_name_plural = "sucursales"
        ordering = ("organization__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="unique_branch_code_per_organization",
            )
        ]

    def clean(self):
        super().clean()
        if self.organization_id and not self.organization.is_active and self.is_active:
            raise ValidationError({"is_active": "Una sucursal activa requiere una organización activa."})

    def __str__(self):
        return f"{self.organization.name} · {self.name}"

