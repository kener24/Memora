from django.urls import reverse
from rest_framework import status

from customers.models import Beneficiary, Customer

from .base import CustomerAPITestCase


class CustomerSecurityTests(CustomerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer_a = Customer.objects.create(
            organization=cls.org_a, branch=cls.branch_a, customer_code="CLI-000001",
            first_name="Cliente", last_name="A", phone="98765432", created_by=cls.admin_a,
        )
        cls.customer_a2 = Customer.objects.create(
            organization=cls.org_a, branch=cls.branch_a2, customer_code="CLI-000002",
            first_name="Cliente", last_name="A2", phone="98765433", created_by=cls.admin_a,
        )
        cls.customer_b = Customer.objects.create(
            organization=cls.org_b, branch=cls.branch_b, customer_code="CLI-000001",
            first_name="Cliente", last_name="B", phone="98765434", created_by=cls.admin_b,
        )
        cls.beneficiary_b = Beneficiary.objects.create(
            customer=cls.customer_b, first_name="Beneficiario", last_name="B", relationship="relative"
        )

    def test_user_from_org_a_cannot_see_or_edit_org_b_customer(self):
        self.authenticate(self.admin_a)
        detail = self.client.get(reverse("customer-detail", args=(self.customer_b.pk,)))
        edit = self.client.patch(
            reverse("customer-detail", args=(self.customer_b.pk,)), {"phone": "99998888"}, format="json"
        )

        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(edit.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_beneficiary_from_other_organization(self):
        self.authenticate(self.admin_a)
        response = self.client.patch(
            reverse("beneficiary-detail", args=(self.customer_b.pk, self.beneficiary_b.pk)),
            {"phone": "99998888"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_branch_from_other_organization_is_rejected(self):
        self.authenticate(self.admin_a)
        response = self.client.post(
            reverse("customer-list"), self.customer_payload(branch=self.branch_b.pk), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", response.data["errors"])

    def test_seller_is_restricted_to_own_branch(self):
        self.authenticate(self.seller_a)
        response = self.client.get(reverse("customer-list"))
        ids = {item["id"] for item in response.data["data"]["results"]}

        self.assertIn(self.customer_a.pk, ids)
        self.assertNotIn(self.customer_a2.pk, ids)

    def test_inventory_role_has_no_access(self):
        self.authenticate(self.inventory_a)
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_collector_has_read_only_access(self):
        self.authenticate(self.collector_a)
        read = self.client.get(reverse("customer-detail", args=(self.customer_a.pk,)))
        create = self.client.post(reverse("customer-list"), self.customer_payload(), format="json")

        self.assertEqual(read.status_code, status.HTTP_200_OK)
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
