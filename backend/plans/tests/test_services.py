from rest_framework import status

from plans.models import FuneralServiceItem

from .base import PlanAPITestCase


class ServiceCatalogTests(PlanAPITestCase):
    def test_admin_can_create_edit_deactivate_and_reactivate_service(self):
        self.authenticate()
        created = self.client.post("/api/plans/services/", self.service_payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        service_id = created.data["data"]["id"]
        self.assertEqual(created.data["data"]["code"], "VEL-001")
        edited = self.client.patch(
            f"/api/plans/services/{service_id}/", {"name": "Sala velatoria premium"}, format="json"
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        self.assertEqual(edited.data["data"]["name"], "Sala velatoria premium")
        inactive = self.client.post(f"/api/plans/services/{service_id}/deactivate/")
        active = self.client.post(f"/api/plans/services/{service_id}/activate/")
        self.assertFalse(inactive.data["data"]["is_active"])
        self.assertTrue(active.data["data"]["is_active"])

    def test_negative_costs_are_rejected(self):
        self.authenticate()
        response = self.client.post(
            "/api/plans/services/", self.service_payload(estimated_cost="-0.01"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("estimated_cost", response.data["errors"])

    def test_code_is_unique_per_organization_but_allowed_across_organizations(self):
        self.authenticate()
        duplicate = self.client.post(
            "/api/plans/services/", self.service_payload(code="ATA-001"), format="json"
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.authenticate(self.admin_b)
        allowed = self.client.post(
            "/api/plans/services/", self.service_payload(code="VEL-001"), format="json"
        )
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)

    def test_search_and_category_filter_run_on_backend(self):
        self.authenticate()
        response = self.client.get("/api/plans/services/?search=Traslado&category=transport")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["code"], "TRA-001")

    def test_manager_can_manage_and_seller_cannot_modify_catalog(self):
        self.authenticate(self.manager_a)
        allowed = self.client.post("/api/plans/services/", self.service_payload(), format="json")
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        self.authenticate(self.seller_a)
        denied = self.client.post("/api/plans/services/", self.service_payload(code="NEW-002"), format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_service_cannot_be_deleted(self):
        self.authenticate()
        response = self.client.delete(f"/api/plans/services/{self.service_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(FuneralServiceItem.objects.filter(pk=self.service_a.pk).exists())
