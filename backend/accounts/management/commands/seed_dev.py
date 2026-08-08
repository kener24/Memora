import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, RoleCode
from organizations.models import Branch, Organization


class Command(BaseCommand):
    help = "Crea una organización, sucursal y administrador mínimos para desarrollo."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv("SEED_ADMIN_PASSWORD")
        if not password:
            raise CommandError("Defina SEED_ADMIN_PASSWORD antes de ejecutar seed_dev.")

        organization, _ = Organization.objects.get_or_create(
            tax_id="DEV-LOCAL",
            defaults={"name": "Memora Desarrollo", "legal_name": "Memora Desarrollo"},
        )
        branch, _ = Branch.objects.get_or_create(
            organization=organization,
            code="CENTRAL",
            defaults={"name": "Sucursal Central"},
        )
        role, _ = Role.objects.update_or_create(
            code=RoleCode.ADMIN,
            defaults={"name": RoleCode.ADMIN.label, "is_active": True},
        )

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="admin.dev",
            defaults={
                "email": "admin@memora.local",
                "first_name": "Administrador",
                "last_name": "Local",
                "organization": organization,
                "branch": branch,
                "role": role,
                "is_staff": True,
            },
        )
        user.email = "admin@memora.local"
        user.organization = organization
        user.branch = branch
        user.role = role
        user.is_staff = True
        user.is_active = True
        user.set_password(password)
        user.full_clean(exclude=("password",))
        user.save()

        action = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Entorno de desarrollo listo; usuario {action}: admin.dev"))

