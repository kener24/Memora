import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  ContractPaymentsPayload, PaginatedPayments, Payment, PaymentInput, PaymentOptions, PaymentPreview,
} from "../types/payment";

function queryString(filters: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return params.size ? `?${params.toString()}` : "";
}
export const getPaymentOptions = () => apiRequest<PaymentOptions>("payments/options/");
export const listPayments = (filters: Record<string, string | number | undefined>) =>
  apiRequest<PaginatedPayments>(`payments/${queryString(filters)}`);
export const getPayment = (id: number) => apiRequest<Payment>(`payments/${id}/`);
export const getContractPayments = (contractId: number, page = 1) =>
  apiRequest<ContractPaymentsPayload>(`contracts/${contractId}/payments/?page=${page}`);
export const previewPayment = (contractId: number, payload: Pick<PaymentInput, "amount" | "payment_type">) =>
  apiRequest<PaymentPreview>(`contracts/${contractId}/payments/preview/`, { method: "POST", body: JSON.stringify(payload) });
export const createPayment = (payload: PaymentInput, idempotencyKey: string) =>
  apiRequest<Payment>("payments/", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload) });
export const settleContract = (
  contractId: number, payload: { expected_balance: string; payment_method: string; reference?: string; notes?: string; payment_date?: string }, idempotencyKey: string,
) => apiRequest<Payment>(`contracts/${contractId}/settle/`, {
  method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload),
});
export const voidPayment = (id: number, reason: string) =>
  apiRequest<Payment>(`payments/${id}/void/`, { method: "POST", body: JSON.stringify({ reason }) });
export const downloadReceiptPdf = (id: number) => apiBlobRequest(`payments/${id}/receipt/pdf/`);
