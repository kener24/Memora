import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, RoleCode
from customers.choices import ActivityAction, Relationship
from customers.models import Beneficiary, Customer, CustomerContact
from customers.services import allocate_customer_code, record_activity
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

        active_customer = Customer.objects.filter(
            organization=organization, identity_number="0801199012345"
        ).first()
        if not active_customer:
            active_customer = Customer.objects.create(
                organization=organization,
                branch=branch,
                customer_code=allocate_customer_code(organization),
                first_name="Esperanza",
                last_name="Estrada",
                identity_number="0801-1990-12345",
                birth_date="1990-05-12",
                phone="9876-5432",
                email="esperanza@example.com",
                department="francisco_morazan",
                city="Tegucigalpa",
                address="Colonia Palmira",
                occupation="Comerciante",
                created_by=user,
            )
            record_activity(active_customer, user, ActivityAction.CREATED)

        Beneficiary.objects.get_or_create(
            customer=active_customer,
            identity_number="0801199012346",
            defaults={
                "first_name": "José",
                "last_name": "Estrada",
                "relationship": Relationship.SON,
                "birth_date": "2012-08-21",
                "phone": "9999-1111",
            },
        )
        CustomerContact.objects.get_or_create(
            customer=active_customer,
            phone="8888-2222",
            defaults={
                "name": "Rosa Estrada",
                "relationship": "Hermana",
                "is_primary": True,
            },
        )

        inactive_customer = Customer.objects.filter(
            organization=organization, identity_number="0801198504321"
        ).first()
        if not inactive_customer:
            inactive_customer = Customer.objects.create(
                organization=organization,
                branch=branch,
                customer_code=allocate_customer_code(organization),
                first_name="Carlos",
                last_name="Mendoza",
                identity_number="0801-1985-04321",
                phone="9765-4321",
                department="comayagua",
                city="Comayagua",
                is_active=False,
                created_by=user,
            )
            record_activity(inactive_customer, user, ActivityAction.CREATED)

        self.stdout.write(self.style.SUCCESS("Datos mínimos de clientes creados o verificados."))
