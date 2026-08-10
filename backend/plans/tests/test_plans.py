from decimal import Decimal

from rest_framework import status

from plans.choices import PlanActivityAction
from plans.models import FuneralPlan, FuneralServiceItem

from .base import PlanAPITestCase


class FuneralPlanTests(PlanAPITestCase):
    def test_create_plan_with_items_cost_margin_and_branch_availability(self):
        self.authenticate()
        response = self.client.post("/api/plans/", self.plan_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data["data"]
        self.assertEqual(data["code"], "PLA-000001")
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(Decimal(data["estimated_plan_cost"]), Decimal("13600.00"))
        self.assertEqual(Decimal(data["estimated_margin"]), Decimal("11400.00"))
        self.assertEqual(Decimal(data["estimated_margin_percent"]), Decimal("45.60"))
        self.assertEqual(data["availability"]["branches"][0]["id"], self.branch_a.pk)

    def test_update_plan_replaces_items_and_records_price_changes(self):
        self.authenticate()
        plan = self.make_plan()
        response = self.client.patch(
            f"/api/plans/{plan.pk}/",
            {
                "base_price": "24000.00",
                "items": [{"service_id": self.service_a2.pk, "quantity": "3.00", "included": True}],
            }, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["items"][0]["quantity"], "3.00")
        plan.refresh_from_db()
        self.assertTrue(plan.activities.filter(action=PlanActivityAction.PRICE_CHANGED).exists())
        self.assertTrue(plan.activities.filter(action=PlanActivityAction.SERVICE_ADDED).exists())
        self.assertTrue(plan.activities.filter(action=PlanActivityAction.SERVICE_REMOVED).exists())

    def test_deactivate_and_reactivate_plan(self):
        self.authenticate()
        plan = self.make_plan()
        inactive = self.client.post(f"/api/plans/{plan.pk}/deactivate/")
        active = self.client.post(f"/api/plans/{plan.pk}/activate/")
        self.assertFalse(inactive.data["data"]["is_active"])
        self.assertTrue(active.data["data"]["is_active"])

    def test_duplicate_is_atomic_and_copies_configuration(self):
        self.authenticate()
        source = self.make_plan(branch=self.branch_a)
        source.items.update(quantity=2, notes="Configuración original")
        response = self.client.post(f"/api/plans/{source.pk}/duplicate/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duplicate = FuneralPlan.objects.get(pk=response.data["data"]["id"])
        self.assertNotEqual(duplicate.code, source.code)
        self.assertEqual(duplicate.name, "Copia de Plan Base")
        self.assertEqual(duplicate.items.get().quantity, Decimal("2.00"))
        self.assertEqual(duplicate.branch_availabilities.get().branch_id, self.branch_a.pk)
        self.assertEqual(duplicate.activities.count(), 1)
        self.assertEqual(duplicate.activities.get().action, PlanActivityAction.DUPLICATED)

    def test_inactive_service_remains_but_cannot_be_newly_added(self):
        self.authenticate()
        plan = self.make_plan()
        self.service_a.is_active = False
        self.service_a.save(update_fields=("is_active", "updated_at"))
        preserved = self.client.patch(
            f"/api/plans/{plan.pk}/",
            {"items": [{"service_id": self.service_a.pk, "quantity": "2.00", "included": True}]},
            format="json",
        )
        self.assertEqual(preserved.status_code, status.HTTP_200_OK)
        other_plan = self.client.post(
            "/api/plans/", self.plan_payload(items=[{
                "service_id": self.service_a.pk, "quantity": "1.00", "included": True,
            }]), format="json",
        )
        self.assertEqual(other_plan.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_filters_and_pagination(self):
        self.authenticate()
        for index in range(14):
            FuneralPlan.objects.create(
                organization=self.org_a, code=f"PLA-X{index:04d}", name=f"Especial {index}",
                base_price=10000 + index, initial_payment=0, allow_financing=index % 2 == 0,
                created_by=self.admin_a,
            )
        response = self.client.get("/api/plans/?search=Especial&allow_financing=true&page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 7)
        paged = self.client.get("/api/plans/?search=Especial&page=2")
        self.assertEqual(paged.data["data"]["total_pages"], 2)
        self.assertEqual(len(paged.data["data"]["results"]), 2)

    def test_invalid_prices_and_duplicate_items_are_rejected(self):
        self.authenticate()
        negative = self.client.post("/api/plans/", self.plan_payload(base_price="-1.00"), format="json")
        duplicate = self.client.post("/api/plans/", self.plan_payload(items=[
            {"service_id": self.service_a.pk, "quantity": "1.00"},
            {"service_id": self.service_a.pk, "quantity": "2.00"},
        ]), format="json")
        self.assertEqual(negative.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
