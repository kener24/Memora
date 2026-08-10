import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  ContractDetail, ContractDraftPayload, ContractModuleOptions, PaginatedContracts,
} from "../types/contract";

function queryString(filters: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.size ? `?${params.toString()}` : "";
}

export function getContractOptions(): Promise<ContractModuleOptions> {
  return apiRequest<ContractModuleOptions>("contracts/options/");
}
export function listContracts(filters: Record<string, string | number | boolean | undefined>): Promise<PaginatedContracts> {
  return apiRequest<PaginatedContracts>(`contracts/${queryString(filters)}`);
}
export function getContract(id: number | string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>(`contracts/${id}/`);
}
export function createContractDraft(payload: ContractDraftPayload, key: string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>("contracts/", {
    method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(payload),
  });
}
export function confirmContract(id: number, key: string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>(`contracts/${id}/confirm/`, {
    method: "POST", headers: { "Idempotency-Key": key }, body: "{}",
  });
}
export function cancelContract(id: number, reason: string): Promise<ContractDetail> {
  return apiRequest<ContractDetail>(`contracts/${id}/cancel/`, {
    method: "POST", body: JSON.stringify({ reason }),
  });
}
export function downloadContractPdf(id: number): Promise<Blob> {
  return apiBlobRequest(`contracts/${id}/pdf/`);
}
