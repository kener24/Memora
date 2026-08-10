from decimal import Decimal

from rest_framework.test import APITestCase

from accounts.models import CustomUser, Role, RoleCode
from organizations.models import Branch, Organization
from plans.models import FuneralPlan, FuneralPlanItem, FuneralServiceItem, PlanBranchAvailability
from plans.services import allocate_plan_code


class PlanAPITestCase(APITestCase):
    password = "Memora-Test-Plan-938!"

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Funeraria Aurora", tax_id="PLAN-ORG-A")
        cls.org_b = Organization.objects.create(name="Funeraria Serena", tax_id="PLAN-ORG-B")
        cls.branch_a = Branch.objects.create(organization=cls.org_a, name="Central A", code="A-CEN")
        cls.branch_a2 = Branch.objects.create(organization=cls.org_a, name="Norte A", code="A-NOR")
        cls.branch_b = Branch.objects.create(organization=cls.org_b, name="Central B", code="B-CEN")
        roles = {code: Role.objects.get(code=code) for code in (
            RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER, RoleCode.ACCOUNTANT, RoleCode.INVENTORY,
        )}
        cls.admin_a = cls.make_user("plan.admin.a", cls.org_a, cls.branch_a, roles[RoleCode.ADMIN])
        cls.admin_b = cls.make_user("plan.admin.b", cls.org_b, cls.branch_b, roles[RoleCode.ADMIN])
        cls.manager_a = cls.make_user("plan.manager.a", cls.org_a, cls.branch_a, roles[RoleCode.MANAGER])
        cls.seller_a = cls.make_user("plan.seller.a", cls.org_a, cls.branch_a, roles[RoleCode.SELLER])
        cls.accountant_a = cls.make_user("plan.accountant.a", cls.org_a, cls.branch_a, roles[RoleCode.ACCOUNTANT])
        cls.inventory_a = cls.make_user("plan.inventory.a", cls.org_a, cls.branch_a, roles[RoleCode.INVENTORY])
        cls.service_a = cls.make_service(cls.org_a, cls.admin_a, "ATA-001", "Ataúd estándar", "casket", "12000.00")
        cls.service_a2 = cls.make_service(cls.org_a, cls.admin_a, "TRA-001", "Traslado local", "transport", "800.00")
        cls.service_b = cls.make_service(cls.org_b, cls.admin_b, "ATA-001", "Ataúd Serena", "casket", "9000.00")

    @classmethod
    def make_user(cls, username, organization, branch, role):
        return CustomUser.objects.create_user(
            username=username, email=f"{username}@example.com", password=cls.password,
            organization=organization, branch=branch, role=role,
        )

    @classmethod
    def make_service(cls, organization, user, code, name, category="other", cost="100.00"):
        return FuneralServiceItem.objects.create(
            organization=organization, code=code, name=name, category=category, unit="service",
            estimated_cost=Decimal(cost), default_sale_price=Decimal(cost) * 2, created_by=user,
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.admin_a)

    def service_payload(self, **overrides):
        payload = {
            "code": "VEL-001", "name": "Sala velatoria", "description": "Uso de sala",
            "category": "wake", "unit": "day", "estimated_cost": "1500.00",
            "default_sale_price": "2500.00",
        }
        payload.update(overrides)
        return payload

    def plan_payload(self, **overrides):
        payload = {
            "name": "Plan Familiar", "description": "Cobertura comercial familiar",
            "base_price": "25000.00", "initial_payment": "5000.00", "allow_financing": True,
            "available_all_branches": False, "available_branch_ids": [self.branch_a.pk],
            "items": [
                {"service_id": self.service_a.pk, "quantity": "1.00", "included": True, "notes": "Modelo estándar"},
                {"service_id": self.service_a2.pk, "quantity": "2.00", "included": True, "notes": "Radio local"},
            ],
        }
        payload.update(overrides)
        return payload

    def make_plan(self, organization=None, user=None, branch=None, active=True):
        organization = organization or self.org_a
        user = user or self.admin_a
        plan = FuneralPlan.objects.create(
            organization=organization, code=allocate_plan_code(organization), name="Plan Base",
            base_price=Decimal("20000.00"), initial_payment=Decimal("2000.00"), allow_financing=True,
            available_all_branches=branch is None, is_active=active, created_by=user,
        )
        service = self.service_a if organization == self.org_a else self.service_b
        FuneralPlanItem.objects.create(plan=plan, service=service, quantity=1)
        if branch:
            PlanBranchAvailability.objects.create(plan=plan, branch=branch)
        return plan
