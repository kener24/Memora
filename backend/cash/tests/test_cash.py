from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from accounts.models import Role, RoleCode
from collection_management.choices import AssignmentStatus, SettlementStatus, WorkSessionStatus
from collection_management.models import CollectionAssignment, CollectorSettlement, CollectorWorkSession
from contracts.models import Contract
from contracts.tests.base import ContractAPITestCase
from payments.choices import PaymentStatus
from payments.models import Payment

from cash.choices import CashMovementStatus, CashSessionStatus
from cash.models import (
    CashAudit, CashCount, CashMovement, CashRegister, CashSession,
    CollectorSettlementReception,
)


class CashSprintTests(ContractAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cashier_role = Role.objects.get(code=RoleCode.CASHIER)
        cls.cashier_a = cls.make_user("cash.cashier.a", cls.org_a, cls.branch_a, cashier_role)
        cls.cashier_a2 = cls.make_user("cash.cashier.a2", cls.org_a, cls.branch_a2, cashier_role)
        cls.cashier_b = cls.make_user("cash.cashier.b", cls.org_b, cls.branch_b, cashier_role)
        cls.register_a = CashRegister.objects.create(
            organization=cls.org_a, branch=cls.branch_a, code="CAJ-900",
            name="Caja Principal", created_by=cls.admin_a,
        )
        cls.register_a2 = CashRegister.objects.create(
            organization=cls.org_a, branch=cls.branch_a2, code="CAJ-901",
            name="Caja Norte", created_by=cls.admin_a,
        )
        cls.register_b = CashRegister.objects.create(
            organization=cls.org_b, branch=cls.branch_b, code="CAJ-900",
            name="Caja Serena", created_by=cls.admin_b,
        )

    def active_contract(self, *, key="cash-contract", confirm_key="cash-confirm", **overrides):
        draft = self.create_draft(key=key, installment_amount="500.00", **overrides).data["data"]
        response = self.confirm(draft["id"], key=confirm_key)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return Contract.objects.get(pk=draft["id"])

    def open_session(self, *, user=None, register=None, opening="2000.00", key="cash-open-key"):
        user = user or self.cashier_a
        register = register or self.register_a
        self.authenticate(user)
        return self.client.post("/api/cash/sessions/open/", {
            "cash_register": register.pk, "opening_cash": opening, "notes": "Apertura operativa",
        }, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def manual(self, session_id, *, direction="in", amount="100.00", method="cash",
               category=None, key="cash-manual-key", user=None, description="Movimiento operativo autorizado"):
        category = category or ("extraordinary_income" if direction == "in" else "operating_expense")
        self.authenticate(user or self.cashier_a)
        return self.client.post("/api/cash/movements/", {
            "cash_session": session_id, "direction": direction, "category": category,
            "amount": amount, "payment_method": method, "description": description,
            "reference": f"REF-{key}",
        }, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def pay(self, contract, *, amount="500.00", method="cash", key="cash-payment", user=None):
        self.authenticate(user or self.cashier_a)
        payload = {
            "contract": contract.pk, "amount": amount, "payment_type": "installment",
            "payment_method": method,
        }
        if method != "cash":
            payload["reference"] = f"TRX-{key}"
        return self.client.post(
            "/api/payments/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key
        )

    def accepted_settlement(self, *, suffix="001", expected="1000.00", reported="950.00"):
        work = CollectorWorkSession.objects.create(
            organization=self.org_a, branch=self.branch_a, collector=self.collector_a,
            status=WorkSessionStatus.CLOSED, ended_at=timezone.now(),
            opened_by=self.collector_a, closed_by=self.collector_a,
        )
        return CollectorSettlement.objects.create(
            organization=self.org_a, branch=self.branch_a, collector=self.collector_a,
            work_session=work, settlement_number=f"LIQ-CASH-{suffix}",
            total_collected=Decimal(expected), expected_cash=Decimal(expected),
            reported_cash=Decimal(reported), difference=Decimal(reported) - Decimal(expected),
            payment_fingerprint="a" * 64, status=SettlementStatus.ACCEPTED,
            submitted_by=self.collector_a, reviewed_by=self.admin_a,
            reviewed_at=timezone.now(), notes="Diferencia documentada",
        )

    def count(self, session_id, *, denominations=None, total=None, reason="", key="cash-count-key"):
        self.authenticate(self.cashier_a)
        payload = {"difference_reason": reason}
        if denominations is not None:
            payload["denominations"] = denominations
        if total is not None:
            payload["counted_cash"] = total
        return self.client.post(
            f"/api/cash/sessions/{session_id}/count/", payload, format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def close(self, session_id, count_id, *, key="cash-close-key"):
        self.authenticate(self.cashier_a)
        return self.client.post(
            f"/api/cash/sessions/{session_id}/close/",
            {"cash_count": count_id, "notes": "Cierre confirmado"}, format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_register_management_code_status_and_no_delete(self):
        self.authenticate(self.admin_a)
        created = self.client.post("/api/cash/registers/", {
            "branch": self.branch_a.pk, "name": "Caja Recepción", "description": "Mostrador",
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertRegex(created.data["data"]["code"], r"^CAJ-\d{3}$")
        item_id = created.data["data"]["id"]
        disabled = self.client.patch(f"/api/cash/registers/{item_id}/", {"is_active": False}, format="json")
        deleted = self.client.delete(f"/api/cash/registers/{item_id}/")
        self.assertFalse(disabled.data["data"]["is_active"])
        self.assertEqual(deleted.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(CashAudit.objects.filter(cash_register_id=item_id).exists())

    def test_opening_is_idempotent_and_blocks_double_register_and_cashier_sessions(self):
        first = self.open_session()
        retry = self.open_session()
        other_register = CashRegister.objects.create(
            organization=self.org_a, branch=self.branch_a, code="CAJ-902",
            name="Caja Alterna", created_by=self.admin_a,
        )
        second = self.open_session(register=other_register, key="cash-second-open")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["data"]["id"], retry.data["data"]["id"])
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(CashSession.objects.filter(status=CashSessionStatus.OPEN).count(), 1)
        self.assertEqual(first.data["data"]["opening_cash"], "2000.00")

    def test_inactive_or_cross_branch_register_cannot_open(self):
        self.register_a.is_active = False
        self.register_a.save(update_fields=("is_active",))
        inactive = self.open_session()
        foreign_branch = self.open_session(
            register=self.register_a2, key="cross-branch-open"
        )
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign_branch.status_code, status.HTTP_404_NOT_FOUND)

    def test_cashier_requires_open_session_for_payment(self):
        contract = self.active_contract()
        response = self.pay(contract)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

    def test_cash_and_transfer_payments_create_one_movement_but_only_cash_changes_expected(self):
        session = self.open_session().data["data"]
        contract = self.active_contract()
        cash = self.pay(contract, key="cash-pay-physical")
        transfer = self.pay(contract, method="transfer", key="cash-pay-transfer")
        retry = self.pay(contract, method="transfer", key="cash-pay-transfer")
        self.assertEqual((cash.status_code, transfer.status_code, retry.status_code), (201, 201, 200))
        self.assertEqual(CashMovement.objects.count(), 2)
        cash_move = CashMovement.objects.get(payment_id=cash.data["data"]["id"])
        transfer_move = CashMovement.objects.get(payment_id=transfer.data["data"]["id"])
        self.assertTrue(cash_move.affects_cash)
        self.assertFalse(transfer_move.affects_cash)
        self.authenticate(self.cashier_a)
        current = self.client.get("/api/cash/sessions/current/").data["data"]
        self.assertEqual(current["summary"]["expected_cash"], Decimal("2500.00"))
        self.assertEqual(current["summary"]["method_totals"]["transfer"], Decimal("500.00"))
        self.assertEqual(current["id"], session["id"])

    def test_collector_cash_payment_never_enters_general_cash(self):
        contract = self.active_contract()
        CollectionAssignment.objects.create(
            organization=self.org_a, branch=self.branch_a, contract=contract,
            collector=self.collector_a, assigned_by=self.admin_a,
            status=AssignmentStatus.ACTIVE,
        )
        CollectorWorkSession.objects.create(
            organization=self.org_a, branch=self.branch_a, collector=self.collector_a,
            opened_by=self.collector_a,
        )
        response = self.pay(contract, user=self.collector_a, key="collector-cash-no-box")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(CashMovement.objects.filter(payment_id=response.data["data"]["id"]).exists())

    def test_manual_income_expense_idempotency_non_cash_and_excess_rejection(self):
        session_id = self.open_session(opening="500.00").data["data"]["id"]
        income = self.manual(session_id, amount="200.00", key="manual-income-once")
        retry = self.manual(session_id, amount="200.00", key="manual-income-once")
        transfer = self.manual(
            session_id, amount="300.00", method="transfer", key="manual-income-transfer"
        )
        expense = self.manual(
            session_id, direction="out", amount="100.00", key="manual-expense"
        )
        excessive = self.manual(
            session_id, direction="out", amount="601.00", key="manual-excess"
        )
        self.assertEqual((income.status_code, retry.status_code, transfer.status_code, expense.status_code), (201, 200, 201, 201))
        self.assertEqual(excessive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CashMovement.objects.count(), 3)
        self.authenticate(self.cashier_a)
        current = self.client.get("/api/cash/sessions/current/").data["data"]
        self.assertEqual(current["summary"]["expected_cash"], Decimal("600.00"))
        self.assertEqual(current["summary"]["financial_in"], Decimal("500.00"))

    def test_manual_movement_void_and_payment_void_recalculate_open_cash(self):
        session_id = self.open_session(opening="500.00").data["data"]["id"]
        manual = self.manual(session_id, amount="100.00", key="void-manual").data["data"]
        self.authenticate(self.cashier_a)
        voided = self.client.post(
            f"/api/cash/movements/{manual['id']}/void/", {"reason": "Ingreso registrado por error"},
            format="json",
        )
        contract = self.active_contract()
        payment = self.pay(contract, key="void-payment-cash").data["data"]
        self.authenticate(self.admin_a)
        payment_void = self.client.post(
            f"/api/payments/{payment['id']}/void/", {"reason": "Pago duplicado en ventanilla"},
            format="json",
        )
        self.assertEqual((voided.status_code, payment_void.status_code), (200, 200))
        self.assertEqual(CashMovement.objects.filter(status=CashMovementStatus.VOIDED).count(), 2)
        self.authenticate(self.cashier_a)
        current = self.client.get("/api/cash/sessions/current/").data["data"]
        self.assertEqual(current["summary"]["expected_cash"], Decimal("500.00"))

    def test_settlement_reception_uses_actual_cash_and_preserves_two_differences(self):
        session_id = self.open_session(opening="0.00").data["data"]["id"]
        settlement = self.accepted_settlement()
        self.authenticate(self.cashier_a)
        payload = {
            "cash_session": session_id, "collector_settlement": settlement.pk,
            "cash_received_by_cashier": "900.00", "notes": "Faltante verificado al recibir",
        }
        first = self.client.post(
            "/api/cash/settlement-receptions/", payload, format="json",
            HTTP_IDEMPOTENCY_KEY="receive-settlement-once",
        )
        retry = self.client.post(
            "/api/cash/settlement-receptions/", payload, format="json",
            HTTP_IDEMPOTENCY_KEY="receive-settlement-once",
        )
        self.assertEqual((first.status_code, retry.status_code), (201, 200))
        data = first.data["data"]
        self.assertEqual(data["collector_difference"], "-50.00")
        self.assertEqual(data["delivery_difference"], "-50.00")
        self.assertEqual(data["total_difference_vs_expected"], "-100.00")
        self.assertEqual(CashMovement.objects.get().amount, Decimal("900.00"))
        self.assertEqual(CollectorSettlementReception.objects.count(), 1)
        duplicate = self.client.post(
            "/api/cash/settlement-receptions/", payload, format="json",
            HTTP_IDEMPOTENCY_KEY="receive-settlement-again",
        )
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)

    def test_count_denominations_is_backend_authoritative_and_exact(self):
        session_id = self.open_session(opening="1500.00").data["data"]["id"]
        response = self.count(session_id, denominations=[
            {"denomination": "500.00", "quantity": 2},
            {"denomination": "100.00", "quantity": 3},
            {"denomination": "50.00", "quantity": 4},
        ])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["counted_cash"], "1500.00")
        self.assertEqual(response.data["data"]["difference"], "0.00")
        self.assertEqual(sum(Decimal(row["subtotal"]) for row in response.data["data"]["denominations"]), Decimal("1500.00"))

    def test_shortage_surplus_require_reason_and_create_distinct_counts(self):
        session_id = self.open_session(opening="1500.00").data["data"]["id"]
        denied = self.count(session_id, total="1450.00", key="count-short-no-note")
        shortage = self.count(
            session_id, total="1450.00", reason="Faltante bajo investigación", key="count-short"
        )
        surplus = self.count(
            session_id, total="1550.00", reason="Sobrante documentado", key="count-surplus"
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(shortage.data["data"]["difference"], "-50.00")
        self.assertEqual(surplus.data["data"]["difference"], "50.00")
        self.assertEqual(CashCount.objects.count(), 2)

    def test_stale_count_blocks_close_until_recount(self):
        session_id = self.open_session(opening="1000.00").data["data"]["id"]
        first = self.count(session_id, total="1000.00", key="count-before-change").data["data"]
        self.manual(session_id, amount="100.00", key="movement-after-count")
        stale = self.close(session_id, first["id"], key="close-stale")
        recount = self.count(session_id, total="1100.00", key="count-after-change").data["data"]
        closed = self.close(session_id, recount["id"], key="close-after-recount")
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(closed.status_code, status.HTTP_200_OK)

    def test_close_freezes_snapshots_blocks_post_close_and_payment_void(self):
        session_id = self.open_session(opening="1000.00").data["data"]["id"]
        contract = self.active_contract()
        payment = self.pay(contract, key="closed-session-payment").data["data"]
        count = self.count(session_id, total="1500.00").data["data"]
        closed = self.close(session_id, count["id"])
        post_movement = self.manual(session_id, amount="10.00", key="post-close-move")
        post_count = self.count(session_id, total="1500.00", key="post-close-count")
        self.authenticate(self.admin_a)
        payment_void = self.client.post(
            f"/api/payments/{payment['id']}/void/", {"reason": "Intento tras cierre"}, format="json"
        )
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertEqual(post_movement.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(post_count.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(payment_void.status_code, status.HTTP_409_CONFLICT)
        session = CashSession.objects.get(pk=session_id)
        self.assertEqual(session.expected_cash_snapshot, Decimal("1500.00"))
        self.assertEqual(session.counted_cash_snapshot, Decimal("1500.00"))
        self.assertEqual(Payment.objects.get(pk=payment["id"]).status, PaymentStatus.CONFIRMED)

    def test_permissions_multi_tenant_branch_and_idor(self):
        self.authenticate(self.admin_a)
        foreign = self.client.get(f"/api/cash/registers/{self.register_b.pk}/")
        self.authenticate(self.cashier_a)
        cross_branch = self.client.post("/api/cash/sessions/open/", {
            "cash_register": self.register_a2.pk, "opening_cash": "0.00",
        }, format="json", HTTP_IDEMPOTENCY_KEY="branch-idor-open")
        self.authenticate(self.collector_a)
        collector = self.client.get("/api/cash/options/")
        self.authenticate(self.inventory_a)
        inventory = self.client.get("/api/cash/registers/")
        self.authenticate(self.accountant_a)
        accountant_read = self.client.get("/api/cash/registers/")
        accountant_write = self.client.post("/api/cash/movements/", {}, format="json")
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(cross_branch.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(collector.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(inventory.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(accountant_read.status_code, status.HTTP_200_OK)
        self.assertEqual(accountant_write.status_code, status.HTTP_403_FORBIDDEN)

    def test_filtered_movement_totals_use_full_queryset_not_page(self):
        session_id = self.open_session().data["data"]["id"]
        self.manual(session_id, amount="100.00", key="totals-in")
        self.manual(session_id, direction="out", amount="40.00", key="totals-out")
        self.authenticate(self.cashier_a)
        response = self.client.get("/api/cash/movements/?direction=out&page_size=1")
        totals = response.data["data"]["totals"]
        self.assertEqual(totals["total_out"], Decimal("40.00"))
        self.assertEqual(totals["net"], Decimal("-40.00"))

    def test_movement_list_queries_remain_bounded_with_multiple_rows(self):
        session_id = self.open_session().data["data"]["id"]
        for index in range(5):
            self.manual(session_id, amount="10.00", key=f"bounded-query-{index}")
        self.authenticate(self.cashier_a)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/cash/movements/?page_size=100")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 5)
        self.assertLessEqual(len(queries), 12)

    def test_dashboard_separates_payments_cash_and_pending_collector_money(self):
        self.open_session(opening="0.00")
        contract = self.active_contract()
        self.pay(contract, amount="500.00", method="transfer", key="dashboard-transfer")
        self.accepted_settlement(expected="800.00", reported="750.00")
        self.authenticate(self.cashier_a)
        response = self.client.get("/api/cash/dashboard/")
        data = response.data["data"]
        self.assertEqual(data["payment_total_today"], Decimal("500.00"))
        self.assertEqual(data["cash_received_today"], Decimal("0.00"))
        self.assertEqual(data["payment_methods"]["transfer"], Decimal("500.00"))
        self.assertEqual(data["pending_settlements"], 1)
        self.assertEqual(data["pending_settlement_cash"], Decimal("750.00"))

    def test_pdf_excel_and_historical_detail_are_real_files(self):
        session_id = self.open_session(opening="1000.00").data["data"]["id"]
        self.manual(session_id, amount="100.00", key="report-movement")
        count = self.count(session_id, total="1100.00").data["data"]
        self.close(session_id, count["id"])
        self.authenticate(self.admin_a)
        detail = self.client.get(f"/api/cash/sessions/{session_id}/")
        pdf = self.client.get(f"/api/cash/sessions/{session_id}/closing-pdf/")
        excel = self.client.get("/api/cash/movements/export.xlsx")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(excel.status_code, status.HTTP_200_OK)
        self.assertTrue(excel.content.startswith(b"PK"))
