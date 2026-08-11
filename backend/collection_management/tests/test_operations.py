from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from accounts.models import Role, RoleCode
from cash.services import create_cash_register, open_cash_session
from contracts.models import Contract
from contracts.tests.base import ContractAPITestCase
from payments.models import Payment

from collection_management.choices import AssignmentStatus, SettlementStatus, WorkSessionStatus
from collection_management.models import (
    CollectionAction, CollectionAssignment, CollectionOperationsAudit, CollectionRoute,
    CollectionRouteStop, CollectionZone, CollectorProfile, CollectorSettlement,
    CollectorSettlementPayment, CollectorWorkSession, RouteVisit,
)


class CollectionOperationsSprintTests(ContractAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        collector_role = Role.objects.get(code=RoleCode.COLLECTOR)
        cashier_role = Role.objects.get(code=RoleCode.CASHIER)
        cls.collector_a2 = cls.make_user("ops.collector.a2", cls.org_a, cls.branch_a, collector_role)
        cls.collector_b = cls.make_user("ops.collector.b", cls.org_b, cls.branch_b, collector_role)
        cls.cashier_a = cls.make_user("ops.cashier.a", cls.org_a, cls.branch_a, cashier_role)

    def active_contract(self, *, key="ops-contract", confirm_key="ops-confirm", **overrides):
        draft = self.create_draft(key=key, installment_amount="500.00", **overrides).data["data"]
        response = self.confirm(draft["id"], key=confirm_key)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return Contract.objects.get(pk=draft["id"])

    def assign(self, contract, collector=None):
        self.authenticate(self.admin_a)
        return self.client.post("/api/collection-assignments/", {
            "contract": contract.pk, "collector": (collector or self.collector_a).pk,
            "reason": "Asignación de prueba Sprint 7",
        }, format="json")

    def start(self, collector=None):
        self.authenticate(collector or self.collector_a)
        return self.client.post("/api/collector-work-sessions/start/", {"notes": "Inicio de pruebas"}, format="json")

    def pay(self, contract, amount, *, method="cash", key="ops-payment", user=None):
        self.authenticate(user or self.collector_a)
        payload = {"contract": contract.pk, "amount": str(amount), "payment_type": "installment", "payment_method": method}
        if method != "cash":
            payload["reference"] = f"REF-{key}"
        return self.client.post("/api/payments/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def closed_session_with_payments(self, *, difference=False):
        contract = self.active_contract()
        self.assertEqual(self.assign(contract).status_code, status.HTTP_201_CREATED)
        started = self.start()
        session_id = started.data["data"]["id"]
        self.assertEqual(self.pay(contract, "500.00", key="ops-cash").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.pay(contract, "300.00", method="transfer", key="ops-transfer").status_code, status.HTTP_201_CREATED)
        self.authenticate(self.collector_a)
        closed = self.client.post(f"/api/collector-work-sessions/{session_id}/close/", {"notes": "Fin"}, format="json")
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        preview = self.client.post("/api/collector-settlements/preview/", {"work_session": session_id}, format="json")
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        data = preview.data["data"]
        reported = "450.00" if difference else "500.00"
        notes = "Faltante documentado" if difference else "Entrega exacta"
        settlement = self.client.post("/api/collector-settlements/submit/", {
            "work_session": session_id, "reported_cash": reported, "notes": notes,
            "payment_fingerprint": data["payment_fingerprint"],
        }, format="json", HTTP_IDEMPOTENCY_KEY="settlement-submit-key")
        return contract, session_id, preview, settlement

    def test_assignment_creates_profile_and_single_active_owner(self):
        contract = self.active_contract()
        first = self.assign(contract)
        second = self.assign(contract, self.collector_a2)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        profile = CollectorProfile.objects.get(user=self.collector_a)
        self.assertRegex(profile.employee_code, r"^COB-\d{3}-\d{5}$")
        self.assertEqual(CollectionAssignment.objects.filter(contract=contract, status=AssignmentStatus.ACTIVE).count(), 1)

    def test_bulk_assignment_is_atomic_and_rejects_already_assigned_contract(self):
        first = self.active_contract(key="ops-bulk-a", confirm_key="ops-bulk-fa")
        second = self.active_contract(key="ops-bulk-b", confirm_key="ops-bulk-fb")
        self.assign(first)
        self.authenticate(self.admin_a)
        response = self.client.post("/api/collection-assignments/bulk/", {
            "contracts": [first.pk, second.pk], "collector": self.collector_a2.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(CollectionAssignment.objects.filter(contract=second).exists())

        response = self.client.post("/api/collection-assignments/bulk/", {
            "contracts": [second.pk, 9999999], "collector": self.collector_a2.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CollectionAssignment.objects.filter(contract=second).exists())

    def test_reassignment_closes_previous_and_preserves_linked_history(self):
        contract = self.active_contract()
        created = self.assign(contract).data["data"]
        self.authenticate(self.admin_a)
        response = self.client.post(f"/api/collection-assignments/{created['id']}/reassign/", {
            "collector": self.collector_a2.pk, "reason": "Balancear carga semanal",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        old = CollectionAssignment.objects.get(pk=created["id"])
        new = CollectionAssignment.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(old.status, AssignmentStatus.REASSIGNED)
        self.assertEqual(new.previous_assignment, old)
        self.assertEqual(new.collector, self.collector_a2)

    def test_assignment_tenant_and_branch_idor_are_rejected(self):
        contract = self.active_contract()
        foreign = self.assign(contract, self.collector_b)
        branch_other = self.assign(contract, self.seller_a2)
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(branch_other.status_code, {status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND})

    def test_collector_global_and_own_portfolios_only_return_active_assignments(self):
        assigned = self.active_contract(key="ops-own-a", confirm_key="ops-own-fa")
        unassigned = self.active_contract(key="ops-own-b", confirm_key="ops-own-fb")
        self.assign(assigned)
        self.authenticate(self.collector_a)
        own = self.client.get("/api/collector/portfolio/")
        global_view = self.client.get("/api/collections/portfolio/")
        for response in (own, global_view):
            ids = [item["contract_id"] for item in response.data["data"]["results"]]
            self.assertIn(assigned.pk, ids)
            self.assertNotIn(unassigned.pk, ids)

    def test_zone_route_stops_reorder_and_customer_uniqueness(self):
        second_customer = self.make_customer(
            self.org_a, self.branch_a, self.admin_a, "Rosa", "Campo", "0801199012399",
        )
        self.authenticate(self.admin_a)
        zone = self.client.post("/api/collection-zones/", {
            "branch": self.branch_a.pk, "code": "NORTE", "name": "Zona norte",
        }, format="json")
        self.assertEqual(zone.status_code, status.HTTP_201_CREATED)
        route = self.client.post("/api/collection-routes/", {
            "branch": self.branch_a.pk, "zone": zone.data["data"]["id"], "collector": self.collector_a.pk,
            "day_of_week": timezone.localdate().weekday(), "name": "Ruta matutina",
        }, format="json")
        route_id = route.data["data"]["id"]
        first = self.client.post(f"/api/collection-routes/{route_id}/stops/", {"customer": self.customer_a.pk}, format="json")
        second = self.client.post(f"/api/collection-routes/{route_id}/stops/", {"customer": second_customer.pk}, format="json")
        self.assertEqual((first.status_code, second.status_code), (status.HTTP_201_CREATED, status.HTTP_201_CREATED))
        stop_ids = [item["id"] for item in second.data["data"]["stops"]]
        reordered = self.client.post(f"/api/collection-routes/{route_id}/reorder/", {"stops": list(reversed(stop_ids))}, format="json")
        self.assertEqual([item["id"] for item in reordered.data["data"]["stops"]], list(reversed(stop_ids)))
        other_route = self.client.post("/api/collection-routes/", {"branch": self.branch_a.pk, "name": "Ruta duplicada"}, format="json")
        duplicate = self.client.post(f"/api/collection-routes/{other_route.data['data']['id']}/stops/", {"customer": self.customer_a.pk}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_not_found_route_visit_creates_collection_action(self):
        contract = self.active_contract()
        self.assign(contract)
        route = CollectionRoute.objects.create(
            organization=self.org_a, branch=self.branch_a, collector=self.collector_a,
            name="Ruta visita", created_by=self.admin_a,
        )
        stop = CollectionRouteStop.objects.create(route=route, customer=self.customer_a, position=1)
        self.authenticate(self.collector_a)
        response = self.client.post(f"/api/collector/route-stops/{stop.pk}/visit/", {
            "status": "not_found", "notes": "No se encontró al titular",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visit = RouteVisit.objects.get(route_stop=stop)
        self.assertIsNotNone(visit.collection_action_id)
        self.assertEqual(CollectionAction.objects.get(pk=visit.collection_action_id).outcome, "not_found")

    def test_collector_payment_requires_assignment_and_open_session(self):
        contract = self.active_contract()
        no_assignment = self.pay(contract, "100.00", key="ops-no-assignment")
        self.assertEqual(no_assignment.status_code, status.HTTP_404_NOT_FOUND)
        self.assign(contract)
        no_session = self.pay(contract, "100.00", key="ops-no-session")
        self.assertEqual(no_session.status_code, status.HTTP_400_BAD_REQUEST)
        self.start()
        accepted = self.pay(contract, "100.00", key="ops-with-session")
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(pk=accepted.data["data"]["id"])
        self.assertEqual(payment.collector_session.collector, self.collector_a)

    def test_admin_and_cashier_payment_flows_do_not_require_collector_session(self):
        contract = self.active_contract()
        admin_payment = self.pay(contract, "100.00", key="ops-admin-pay", user=self.admin_a)
        cash_register = create_cash_register(
            self.org_a, self.branch_a, self.admin_a, "Caja de prueba Sprint 8"
        )
        open_cash_session(cash_register, self.cashier_a, "0.00", "", "ops-cashier-open")
        cashier_payment = self.pay(contract, "100.00", key="ops-cashier-pay", user=self.cashier_a)
        self.assertEqual((admin_payment.status_code, cashier_payment.status_code), (201, 201))
        self.assertFalse(Payment.objects.exclude(collector_session=None).exists())

    def test_only_one_open_and_one_daily_work_session_are_allowed(self):
        first = self.start()
        second = self.start()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.authenticate(self.collector_a)
        self.client.post(f"/api/collector-work-sessions/{first.data['data']['id']}/close/", {}, format="json")
        third = self.start()
        self.assertEqual(third.status_code, status.HTTP_409_CONFLICT)

    def test_close_session_summary_uses_confirmed_payments_by_method(self):
        contract = self.active_contract()
        self.assign(contract); started = self.start(); session_id = started.data["data"]["id"]
        self.pay(contract, "200.00", key="ops-summary-cash")
        self.pay(contract, "100.00", method="transfer", key="ops-summary-transfer")
        self.authenticate(self.collector_a)
        closed = self.client.post(f"/api/collector-work-sessions/{session_id}/close/", {}, format="json")
        summary = closed.data["data"]["summary"]
        self.assertEqual(Decimal(summary["total_collected"]), Decimal("300.00"))
        self.assertEqual(Decimal(summary["expected_cash"]), Decimal("200.00"))
        self.assertEqual(summary["payment_count"], 2)

    def test_settlement_formula_snapshots_and_idempotency(self):
        _, session_id, preview, response = self.closed_session_with_payments()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        settlement = CollectorSettlement.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(settlement.total_collected, Decimal("800.00"))
        self.assertEqual(settlement.expected_cash, Decimal("500.00"))
        self.assertEqual(settlement.reported_cash, Decimal("500.00"))
        self.assertEqual(settlement.difference, Decimal("0.00"))
        self.assertEqual(CollectorSettlementPayment.objects.filter(settlement=settlement).count(), 2)
        retry = self.client.post("/api/collector-settlements/submit/", {
            "work_session": session_id, "reported_cash": "500.00", "notes": "Entrega exacta",
            "payment_fingerprint": preview.data["data"]["payment_fingerprint"],
        }, format="json", HTTP_IDEMPOTENCY_KEY="settlement-submit-key")
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.data["data"]["id"], settlement.pk)

    def test_settlement_difference_requires_note_and_acceptance_is_audited(self):
        _, _, _, response = self.closed_session_with_payments(difference=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        settlement_id = response.data["data"]["id"]
        self.assertEqual(Decimal(response.data["data"]["difference"]), Decimal("-50.00"))
        self.authenticate(self.admin_a)
        accepted = self.client.post(f"/api/collector-settlements/{settlement_id}/accept/", {
            "reason": "Diferencia validada con el cobrador",
        }, format="json")
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(CollectorSettlement.objects.get(pk=settlement_id).status, SettlementStatus.ACCEPTED)
        self.assertTrue(CollectionOperationsAudit.objects.filter(settlement_id=settlement_id, event="settlement_accepted").exists())

    def test_short_difference_note_and_stale_fingerprint_are_rejected(self):
        contract = self.active_contract(); self.assign(contract); started = self.start(); session_id = started.data["data"]["id"]
        self.pay(contract, "100.00", key="ops-fingerprint")
        self.authenticate(self.collector_a)
        self.client.post(f"/api/collector-work-sessions/{session_id}/close/", {}, format="json")
        preview = self.client.post("/api/collector-settlements/preview/", {"work_session": session_id}, format="json").data["data"]
        short = self.client.post("/api/collector-settlements/submit/", {
            "work_session": session_id, "reported_cash": "90.00", "notes": "no",
            "payment_fingerprint": preview["payment_fingerprint"],
        }, format="json", HTTP_IDEMPOTENCY_KEY="ops-short-note")
        stale = self.client.post("/api/collector-settlements/submit/", {
            "work_session": session_id, "reported_cash": "100.00", "notes": "correcto",
            "payment_fingerprint": "0" * 64,
        }, format="json", HTTP_IDEMPOTENCY_KEY="ops-stale-fingerprint")
        self.assertEqual(short.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)

    def test_settlement_cannot_include_same_payment_twice(self):
        _, _, _, response = self.closed_session_with_payments()
        settlement = CollectorSettlement.objects.get(pk=response.data["data"]["id"])
        item = settlement.payment_items.first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CollectorSettlementPayment.objects.create(
                    settlement=settlement, payment=item.payment, payment_number_snapshot="DUP",
                    receipt_number_snapshot="DUP", customer_name_snapshot="DUP",
                    contract_number_snapshot="DUP", payment_method_snapshot="cash", amount_snapshot="1.00",
                )

    def test_settled_payment_void_keeps_snapshot_and_adds_audit(self):
        _, _, _, response = self.closed_session_with_payments()
        settlement = CollectorSettlement.objects.get(pk=response.data["data"]["id"])
        payment = settlement.payment_items.first().payment
        self.authenticate(self.admin_a)
        voided = self.client.post(f"/api/payments/{payment.pk}/void/", {"reason": "Corrección posterior al cierre"}, format="json")
        self.assertEqual(voided.status_code, status.HTTP_200_OK)
        self.assertEqual(settlement.payment_items.count(), 2)
        self.assertTrue(CollectionOperationsAudit.objects.filter(payment=payment, event="settled_payment_voided").exists())

    def test_permissions_and_tenant_isolation_for_operations(self):
        self.authenticate(self.inventory_a)
        self.assertEqual(self.client.get("/api/collectors/").status_code, status.HTTP_403_FORBIDDEN)
        self.authenticate(self.admin_b)
        self.assertEqual(self.client.get(f"/api/collectors/{self.collector_a.pk}/").status_code, status.HTTP_404_NOT_FOUND)
        self.authenticate(self.collector_a)
        self.assertEqual(self.client.get("/api/collection-assignments/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/collector-settlements/").status_code, status.HTTP_200_OK)

    def test_real_excel_and_pdf_exports(self):
        _, _, _, response = self.closed_session_with_payments()
        settlement_id = response.data["data"]["id"]
        self.authenticate(self.admin_a)
        productivity = self.client.get("/api/collectors/productivity/export.xlsx")
        settlements = self.client.get("/api/collector-settlements/export.xlsx")
        pdf = self.client.get(f"/api/collector-settlements/{settlement_id}/pdf/")
        self.assertTrue(productivity.content.startswith(b"PK"))
        self.assertTrue(settlements.content.startswith(b"PK"))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertGreater(len(pdf.content), 2000)

    def test_options_and_collector_metrics_are_available_without_writes(self):
        self.authenticate(self.admin_a)
        options = self.client.get("/api/collection-operations/options/")
        metrics = self.client.get(f"/api/collectors/{self.collector_a.pk}/metrics/")
        self.assertEqual((options.status_code, metrics.status_code), (200, 200))
        self.assertIn("visit_statuses", options.data["data"])
        self.assertEqual(metrics.data["data"]["assigned_contracts"], 0)
