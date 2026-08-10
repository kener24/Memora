from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status

from accounts.models import Role, RoleCode
from contracts.models import Contract
from contracts.tests.base import ContractAPITestCase
from installments.choices import InstallmentStatus
from installments.models import Installment
from payments.choices import PaymentStatus, ReceiptStatus
from payments.models import Payment, PaymentApplication, Receipt
from payments.services import financial_summary


class PaymentFlowTests(ContractAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cashier_role = Role.objects.get(code=RoleCode.CASHIER)
        cls.cashier_a = cls.make_user("pay.cashier.a", cls.org_a, cls.branch_a, cashier_role)

    def active_contract(self, *, key="pay-contract-create", confirm_key="pay-contract-confirm", **overrides):
        draft = self.create_draft(key=key, installment_amount="500.00", **overrides).data["data"]
        response = self.confirm(draft["id"], key=confirm_key)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return Contract.objects.get(pk=draft["id"])

    def pay(self, contract, amount, *, payment_type="installment", method="cash", key="payment-key-0001", user=None, **extra):
        self.authenticate(user)
        payload = {
            "contract": contract.pk, "amount": str(amount), "payment_type": payment_type,
            "payment_method": method, **extra,
        }
        return self.client.post("/api/payments/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)

    def test_exact_payment_creates_application_receipt_and_paid_installment(self):
        contract = self.active_contract()
        response = self.pay(contract, "500.00")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(contract=contract)
        first = Installment.objects.filter(contract=contract).first()
        self.assertEqual(payment.status, PaymentStatus.CONFIRMED)
        self.assertEqual(payment.applications.get().amount_applied, Decimal("500.00"))
        self.assertEqual(first.paid_amount, Decimal("500.00"))
        self.assertEqual(first.status, InstallmentStatus.PAID)
        self.assertEqual(payment.receipt.status, ReceiptStatus.ISSUED)
        self.assertEqual(financial_summary(contract)["contract_balance"], Decimal("22500.00"))

    def test_partial_payment_and_completion_keep_both_applications(self):
        contract = self.active_contract()
        self.pay(contract, "200.00", key="partial-payment-1")
        first = Installment.objects.filter(contract=contract).first()
        first.refresh_from_db()
        self.assertEqual((first.paid_amount, first.pending_amount, first.status), (
            Decimal("200.00"), Decimal("300.00"), InstallmentStatus.PARTIALLY_PAID,
        ))
        self.pay(contract, "300.00", key="partial-payment-2")
        first.refresh_from_db()
        self.assertEqual(first.paid_amount, Decimal("500.00"))
        self.assertEqual(first.status, InstallmentStatus.PAID)
        self.assertEqual(PaymentApplication.objects.filter(installment=first).count(), 2)

    def test_multiquota_and_advance_use_oldest_due_first(self):
        contract = self.active_contract()
        response = self.pay(contract, "1200.00", payment_type="advance", key="advance-multi-payment")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        items = list(Installment.objects.filter(contract=contract).order_by("installment_number")[:4])
        self.assertEqual([item.paid_amount for item in items], [
            Decimal("500.00"), Decimal("500.00"), Decimal("200.00"), Decimal("0.00"),
        ])
        self.assertEqual([item.status for item in items[:3]], [
            InstallmentStatus.PAID, InstallmentStatus.PAID, InstallmentStatus.PARTIALLY_PAID,
        ])

    def test_initial_payment_is_explicit_and_does_not_modify_installments(self):
        contract = self.active_contract()
        response = self.pay(contract, "3000.00", payment_type="initial_payment", key="initial-payment-key")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(contract=contract)
        self.assertEqual(payment.initial_amount_applied, Decimal("3000.00"))
        self.assertEqual(payment.applications.count(), 0)
        self.assertFalse(Installment.objects.filter(contract=contract, paid_amount__gt=0).exists())
        summary = financial_summary(Contract.objects.get(pk=contract.pk))
        self.assertEqual(summary["initial_payment_paid"], Decimal("3000.00"))
        self.assertEqual(summary["initial_payment_pending"], Decimal("2000.00"))

    def test_settlement_revalidates_balance_and_pays_every_obligation(self):
        contract = self.active_contract()
        self.authenticate()
        response = self.client.post(
            f"/api/contracts/{contract.pk}/settle/",
            {"expected_balance": "23000.00", "payment_method": "transfer", "reference": "TRX-900"},
            format="json", HTTP_IDEMPOTENCY_KEY="settlement-payment-key",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(contract=contract)
        self.assertEqual(payment.initial_amount_applied, Decimal("5000.00"))
        self.assertEqual(payment.applications.aggregate(value=Sum("amount_applied"))["value"], Decimal("18000.00"))
        self.assertFalse(Installment.objects.filter(contract=contract).exclude(status=InstallmentStatus.PAID).exists())
        summary = financial_summary(Contract.objects.get(pk=contract.pk))
        self.assertEqual(summary["contract_balance"], Decimal("0.00"))
        self.assertEqual(summary["financial_status"], "paid")

    def test_overpayment_reference_and_changed_settlement_balance_are_rejected(self):
        contract = self.active_contract()
        overpay = self.pay(contract, "18000.01", key="overpayment-key")
        no_reference = self.pay(contract, "500.00", method="transfer", key="missing-reference-key")
        self.authenticate()
        stale = self.client.post(
            f"/api/contracts/{contract.pk}/settle/",
            {"expected_balance": "1.00", "payment_method": "cash"}, format="json",
            HTTP_IDEMPOTENCY_KEY="stale-settlement-key",
        )
        self.assertEqual(overpay.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(no_reference.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Payment.objects.count(), 0)

    def test_idempotency_retries_without_duplication_and_rejects_changed_payload(self):
        contract = self.active_contract()
        first = self.pay(contract, "500.00", key="same-payment-idempotency")
        second = self.pay(contract, "500.00", key="same-payment-idempotency")
        changed = self.pay(contract, "700.00", key="same-payment-idempotency")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(changed.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(PaymentApplication.objects.count(), 1)

    def test_void_rebuilds_installments_and_marks_receipt_void(self):
        contract = self.active_contract()
        created = self.pay(contract, "700.00").data["data"]
        self.authenticate()
        response = self.client.post(f"/api/payments/{created['id']}/void/", {"reason": "Registro duplicado"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(pk=created["id"])
        self.assertEqual(payment.status, PaymentStatus.VOIDED)
        self.assertEqual(payment.receipt.status, ReceiptStatus.VOIDED)
        self.assertFalse(Installment.objects.filter(contract=contract, paid_amount__gt=0).exists())
        self.assertTrue(payment.applications.exists())
        self.assertEqual(financial_summary(Contract.objects.get(pk=contract.pk))["total_paid"], Decimal("0.00"))

    def test_void_of_earlier_payment_rebuilds_later_payment_deterministically(self):
        contract = self.active_contract()
        first = self.pay(contract, "500.00", key="chronological-payment-a").data["data"]
        second = self.pay(contract, "500.00", key="chronological-payment-b").data["data"]
        self.authenticate()
        self.client.post(f"/api/payments/{first['id']}/void/", {"reason": "Anulación cronológica"}, format="json")
        second_payment = Payment.objects.get(pk=second["id"])
        self.assertEqual(second_payment.applications.get().installment.installment_number, 1)
        items = list(Installment.objects.filter(contract=contract).order_by("installment_number")[:2])
        self.assertEqual([item.paid_amount for item in items], [Decimal("500.00"), Decimal("0.00")])
        self.assertEqual(Payment.objects.filter(status=PaymentStatus.CONFIRMED).count(), 1)

    def test_payment_blocks_simple_cancellation_and_reprogramming(self):
        contract = self.active_contract()
        self.pay(contract, "100.00", payment_type="initial_payment", key="blocking-initial-payment")
        self.authenticate()
        cancelled = self.client.post(
            f"/api/contracts/{contract.pk}/cancel/", {"reason": "Intento simple"}, format="json"
        )
        reprogrammed = self.client.post(
            f"/api/contracts/{contract.pk}/installment-schedule/reprogram/",
            {"frequency": "weekly", "installment_amount": "500.00",
             "first_due_date": str(timezone.localdate() + timedelta(days=7)),
             "reason": "Intento con pagos"}, format="json",
        )
        self.assertEqual(cancelled.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(reprogrammed.status_code, status.HTTP_400_BAD_REQUEST)
        contract.refresh_from_db()
        self.assertEqual(contract.status, "active")

    def test_cancelled_contract_rejects_new_payment(self):
        contract = self.active_contract()
        self.authenticate()
        self.client.post(f"/api/contracts/{contract.pk}/cancel/", {"reason": "Cancelación válida"}, format="json")
        response = self.pay(contract, "500.00", key="cancelled-contract-payment")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_permissions_collector_and_cashier_collect_seller_cannot_and_admin_voids(self):
        contract = self.active_contract()
        collected = self.pay(contract, "100.00", user=self.collector_a, key="collector-payment-key")
        cashier = self.pay(contract, "100.00", user=self.cashier_a, key="cashier-payment-key")
        seller = self.pay(contract, "100.00", user=self.seller_a, key="seller-payment-key")
        self.authenticate(self.collector_a)
        denied_void = self.client.post(
            f"/api/payments/{collected.data['data']['id']}/void/", {"reason": "Sin autoridad"}, format="json"
        )
        self.authenticate()
        allowed_void = self.client.post(
            f"/api/payments/{collected.data['data']['id']}/void/", {"reason": "Corrección autorizada"}, format="json"
        )
        self.assertEqual(collected.status_code, status.HTTP_201_CREATED)
        self.assertEqual(cashier.status_code, status.HTTP_201_CREATED)
        self.assertEqual(seller.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied_void.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed_void.status_code, status.HTTP_200_OK)

    def test_least_privilege_blocks_collector_prime_and_cashier_settlement(self):
        contract = self.active_contract()
        collector_prime = self.pay(
            contract, "100.00", payment_type="initial_payment", user=self.collector_a,
            key="collector-prime-denied",
        )
        self.authenticate(self.cashier_a)
        cashier_settlement = self.client.post(
            f"/api/contracts/{contract.pk}/settle/",
            {"expected_balance": "25000.00", "payment_method": "cash"},
            format="json", HTTP_IDEMPOTENCY_KEY="cashier-settlement-denied",
        )
        self.assertEqual(collector_prime.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cashier_settlement.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Payment.objects.count(), 0)

    def test_tenant_isolation_protects_detail_void_receipt_and_contract_payment(self):
        contract = self.active_contract()
        payment = self.pay(contract, "500.00").data["data"]
        self.authenticate(self.admin_b)
        self.assertEqual(self.client.get(f"/api/payments/{payment['id']}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f"/api/payments/{payment['id']}/receipt/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f"/api/payments/{payment['id']}/receipt/pdf/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(
            f"/api/payments/{payment['id']}/void/", {"reason": "Ataque externo"}, format="json"
        ).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.pay(contract, "100.00", user=self.admin_b, key="foreign-contract-payment").status_code, status.HTTP_404_NOT_FOUND)

    def test_list_search_filters_total_and_receipt_pdf(self):
        contract = self.active_contract()
        payment = self.pay(contract, "500.00", method="check", reference="CHK-123").data["data"]
        self.authenticate()
        listed = self.client.get("/api/payments/?search=CHK-123&payment_method=check&preset=today")
        pdf = self.client.get(f"/api/payments/{payment['id']}/receipt/pdf/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["data"]["count"], 1)
        self.assertEqual(Decimal(listed.data["data"]["total_confirmed"]), Decimal("500.00"))
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_backdate_is_audited_permission_and_receipt_snapshot_is_historical(self):
        contract = self.active_contract()
        old_date = (timezone.now() - timedelta(days=1)).isoformat()
        denied = self.pay(contract, "100.00", user=self.collector_a, key="collector-backdate-key", payment_date=old_date)
        allowed = self.pay(contract, "100.00", user=self.admin_a, key="admin-backdate-key", payment_date=old_date)
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        receipt = Payment.objects.get(pk=allowed.data["data"]["id"]).receipt
        original_name = receipt.customer_name_snapshot
        self.customer_a.first_name = "Nombre posterior"
        self.customer_a.save()
        receipt.refresh_from_db()
        self.assertEqual(receipt.customer_name_snapshot, original_name)
