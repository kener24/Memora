from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel


class RoleCode(models.TextChoices):
    SUPERADMIN = "superadmin", "Superadministrador"
    ADMIN = "admin", "Administrador"
    MANAGER = "manager", "Gerente"
    SELLER = "seller", "Vendedor"
    COLLECTOR = "collector", "Cobrador"
    CASHIER = "cashier", "Cajero"
    INVENTORY = "inventory", "Inventario"
    ACCOUNTANT = "accountant", "Contador"


class Role(TimeStampedModel):
    code = models.CharField("código", max_length=30, unique=True, choices=RoleCode.choices)
    name = models.CharField("nombre", max_length=80)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "rol"
        verbose_name_plural = "roles"
        ordering = ("name",)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    email = models.EmailField("correo electrónico", unique=True)
    phone = models.CharField("teléfono", max_length=30, blank=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
        verbose_name="rol",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
        verbose_name="organización",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
        verbose_name="sucursal",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ("first_name", "last_name", "username")

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.branch_id and not self.organization_id:
            raise ValidationError({"organization": "Una sucursal requiere una organización."})
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "La sucursal debe pertenecer a la organización seleccionada."})
        if self.role_id and self.role.code != RoleCode.SUPERADMIN and not self.organization_id:
            raise ValidationError({"organization": "Los usuarios que no son superadministradores requieren una organización."})

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

