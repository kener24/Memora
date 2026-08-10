from rest_framework import status

from contracts.models import Contract

from .base import ContractAPITestCase


class ContractCancellationTests(ContractAPITestCase):
    def setUp(self):
        draft = self.create_draft().data["data"]
        self.contract_id = draft["id"]
        self.confirm(self.contract_id)

    def test_manager_cancels_with_audit_and_reason(self):
        self.authenticate(self.manager_a)
        response = self.client.post(
            f"/api/contracts/{self.contract_id}/cancel/", {"reason": "Solicitud escrita del cliente"}, format="json",
        )
        contract = Contract.objects.get(pk=self.contract_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(contract.status, "cancelled")
        self.assertEqual(contract.cancelled_by, self.manager_a)
        self.assertIsNotNone(contract.cancelled_at)
        self.assertEqual(contract.activities.filter(action="cancelled").count(), 1)

    def test_cancellation_is_irreversible_and_requires_reason(self):
        self.authenticate(self.admin_a)
        missing = self.client.post(f"/api/contracts/{self.contract_id}/cancel/", {"reason": ""}, format="json")
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        first = self.client.post(
            f"/api/contracts/{self.contract_id}/cancel/", {"reason": "Cambio contractual solicitado"}, format="json",
        )
        second = self.client.post(
            f"/api/contracts/{self.contract_id}/cancel/", {"reason": "Segundo intento"}, format="json",
        )
        edit = self.client.patch(f"/api/contracts/{self.contract_id}/", {"notes": "Reactivar"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(edit.status_code, status.HTTP_409_CONFLICT)

    def test_seller_cannot_cancel(self):
        self.authenticate(self.seller_a)
        response = self.client.post(
            f"/api/contracts/{self.contract_id}/cancel/", {"reason": "No autorizado"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
