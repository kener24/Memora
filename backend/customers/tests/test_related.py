from django.urls import reverse
from rest_framework import status

from customers.models import Beneficiary, Customer, CustomerContact

from .base import CustomerAPITestCase


class RelatedRecordsTests(CustomerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer = Customer.objects.create(
            organization=cls.org_a,
            branch=cls.branch_a,
            customer_code="CLI-000001",
            first_name="Esperanza",
            last_name="Estrada",
            phone="98765432",
            created_by=cls.admin_a,
        )

    def test_create_edit_and_deactivate_beneficiary(self):
        self.authenticate()
        create = self.client.post(
            reverse("beneficiary-list-create", args=(self.customer.pk,)),
            {"first_name": "José", "last_name": "Estrada", "relationship": "son", "phone": "9999-1111"},
            format="json",
        )
        beneficiary_id = create.data["data"]["id"]
        edit = self.client.patch(
            reverse("beneficiary-detail", args=(self.customer.pk, beneficiary_id)),
            {"first_name": "José Luis"},
            format="json",
        )
        deactivate = self.client.patch(
            reverse("beneficiary-detail", args=(self.customer.pk, beneficiary_id)),
            {"is_active": False},
            format="json",
        )

        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(edit.data["data"]["first_name"], "José Luis")
        self.assertFalse(deactivate.data["data"]["is_active"])
        self.assertEqual(self.customer.activities.count(), 3)

    def test_self_beneficiary_does_not_duplicate_customer_data(self):
        self.authenticate()
        response = self.client.post(
            reverse("beneficiary-list-create", args=(self.customer.pk,)),
            {"is_customer": True, "relationship": "self"},
            format="json",
        )
        beneficiary = Beneficiary.objects.get(pk=response.data["data"]["id"])

        self.assertEqual(response.data["data"]["full_name"], self.customer.full_name)
        self.assertEqual(beneficiary.first_name, "")

    def test_create_edit_and_switch_primary_contact(self):
        self.authenticate()
        first = self.client.post(
            reverse("contact-list-create", args=(self.customer.pk,)),
            {"name": "Rosa Estrada", "relationship": "Hermana", "phone": "99991111", "is_primary": True},
            format="json",
        )
        second = self.client.post(
            reverse("contact-list-create", args=(self.customer.pk,)),
            {"name": "Carlos Estrada", "relationship": "Hijo", "phone": "88882222", "is_primary": True},
            format="json",
        )
        edit = self.client.patch(
            reverse("contact-detail", args=(self.customer.pk, second.data["data"]["id"])),
            {"secondary_phone": "7777-3333"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertFalse(CustomerContact.objects.get(pk=first.data["data"]["id"]).is_primary)
        self.assertTrue(CustomerContact.objects.get(pk=second.data["data"]["id"]).is_primary)
        self.assertEqual(edit.data["data"]["secondary_phone"], "7777-3333")

    def test_contact_id_cannot_be_mixed_between_customers(self):
        other = Customer.objects.create(
            organization=self.org_a, branch=self.branch_a, customer_code="CLI-000002",
            first_name="Otro", last_name="Cliente", phone="88887777", created_by=self.admin_a,
        )
        contact = CustomerContact.objects.create(customer=other, name="Contacto", phone="99990000")
        self.authenticate()
        response = self.client.patch(
            reverse("contact-detail", args=(self.customer.pk, contact.pk)),
            {"name": "Manipulado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
