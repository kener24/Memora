from rest_framework import status

from .base import ContractAPITestCase


class ContractSecurityTests(ContractAPITestCase):
    def test_organization_isolation_blocks_detail_pdf_and_cancel(self):
        draft = self.create_draft().data["data"]
        self.confirm(draft["id"])
        self.authenticate(self.admin_b)
        self.assertEqual(self.client.get(f"/api/contracts/{draft['id']}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f"/api/contracts/{draft['id']}/pdf/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.post(f"/api/contracts/{draft['id']}/cancel/", {"reason": "Intento externo"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cross_tenant_and_cross_branch_relations_are_rejected(self):
        foreign_customer = self.create_draft(key="foreign-customer", customer=self.customer_b.pk)
        foreign_plan = self.create_draft(key="foreign-plan", plan=self.plan_b.pk)
        wrong_beneficiary = self.create_draft(key="wrong-beneficiary", beneficiary=self.beneficiary_a2.pk)
        self.assertEqual(foreign_customer.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign_plan.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(wrong_beneficiary.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_is_forced_to_own_branch_and_identity(self):
        other_seller = self.create_draft(user=self.seller_a, seller=self.seller_a2.pk, discount="0.00")
        other_branch = self.create_draft(
            user=self.seller_a, key="seller-other-branch", branch=self.branch_a2.pk,
            customer=self.customer_a2.pk, beneficiary=self.beneficiary_a2.pk,
            plan=self.plan_a2.pk, seller=self.seller_a.pk, discount="0.00",
        )
        self.assertEqual(other_seller.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(other_branch.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_cannot_apply_discount_or_view_internal_costs(self):
        denied = self.create_draft(user=self.seller_a)
        allowed = self.create_draft(user=self.seller_a, key="seller-no-discount", discount="0.00")
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        confirmed = self.confirm(allowed.data["data"]["id"], self.seller_a, "seller-confirm-key")
        self.assertNotIn("estimated_cost_snapshot", confirmed.data["data"]["plan_items"][0])

    def test_accountant_reads_costs_but_cannot_create(self):
        draft = self.create_draft().data["data"]
        confirmed = self.confirm(draft["id"]).data["data"]
        self.authenticate(self.accountant_a)
        detail = self.client.get(f"/api/contracts/{confirmed['id']}/")
        denied = self.client.post(
            "/api/contracts/", self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="accountant-create",
        )
        self.assertIn("estimated_cost_snapshot", detail.data["data"]["plan_items"][0])
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_inventory_role_has_no_contract_access(self):
        self.authenticate(self.inventory_a)
        self.assertEqual(self.client.get("/api/contracts/").status_code, status.HTTP_403_FORBIDDEN)
