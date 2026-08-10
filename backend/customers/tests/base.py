from rest_framework.test import APITestCase

from accounts.models import CustomUser, Role, RoleCode
from organizations.models import Branch, Organization


class CustomerAPITestCase(APITestCase):
    password = "Memora-Test-938!"

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organization.objects.create(name="Funeraria Aurora", tax_id="ORG-A")
        cls.org_b = Organization.objects.create(name="Funeraria Serena", tax_id="ORG-B")
        cls.branch_a = Branch.objects.create(organization=cls.org_a, name="Central A", code="A-CEN")
        cls.branch_a2 = Branch.objects.create(organization=cls.org_a, name="Norte A", code="A-NOR")
        cls.branch_b = Branch.objects.create(organization=cls.org_b, name="Central B", code="B-CEN")
        cls.admin_role = Role.objects.get(code=RoleCode.ADMIN)
        cls.seller_role = Role.objects.get(code=RoleCode.SELLER)
        cls.collector_role = Role.objects.get(code=RoleCode.COLLECTOR)
        cls.inventory_role = Role.objects.get(code=RoleCode.INVENTORY)
        cls.admin_a = CustomUser.objects.create_user(
            username="admin.a",
            email="admin.a@example.com",
            password=cls.password,
            organization=cls.org_a,
            branch=cls.branch_a,
            role=cls.admin_role,
        )
        cls.admin_b = CustomUser.objects.create_user(
            username="admin.b",
            email="admin.b@example.com",
            password=cls.password,
            organization=cls.org_b,
            branch=cls.branch_b,
            role=cls.admin_role,
        )
        cls.seller_a = CustomUser.objects.create_user(
            username="seller.a",
            email="seller.a@example.com",
            password=cls.password,
            organization=cls.org_a,
            branch=cls.branch_a,
            role=cls.seller_role,
        )
        cls.collector_a = CustomUser.objects.create_user(
            username="collector.a",
            email="collector.a@example.com",
            password=cls.password,
            organization=cls.org_a,
            branch=cls.branch_a,
            role=cls.collector_role,
        )
        cls.inventory_a = CustomUser.objects.create_user(
            username="inventory.a",
            email="inventory.a@example.com",
            password=cls.password,
            organization=cls.org_a,
            branch=cls.branch_a,
            role=cls.inventory_role,
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.admin_a)

    def customer_payload(self, **overrides):
        payload = {
            "first_name": "Esperanza",
            "last_name": "Estrada",
            "phone": "9876-5432",
            "branch": self.branch_a.pk,
            "department": "francisco_morazan",
            "city": "Tegucigalpa",
        }
        payload.update(overrides)
        return payload
