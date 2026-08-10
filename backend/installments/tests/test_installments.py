from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from contracts.choices import ContractStatus
from contracts.tests.base import ContractAPITestCase
from installments.choices import InstallmentStatus, ScheduleStatus
from installments.models import Installment, InstallmentSchedule
from installments.services import build_automatic_preview, effective_installment_status, monthly_due_date


class InstallmentEngineAndAPITests(ContractAPITestCase):
    def active_contract(self, *, key="s4-create", confirm_key="s4-confirm", **overrides):
        draft = self.create_draft(key=key, **overrides).data["data"]
        response = self.confirm(draft["id"], key=confirm_key)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["data"]

    def test_exact_amount_and_adjusted_last_installment(self):
        contract = self.active_contract(installment_amount="7000.00")
        schedule = InstallmentSchedule.objects.get(contract_id=contract["id"])
        amounts = list(schedule.installments.values_list("current_amount", flat=True))
        self.assertEqual(amounts, [Decimal("7000.00"), Decimal("7000.00"), Decimal("4000.00")])
        self.assertEqual(sum(amounts), Decimal("18000.00"))

    def test_month_end_anchor_is_preserved(self):
        self.assertEqual(monthly_due_date(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertEqual(monthly_due_date(date(2025, 1, 31), 2), date(2025, 3, 31))
        self.assertEqual(monthly_due_date(date(2025, 1, 31), 3), date(2025, 4, 30))

    def test_weekly_and_biweekly_intervals(self):
        contract_data = self.active_contract()
        contract = InstallmentSchedule.objects.get(contract_id=contract_data["id"]).contract
        weekly = build_automatic_preview(contract, "weekly", "6000", contract.sale_date)
        biweekly = build_automatic_preview(contract, "biweekly", "6000", contract.sale_date)
        self.assertEqual((weekly.items[1].due_date - weekly.items[0].due_date).days, 7)
        self.assertEqual((biweekly.items[1].due_date - biweekly.items[0].due_date).days, 15)

    def test_confirmation_generates_once_and_generate_endpoint_is_idempotent(self):
        contract = self.active_contract()
        self.authenticate()
        first = self.client.post(f"/api/contracts/{contract['id']}/installment-schedule/generate/", {}, format="json")
        second = self.client.post(f"/api/contracts/{contract['id']}/installment-schedule/generate/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(InstallmentSchedule.objects.filter(contract_id=contract["id"]).count(), 1)
        self.assertEqual(Installment.objects.filter(contract_id=contract["id"]).count(), 12)

    def test_custom_schedule_requires_exact_manual_sum(self):
        contract = self.active_contract(
            payment_frequency="custom", installment_amount="9000.00",
            key="s4-custom", confirm_key="s4-custom-confirm",
        )
        self.assertFalse(InstallmentSchedule.objects.filter(contract_id=contract["id"]).exists())
        self.authenticate()
        invalid = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/generate/",
            {"manual_installments": [{"due_date": str(timezone.localdate()), "amount": "100.00"}]},
            format="json",
        )
        valid = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/generate/",
            {"manual_installments": [
                {"due_date": str(timezone.localdate() + timedelta(days=30)), "amount": "8000.00"},
                {"due_date": str(timezone.localdate() + timedelta(days=60)), "amount": "10000.00"},
            ]}, format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(valid.data["data"]["schedule"]["frequency"], "custom")

    def test_preview_does_not_persist_and_reprogram_keeps_version_history(self):
        contract = self.active_contract()
        before_count = InstallmentSchedule.objects.count()
        self.authenticate()
        payload = {
            "frequency": "weekly", "installment_amount": "5000.00",
            "first_due_date": str(timezone.localdate() + timedelta(days=7)),
        }
        preview = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/preview/", payload, format="json"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(InstallmentSchedule.objects.count(), before_count)
        payload["reason"] = "Ajuste solicitado por el cliente"
        changed = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/reprogram/", payload, format="json"
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        schedules = InstallmentSchedule.objects.filter(contract_id=contract["id"]).order_by("version")
        self.assertEqual(list(schedules.values_list("version", "status")), [(1, "replaced"), (2, "active")])
        self.assertFalse(schedules[0].installments.exclude(status=InstallmentStatus.CANCELLED).exists())
        self.assertEqual(changed.data["data"]["schedule"]["previous_schedule"], schedules[0].pk)

    def test_contract_cancellation_cancels_schedule_and_items(self):
        contract = self.active_contract()
        self.authenticate()
        cancelled = self.client.post(
            f"/api/contracts/{contract['id']}/cancel/", {"reason": "Solicitud documentada"}, format="json"
        )
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        schedule = InstallmentSchedule.objects.get(contract_id=contract["id"])
        self.assertEqual(schedule.status, ScheduleStatus.CANCELLED)
        self.assertFalse(schedule.installments.exclude(status=InstallmentStatus.CANCELLED).exists())
        self.assertEqual(schedule.contract.status, ContractStatus.CANCELLED)

    def test_cash_contract_never_creates_a_schedule(self):
        draft = self.create_draft(key="s4-cash-create", allow_financing=False).data["data"]
        confirmed = self.confirm(draft["id"], key="s4-cash-confirm")
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        self.assertFalse(InstallmentSchedule.objects.filter(contract_id=draft["id"]).exists())

    def test_reprogramming_is_blocked_if_a_payment_already_exists(self):
        contract = self.active_contract()
        item = Installment.objects.filter(contract_id=contract["id"]).first()
        item.paid_amount = Decimal("1.00")
        item.status = InstallmentStatus.PARTIALLY_PAID
        item.save(update_fields=("paid_amount", "status", "updated_at"))
        self.authenticate()
        denied = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/reprogram/",
            {"frequency": "weekly", "installment_amount": "5000.00",
             "first_due_date": str(timezone.localdate() + timedelta(days=7)),
             "reason": "Intento posterior a un pago"}, format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(InstallmentSchedule.objects.get(contract_id=contract["id"]).status, ScheduleStatus.ACTIVE)

    def test_effective_overdue_is_calculated_without_mutating_the_obligation(self):
        contract = self.active_contract(first_due_date=str(timezone.localdate() + timedelta(days=1)))
        item = Installment.objects.filter(contract_id=contract["id"]).first()
        item.due_date = timezone.localdate() - timedelta(days=1)
        item.save(update_fields=("due_date", "updated_at"))
        self.assertEqual(effective_installment_status(item), InstallmentStatus.OVERDUE)
        item.refresh_from_db()
        self.assertEqual(item.status, InstallmentStatus.PENDING)

    def test_filters_pagination_pdf_and_tenant_isolation(self):
        contract = self.active_contract()
        self.authenticate()
        listed = self.client.get("/api/installments/?preset=month&page_size=5")
        pdf = self.client.get(f"/api/contracts/{contract['id']}/installment-schedule/pdf/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["data"]["page_size"], 5)
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.authenticate(self.admin_b)
        self.assertEqual(
            self.client.get(f"/api/contracts/{contract['id']}/installment-schedule/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/contracts/{contract['id']}/installment-schedule/pdf/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_role_permissions_protect_mutation_and_module(self):
        contract = self.active_contract()
        self.authenticate(self.collector_a)
        self.assertEqual(self.client.get("/api/installments/").status_code, status.HTTP_200_OK)
        denied = self.client.post(
            f"/api/contracts/{contract['id']}/installment-schedule/reprogram/",
            {"frequency": "weekly", "installment_amount": "1000.00",
             "first_due_date": str(timezone.localdate() + timedelta(days=7)), "reason": "Sin permiso"},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.authenticate(self.inventory_a)
        self.assertEqual(self.client.get("/api/installments/").status_code, status.HTTP_403_FORBIDDEN)
