from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from contracts.models import Contract
from contracts.tests.base import ContractAPITestCase
from installments.models import Installment
from payments.models import Payment

from collection_management.models import CollectionAction, CollectionAudit, PaymentPromise
from collection_management.services import aging_summary, portfolio_queryset, portfolio_row


class CollectionSprintTests(ContractAPITestCase):
    def active_contract(self, *, key="collection-contract", confirm_key="collection-confirm", user=None, **overrides):
        draft = self.create_draft(user=user, key=key, **overrides).data["data"]
        confirmed = self.confirm(draft["id"], user=user, key=confirm_key)
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        return Contract.objects.get(pk=draft["id"])

    def set_first_due(self, contract, days_ago):
        installment = Installment.objects.filter(contract=contract).order_by("installment_number").first()
        installment.due_date = timezone.localdate() - timedelta(days=days_ago)
        installment.save(update_fields=("due_date",))
        return installment

    def create_action(self, contract, **overrides):
        self.authenticate()
        payload = {
            "contract": contract.pk, "action_type": "phone_call", "outcome": "contacted",
            "notes": "Cliente contactado y saldo explicado.",
        }
        payload.update(overrides)
        return self.client.post("/api/collections/collection-actions/", payload, format="json")

    def pay(self, contract, amount, key="collection-payment"):
        self.authenticate()
        return self.client.post("/api/payments/", {
            "contract": contract.pk, "amount": str(amount), "payment_type": "installment", "payment_method": "cash",
        }, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def test_status_and_priority_are_derived_from_oldest_pending_installment(self):
        overdue = self.active_contract()
        self.set_first_due(overdue, 35)
        item = portfolio_queryset(self.admin_a).get(pk=overdue.pk)
        row = portfolio_row(item)
        self.assertEqual(row["collection_status"], "overdue")
        self.assertEqual(row["priority"], "high")
        self.assertEqual(row["days_overdue"], 35)
        self.assertEqual(row["overdue_amount"], Decimal("1500.00"))
        self.assertEqual(row["balance"], Decimal("23000.00"))
        self.assertEqual(row["upcoming_amount"], Decimal("21500.00"))

    def test_current_due_soon_and_severe_boundaries(self):
        current = self.active_contract(key="current-c", confirm_key="current-f")
        self.assertEqual(portfolio_row(portfolio_queryset(self.admin_a).get(pk=current.pk))["collection_status"], "current")
        due_installment = Installment.objects.filter(contract=current).order_by("installment_number").first()
        due_installment.due_date = timezone.localdate() + timedelta(days=7)
        due_installment.save(update_fields=("due_date",))
        self.assertEqual(portfolio_row(portfolio_queryset(self.admin_a).get(pk=current.pk))["collection_status"], "due_soon")
        self.set_first_due(current, 91)
        severe_row = portfolio_row(portfolio_queryset(self.admin_a).get(pk=current.pk))
        self.assertEqual((severe_row["collection_status"], severe_row["priority"]), ("severely_overdue", "critical"))

    def test_partial_payment_reduces_overdue_and_total_without_manual_debt(self):
        contract = self.active_contract()
        self.set_first_due(contract, 10)
        self.assertEqual(self.pay(contract, "500.00").status_code, status.HTTP_201_CREATED)
        row = portfolio_row(portfolio_queryset(self.admin_a).get(pk=contract.pk))
        self.assertEqual(row["total_paid"], Decimal("500.00"))
        self.assertEqual(row["balance"], Decimal("22500.00"))
        self.assertEqual(row["overdue_amount"], Decimal("1000.00"))

    def test_aging_uses_each_installment_and_exact_buckets(self):
        contract = self.active_contract()
        installments = list(Installment.objects.filter(contract=contract).order_by("installment_number")[:5])
        for item, days in zip(installments, (1, 31, 61, 91, 121), strict=True):
            item.due_date = timezone.localdate() - timedelta(days=days)
            item.save(update_fields=("due_date",))
        result = aging_summary(self.admin_a)
        self.assertEqual([bucket["installments"] for bucket in result["buckets"]], [1, 1, 1, 1, 1])
        self.assertEqual(result["total_overdue"], Decimal("7500.00"))

    def test_portfolio_api_filters_search_ordering_and_filtered_totals(self):
        contract = self.active_contract()
        self.set_first_due(contract, 20)
        self.authenticate()
        response = self.client.get(f"/api/collections/portfolio/?search={contract.contract_number}&status=overdue&ordering=-balance")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(Decimal(data["totals"]["pending"]), Decimal("23000.00"))
        self.assertEqual(Decimal(data["totals"]["overdue"]), Decimal("1500.00"))

    def test_summary_counts_confirmed_month_payments_only(self):
        contract = self.active_contract()
        self.set_first_due(contract, 5)
        self.pay(contract, "400.00")
        self.authenticate()
        result = self.client.get("/api/collections/portfolio/summary/")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(result.data["data"]["collected_this_month"]), Decimal("400.00"))
        self.assertEqual(result.data["data"]["overdue_customers"], 1)

    def test_action_is_immutable_audited_and_void_requires_authority(self):
        contract = self.active_contract()
        created = self.create_action(contract, next_follow_up_date=str(timezone.localdate()))
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        action_id = created.data["data"]["id"]
        self.assertEqual(CollectionAudit.objects.filter(action_id=action_id, event="action_created").count(), 1)
        self.authenticate(self.collector_a)
        denied = self.client.post(f"/api/collections/collection-actions/{action_id}/void/", {"reason": "Intento sin permiso"}, format="json")
        self.authenticate()
        allowed = self.client.post(f"/api/collections/collection-actions/{action_id}/void/", {"reason": "Registro duplicado"}, format="json")
        update = self.client.patch(f"/api/collections/collection-actions/{action_id}/", {"notes": "alterado"}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(update.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(CollectionAction.objects.get(pk=action_id).status, "voided")

    def test_promise_one_pending_effective_broken_and_audited_resolution(self):
        contract = self.active_contract()
        future = timezone.localdate() + timedelta(days=2)
        created = self.create_action(contract, outcome="promise_to_pay", promised_amount="500.00", promised_date=str(future))
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        promise = PaymentPromise.objects.get(contract=contract)
        duplicate = self.client.post("/api/collections/payment-promises/", {
            "contract": contract.pk, "promised_amount": "200.00", "promised_date": str(future),
        }, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        promise.promised_date = timezone.localdate() - timedelta(days=1)
        promise.save(update_fields=("promised_date",))
        self.assertEqual(PaymentPromise.objects.get(pk=promise.pk).effective_status, "broken")
        broken = self.client.post(f"/api/collections/payment-promises/{promise.pk}/break/", {"reason": "No realizó el pago acordado"}, format="json")
        self.assertEqual(broken.status_code, status.HTTP_200_OK)
        self.assertEqual(CollectionAudit.objects.filter(promise=promise, event="promise_broken").count(), 1)

    def test_promise_fulfillment_reuses_confirmed_payment(self):
        contract = self.active_contract()
        promise_response = self.client.post("/api/collections/payment-promises/", {
            "contract": contract.pk, "promised_amount": "300.00", "promised_date": str(timezone.localdate()),
        }, format="json")
        promise_id = promise_response.data["data"]["id"]
        payment = self.pay(contract, "300.00", key="promise-payment").data["data"]
        result = self.client.post(f"/api/collections/payment-promises/{promise_id}/fulfill/", {"payment": payment["id"]}, format="json")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        promise = PaymentPromise.objects.get(pk=promise_id)
        self.assertEqual(promise.fulfilled_payment_id, payment["id"])
        self.assertEqual(promise.status, "fulfilled")

    def test_follow_up_agenda_groups_overdue_today_and_upcoming(self):
        contract = self.active_contract()
        for index, offset in enumerate((-1, 0, 3)):
            self.create_action(contract, notes=f"Seguimiento {index}", next_follow_up_date=str(timezone.localdate() + timedelta(days=offset)))
        response = self.client.get("/api/collections/collection-follow-ups/")
        self.assertEqual([len(response.data["data"][key]) for key in ("overdue", "today", "upcoming")], [1, 1, 1])

    def test_tenant_and_branch_idor_are_enforced_for_all_operational_objects(self):
        foreign = self.active_contract()
        action = self.create_action(foreign).data["data"]
        self.authenticate(self.admin_b)
        self.assertEqual(self.client.get(f"/api/collections/portfolio/contracts/{foreign.pk}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f"/api/collections/collection-actions/{action['id']}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post("/api/collections/collection-actions/", {
            "contract": foreign.pk, "action_type": "phone_call", "outcome": "contacted", "notes": "Ataque externo",
        }, format="json").status_code, status.HTTP_404_NOT_FOUND)
        branch_contract = self.active_contract(
            key="branch-c", confirm_key="branch-f", user=self.admin_a, branch=self.branch_a2.pk,
            customer=self.customer_a2.pk, beneficiary=self.beneficiary_a2.pk, plan=self.plan_a2.pk, seller=self.seller_a2.pk,
        )
        self.authenticate(self.collector_a)
        results = self.client.get("/api/collections/portfolio/").data["data"]["results"]
        self.assertNotIn(branch_contract.pk, [item["contract_id"] for item in results])

    def test_inventory_denied_and_collector_can_create_but_not_export(self):
        contract = self.active_contract()
        self.authenticate(self.inventory_a)
        self.assertEqual(self.client.get("/api/collections/portfolio/").status_code, status.HTTP_403_FORBIDDEN)
        self.authenticate(self.collector_a)
        self.assertEqual(self.client.post("/api/collections/collection-actions/", {
            "contract": contract.pk, "action_type": "whatsapp", "outcome": "no_answer", "notes": "No respondió al mensaje",
        }, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get("/api/collections/portfolio/export.xlsx").status_code, status.HTTP_403_FORBIDDEN)

    def test_real_excel_and_pdf_exports_respect_filters(self):
        contract = self.active_contract()
        self.set_first_due(contract, 10)
        self.authenticate()
        xlsx = self.client.get(f"/api/collections/portfolio/export.xlsx?search={contract.contract_number}")
        pdf = self.client.get(f"/api/collections/portfolio/export.pdf?search={contract.contract_number}")
        self.assertEqual(xlsx.status_code, status.HTTP_200_OK)
        self.assertTrue(xlsx.content.startswith(b"PK"))
        self.assertGreater(len(xlsx.content), 5000)
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_portfolio_list_query_count_is_constant(self):
        for index in range(3):
            self.active_contract(key=f"query-c-{index}", confirm_key=f"query-f-{index}")
        self.authenticate()
        with self.assertNumQueries(5):
            response = self.client.get("/api/collections/portfolio/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
