import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, RoleCode
from customers.choices import ActivityAction, Relationship
from customers.models import Beneficiary, Customer, CustomerContact
from customers.services import allocate_customer_code, record_activity
from organizations.models import Branch, Organization
from plans.choices import PlanActivityAction
from plans.models import FuneralPlan, FuneralPlanItem, FuneralServiceItem
from plans.services import allocate_plan_code, record_plan_activity


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

        service_definitions = (
            ("ATA-EST", "Ataúd estándar", "casket", "unit", "8500.00", "11000.00"),
            ("PRE-BAS", "Preparación básica", "preparation", "service", "1800.00", "2800.00"),
            ("SAL-VEL", "Sala velatoria", "wake", "day", "1200.00", "2200.00"),
            ("TRA-LOC", "Traslado local", "transport", "service", "800.00", "1400.00"),
            ("SIL-UNI", "Sillas para ceremonia", "furniture", "quantity", "18.00", "30.00"),
        )
        catalog = {}
        for code, name, category, unit, cost, price in service_definitions:
            service, _ = FuneralServiceItem.objects.get_or_create(
                organization=organization,
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "estimated_cost": Decimal(cost),
                    "default_sale_price": Decimal(price),
                    "created_by": user,
                },
            )
            catalog[code] = service

        plan = FuneralPlan.objects.filter(organization=organization, name="Plan Protección Familiar").first()
        if not plan:
            plan = FuneralPlan.objects.create(
                organization=organization,
                code=allocate_plan_code(organization),
                name="Plan Protección Familiar",
                description="Cobertura comercial con prestaciones esenciales para una familia.",
                base_price=Decimal("25000.00"),
                initial_payment=Decimal("5000.00"),
                allow_financing=True,
                available_all_branches=True,
                created_by=user,
            )
            record_plan_activity(plan, user, PlanActivityAction.CREATED)

        item_definitions = (("ATA-EST", "1.00"), ("PRE-BAS", "1.00"), ("SAL-VEL", "2.00"), ("TRA-LOC", "1.00"), ("SIL-UNI", "50.00"))
        for order, (code, quantity) in enumerate(item_definitions):
            FuneralPlanItem.objects.get_or_create(
                plan=plan,
                service=catalog[code],
                defaults={"quantity": Decimal(quantity), "sort_order": order},
            )

        self.stdout.write(self.style.SUCCESS("Catálogo y plan funerario de demostración creados o verificados."))
