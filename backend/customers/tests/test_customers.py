from django.urls import reverse
from rest_framework import status

from customers.models import Customer

from .base import CustomerAPITestCase


class CustomerCrudTests(CustomerAPITestCase):
    def test_create_valid_customer_and_activity(self):
        self.authenticate()
        response = self.client.post(reverse("customer-list"), self.customer_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(customer.organization, self.org_a)
        self.assertEqual(customer.created_by, self.admin_a)
        self.assertEqual(customer.customer_code, "CLI-000001")
        self.assertEqual(customer.activities.count(), 1)

    def test_required_fields_are_validated(self):
        self.authenticate()
        response = self.client.post(reverse("customer-list"), {"phone": "98765432"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data["errors"])
        self.assertIn("last_name", response.data["errors"])

    def test_customer_code_is_automatic_and_sequential(self):
        self.authenticate()
        first = self.client.post(reverse("customer-list"), self.customer_payload(), format="json")
        second = self.client.post(
            reverse("customer-list"),
            self.customer_payload(first_name="María", phone="9999-1111"),
            format="json",
        )

        self.assertEqual(first.data["data"]["customer_code"], "CLI-000001")
        self.assertEqual(second.data["data"]["customer_code"], "CLI-000002")

    def test_duplicate_active_identity_in_same_organization_is_rejected(self):
        self.authenticate()
        identity = "0801-1990-12345"
        self.client.post(reverse("customer-list"), self.customer_payload(identity_number=identity), format="json")
        response = self.client.post(
            reverse("customer-list"),
            self.customer_payload(first_name="Rosa", phone="99991111", identity_number="0801199012345"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("identity_number", response.data["errors"])

    def test_same_identity_is_allowed_in_other_organization(self):
        identity = "0801199012345"
        self.authenticate(self.admin_a)
        first = self.client.post(reverse("customer-list"), self.customer_payload(identity_number=identity), format="json")
        self.authenticate(self.admin_b)
        second = self.client.post(
            reverse("customer-list"),
            self.customer_payload(branch=self.branch_b.pk, identity_number=identity),
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

    def test_edit_customer_normalizes_values(self):
        self.authenticate()
        created = self.client.post(reverse("customer-list"), self.customer_payload(), format="json").data["data"]
        response = self.client.patch(
            reverse("customer-detail", args=(created["id"],)),
            {"first_name": "  Ana   María ", "email": " ANA@EXAMPLE.COM "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["first_name"], "Ana María")
        self.assertEqual(response.data["data"]["email"], "ana@example.com")

    def test_deactivate_and_reactivate_customer(self):
        self.authenticate()
        created = self.client.post(reverse("customer-list"), self.customer_payload(), format="json").data["data"]
        deactivated = self.client.post(reverse("customer-deactivate", args=(created["id"],)), format="json")
        activated = self.client.post(reverse("customer-activate", args=(created["id"],)), format="json")

        self.assertFalse(deactivated.data["data"]["is_active"])
        self.assertTrue(activated.data["data"]["is_active"])
        self.assertEqual(Customer.objects.get(pk=created["id"]).activities.count(), 3)

    def test_future_birth_date_is_rejected(self):
        self.authenticate()
        response = self.client.post(
            reverse("customer-list"), self.customer_payload(birth_date="2999-01-01"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("birth_date", response.data["errors"])


class CustomerListTests(CustomerAPITestCase):
    def create_customer(self, code, name, branch=None, active=True, department="cortes"):
        return Customer.objects.create(
            organization=self.org_a,
            branch=branch or self.branch_a,
            customer_code=code,
            first_name=name,
            last_name="Prueba",
            phone=f"98{int(code[-6:]):06d}"[-8:],
            department=department,
            is_active=active,
            created_by=self.admin_a,
        )

    def test_search_is_performed_by_backend(self):
        self.create_customer("CLI-000010", "Esperanza")
        self.create_customer("CLI-000011", "Dolores")
        self.authenticate()
        response = self.client.get(reverse("customer-list"), {"search": "esper"})

        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["full_name"], "Esperanza Prueba")

    def test_filters_by_status_branch_department_and_date(self):
        self.create_customer("CLI-000010", "Activo", branch=self.branch_a, department="cortes")
        self.create_customer("CLI-000011", "Inactivo", branch=self.branch_a2, active=False, department="yoro")
        self.authenticate()
        response = self.client.get(
            reverse("customer-list"),
            {"is_active": "false", "branch": self.branch_a2.pk, "department": "yoro", "created_from": "2020-01-01"},
        )

        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["full_name"], "Inactivo Prueba")

    def test_pagination_returns_total_and_pages(self):
        for number in range(1, 15):
            self.create_customer(f"CLI-{number:06d}", f"Cliente {number}")
        self.authenticate()
        response = self.client.get(reverse("customer-list"), {"page": 2})

        self.assertEqual(response.data["data"]["count"], 14)
        self.assertEqual(response.data["data"]["page"], 2)
        self.assertEqual(response.data["data"]["total_pages"], 2)
        self.assertEqual(len(response.data["data"]["results"]), 2)
