from decimal import Decimal

from rest_framework import status

from contracts.models import Contract, ContractActivity, ContractIdempotencyKey

from .base import ContractAPITestCase


class ContractCreationTests(ContractAPITestCase):
    def test_creates_draft_with_sequence_and_calculated_amounts(self):
        response = self.create_draft()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data["data"]
        self.assertEqual(data["contract_number"], "CTR-000001")
        self.assertEqual(data["status"], "draft")
        self.assertEqual(Decimal(data["subtotal"]), Decimal("24000.00"))
        self.assertEqual(Decimal(data["total_price"]), Decimal("23000.00"))
        self.assertEqual(Decimal(data["financed_amount"]), Decimal("18000.00"))
        self.assertEqual(ContractActivity.objects.filter(action="draft_created").count(), 1)

    def test_create_is_idempotent_and_does_not_consume_a_second_number(self):
        first = self.create_draft(key="same-create-key")
        second = self.create_draft(key="same-create-key")
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(ContractIdempotencyKey.objects.count(), 1)

    def test_cash_sale_resets_future_payment_fields(self):
        response = self.create_draft(
            allow_financing=False, initial_payment_agreed="900.00", payment_frequency="weekly",
            installment_amount="200.00", first_due_date="2099-01-01",
        )
        data = response.data["data"]
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(data["financed_amount"]), Decimal("0.00"))
        self.assertEqual(data["payment_frequency"], "")
        self.assertIsNone(data["first_due_date"])

    def test_rejects_invalid_discount_initial_payment_and_missing_idempotency(self):
        too_much = self.create_draft(discount="25000.00")
        full_prime = self.create_draft(key="full-prime-key", initial_payment_agreed="23000.00")
        self.authenticate()
        no_key = self.client.post("/api/contracts/", self.payload(), format="json")
        self.assertEqual(too_much.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(full_prime.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(no_key.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_only_updates_a_draft(self):
        draft = self.create_draft().data["data"]
        self.authenticate()
        changed = self.client.patch(f"/api/contracts/{draft['id']}/", {"notes": "Nota actualizada"}, format="json")
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertEqual(changed.data["data"]["notes"], "Nota actualizada")
        self.confirm(draft["id"])
        blocked = self.client.patch(f"/api/contracts/{draft['id']}/", {"notes": "Intrusión"}, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)

    def test_list_supports_search_filters_and_pagination(self):
        draft = self.create_draft().data["data"]
        self.authenticate()
        found = self.client.get("/api/contracts/?search=Ana&status=draft")
        missing = self.client.get("/api/contracts/?search=NoExiste")
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertEqual(found.data["data"]["results"][0]["id"], draft["id"])
        self.assertEqual(missing.data["data"]["count"], 0)


class ContractConfirmationTests(ContractAPITestCase):
    def test_confirmation_freezes_complete_snapshot_and_is_idempotent(self):
        draft = self.create_draft().data["data"]
        first = self.confirm(draft["id"], key="same-confirm-key")
        second = self.confirm(draft["id"], key="same-confirm-key")
        data = first.data["data"]
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["customer_name_snapshot"], "Ana Lagos")
        self.assertEqual(data["beneficiary_name_snapshot"], "Luis Lagos")
        self.assertEqual(data["plan_name_snapshot"], "Plan Serenidad")
        self.assertEqual(len(data["plan_items"]), 2)
        self.assertEqual(ContractActivity.objects.filter(action="confirmed").count(), 1)

    def test_confirmation_rejects_changed_catalog_price(self):
        draft = self.create_draft().data["data"]
        self.plan_a.base_price = Decimal("26000.00")
        self.plan_a.save(update_fields=("base_price", "updated_at"))
        response = self.confirm(draft["id"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Contract.objects.get(pk=draft["id"]).status, "draft")

    def test_historical_snapshot_survives_master_data_changes(self):
        draft = self.create_draft().data["data"]
        self.confirm(draft["id"])
        self.customer_a.first_name = "Nombre cambiado"
        self.customer_a.save()
        self.plan_a.name = "Plan cambiado"
        self.plan_a.save()
        self.service_a.name = "Servicio cambiado"
        self.service_a.save()
        self.authenticate()
        data = self.client.get(f"/api/contracts/{draft['id']}/").data["data"]
        self.assertEqual(data["customer_name_snapshot"], "Ana Lagos")
        self.assertEqual(data["plan_name_snapshot"], "Plan Serenidad")
        self.assertEqual(data["plan_items"][0]["service_name_snapshot"], "Sala velatoria")

    def test_pdf_uses_confirmed_snapshot(self):
        draft = self.create_draft().data["data"]
        self.confirm(draft["id"])
        self.authenticate()
        response = self.client.get(f"/api/contracts/{draft['id']}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("Contrato_CTR-000001.pdf", response["Content-Disposition"])
