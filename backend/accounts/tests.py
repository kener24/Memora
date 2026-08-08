from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import Branch, Organization

from .models import CustomUser, Role, RoleCode


class AuthenticationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Funeraria de Prueba")
        cls.branch = Branch.objects.create(
            organization=cls.organization,
            name="Central",
            code="CENTRAL",
        )
        cls.role = Role.objects.get(code=RoleCode.ADMIN)
        cls.user = CustomUser.objects.create_user(
            username="admin.test",
            email="admin@example.com",
            password="Memora-Test-938!",
            first_name="Ana",
            last_name="López",
            organization=cls.organization,
            branch=cls.branch,
            role=cls.role,
            is_staff=True,
        )

    def test_valid_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"identifier": "admin@example.com", "password": "Memora-Test-938!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    def test_invalid_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"identifier": "admin@example.com", "password": "incorrecta"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertNotIn("password", str(response.data).lower())

    def test_anonymous_me_is_rejected(self):
        response = self.client.get(reverse("accounts:me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_authenticated_user_can_get_me(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("accounts:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], self.user.email)
        self.assertEqual(response.data["data"]["rol"]["codigo"], RoleCode.ADMIN)
        self.assertEqual(response.data["data"]["organizacion"]["id"], self.organization.id)
        self.assertEqual(response.data["data"]["sucursal"]["id"], self.branch.id)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=("is_active", "updated_at"))
        response = self.client.post(
            reverse("accounts:login"),
            {"identifier": self.user.username, "password": "Memora-Test-938!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
