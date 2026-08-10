from rest_framework import status

from .base import PlanAPITestCase


class PlanSecurityTests(PlanAPITestCase):
    def test_organization_isolation_prevents_read_edit_and_service_idor(self):
        plan_b = self.make_plan(self.org_b, self.admin_b)
        self.authenticate(self.admin_a)
        read = self.client.get(f"/api/plans/{plan_b.pk}/")
        edit = self.client.patch(f"/api/plans/{plan_b.pk}/", {"name": "Intrusión"}, format="json")
        service = self.client.patch(
            f"/api/plans/services/{self.service_b.pk}/", {"name": "Intrusión"}, format="json"
        )
        self.assertEqual(read.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(edit.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(service.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_organization_service_and_branch_are_rejected(self):
        self.authenticate()
        foreign_service = self.client.post(
            "/api/plans/", self.plan_payload(items=[{
                "service_id": self.service_b.pk, "quantity": "1.00", "included": True,
            }]), format="json",
        )
        foreign_branch = self.client.post(
            "/api/plans/", self.plan_payload(available_branch_ids=[self.branch_b.pk]), format="json"
        )
        self.assertEqual(foreign_service.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign_branch.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_only_reads_active_plans_available_in_own_branch(self):
        visible = self.make_plan(branch=self.branch_a)
        self.make_plan(branch=self.branch_a2)
        self.make_plan(branch=self.branch_a, active=False)
        self.authenticate(self.seller_a)
        listing = self.client.get("/api/plans/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data["data"]["results"]], [visible.pk])
        denied = self.client.patch(f"/api/plans/{visible.pk}/", {"name": "No permitido"}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_cost_fields_are_never_sent_to_seller(self):
        plan = self.make_plan(branch=self.branch_a)
        self.authenticate(self.seller_a)
        detail = self.client.get(f"/api/plans/{plan.pk}/")
        services = self.client.get("/api/plans/services/")
        data = detail.data["data"]
        self.assertNotIn("estimated_plan_cost", data)
        self.assertNotIn("estimated_margin", data)
        self.assertNotIn("estimated_cost", data["items"][0]["service"])
        self.assertNotIn("estimated_cost", services.data["data"]["results"][0])

    def test_accountant_receives_costs_but_cannot_modify(self):
        plan = self.make_plan()
        self.authenticate(self.accountant_a)
        detail = self.client.get(f"/api/plans/{plan.pk}/")
        denied = self.client.patch(f"/api/plans/{plan.pk}/", {"name": "No permitido"}, format="json")
        self.assertIn("estimated_plan_cost", detail.data["data"])
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_cannot_bypass_scope_with_branch_filter_or_duplicate(self):
        hidden = self.make_plan(branch=self.branch_a2)
        self.authenticate(self.seller_a)
        read = self.client.get(f"/api/plans/{hidden.pk}/")
        duplicate = self.client.post(f"/api/plans/{hidden.pk}/duplicate/")
        self.assertEqual(read.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(duplicate.status_code, status.HTTP_403_FORBIDDEN)
