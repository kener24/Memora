from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import CustomUser, Role, RoleCode
from customers.models import Beneficiary, Customer
from customers.services import allocate_customer_code
from organizations.models import Branch, Organization
from plans.models import FuneralPlan, FuneralPlanItem, FuneralServiceItem, PlanBranchAvailability
from plans.services import allocate_plan_code


class ContractAPITestCase(APITestCase):
    password = "Memora-Contracts-938!"

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Memora Aurora", tax_id="CTR-ORG-A")
        cls.org_b = Organization.objects.create(name="Memora Serena", tax_id="CTR-ORG-B")
        cls.branch_a = Branch.objects.create(organization=cls.org_a, name="Central A", code="A-CEN")
        cls.branch_a2 = Branch.objects.create(organization=cls.org_a, name="Norte A", code="A-NOR")
        cls.branch_b = Branch.objects.create(organization=cls.org_b, name="Central B", code="B-CEN")
        roles = {code: Role.objects.get(code=code) for code in (
            RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER, RoleCode.ACCOUNTANT,
            RoleCode.COLLECTOR, RoleCode.INVENTORY,
        )}
        cls.admin_a = cls.make_user("ctr.admin.a", cls.org_a, cls.branch_a, roles[RoleCode.ADMIN])
        cls.manager_a = cls.make_user("ctr.manager.a", cls.org_a, cls.branch_a, roles[RoleCode.MANAGER])
        cls.seller_a = cls.make_user("ctr.seller.a", cls.org_a, cls.branch_a, roles[RoleCode.SELLER])
        cls.seller_a2 = cls.make_user("ctr.seller.a2", cls.org_a, cls.branch_a2, roles[RoleCode.SELLER])
        cls.accountant_a = cls.make_user("ctr.accountant.a", cls.org_a, cls.branch_a, roles[RoleCode.ACCOUNTANT])
        cls.collector_a = cls.make_user("ctr.collector.a", cls.org_a, cls.branch_a, roles[RoleCode.COLLECTOR])
        cls.inventory_a = cls.make_user("ctr.inventory.a", cls.org_a, cls.branch_a, roles[RoleCode.INVENTORY])
        cls.admin_b = cls.make_user("ctr.admin.b", cls.org_b, cls.branch_b, roles[RoleCode.ADMIN])
        cls.customer_a = cls.make_customer(cls.org_a, cls.branch_a, cls.admin_a, "Ana", "Lagos", "0801199012345")
        cls.customer_a2 = cls.make_customer(cls.org_a, cls.branch_a2, cls.admin_a, "Mario", "Duarte", "0801199012346")
        cls.customer_b = cls.make_customer(cls.org_b, cls.branch_b, cls.admin_b, "Eva", "Paz", "0801199012347")
        cls.beneficiary_a = Beneficiary.objects.create(
            customer=cls.customer_a, first_name="Luis", last_name="Lagos", relationship="child",
            identity_number="0801200012345", phone="99998888",
        )
        cls.beneficiary_a2 = Beneficiary.objects.create(
            customer=cls.customer_a2, first_name="Sara", last_name="Duarte", relationship="spouse",
        )
        cls.service_a = cls.make_service(cls.org_a, cls.admin_a, "VEL-CTR", "Sala velatoria", "1500.00")
        cls.service_a2 = cls.make_service(cls.org_a, cls.admin_a, "TRA-CTR", "Traslado local", "800.00")
        cls.service_b = cls.make_service(cls.org_b, cls.admin_b, "VEL-B", "Sala Serena", "1200.00")
        cls.plan_a = cls.make_plan(cls.org_a, cls.admin_a, cls.service_a, cls.branch_a, "Plan Serenidad")
        FuneralPlanItem.objects.create(
            plan=cls.plan_a, service=cls.service_a2, quantity=Decimal("2.00"), notes="Perímetro urbano", sort_order=2,
        )
        cls.plan_a2 = cls.make_plan(cls.org_a, cls.admin_a, cls.service_a, cls.branch_a2, "Plan Norte")
        cls.plan_b = cls.make_plan(cls.org_b, cls.admin_b, cls.service_b, cls.branch_b, "Plan Serena")

    @classmethod
    def make_user(cls, username, organization, branch, role):
        return CustomUser.objects.create_user(
            username=username, email=f"{username}@example.com", password=cls.password,
            first_name=username.split(".")[1].title(), last_name="Memora", organization=organization,
            branch=branch, role=role,
        )

    @classmethod
    def make_customer(cls, organization, branch, user, first, last, identity):
        return Customer.objects.create(
            organization=organization, branch=branch, customer_code=allocate_customer_code(organization),
            first_name=first, last_name=last, identity_number=identity, phone="98765432",
            address="Barrio Centro, Honduras", created_by=user,
        )

    @classmethod
    def make_service(cls, organization, user, code, name, cost):
        return FuneralServiceItem.objects.create(
            organization=organization, code=code, name=name, description=f"Servicio {name}",
            category="other", unit="service", estimated_cost=Decimal(cost),
            default_sale_price=Decimal(cost) * 2, created_by=user,
        )

    @classmethod
    def make_plan(cls, organization, user, service, branch, name):
        plan = FuneralPlan.objects.create(
            organization=organization, code=allocate_plan_code(organization), name=name,
            description=f"Cobertura de {name}", base_price=Decimal("24000.00"),
            initial_payment=Decimal("4000.00"), allow_financing=True,
            available_all_branches=False, created_by=user,
        )
        FuneralPlanItem.objects.create(plan=plan, service=service, quantity=1, sort_order=1)
        PlanBranchAvailability.objects.create(plan=plan, branch=branch)
        return plan

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.admin_a)

    def payload(self, **overrides):
        payload = {
            "branch": self.branch_a.pk, "customer": self.customer_a.pk,
            "beneficiary": self.beneficiary_a.pk, "plan": self.plan_a.pk,
            "seller": self.seller_a.pk, "sale_date": str(timezone.localdate()),
            "start_date": str(timezone.localdate()), "discount": "1000.00",
            "allow_financing": True, "initial_payment_agreed": "5000.00",
            "payment_frequency": "monthly", "installment_amount": "1500.00",
            "first_due_date": str(timezone.localdate() + timedelta(days=30)),
            "notes": "Venta de prueba contractual",
        }
        payload.update(overrides)
        return payload

    def create_draft(self, user=None, key="create-contract-0001", **overrides):
        self.authenticate(user)
        return self.client.post(
            "/api/contracts/", self.payload(**overrides), format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def confirm(self, contract_id, user=None, key="confirm-contract-0001"):
        self.authenticate(user)
        return self.client.post(
            f"/api/contracts/{contract_id}/confirm/", {}, format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
