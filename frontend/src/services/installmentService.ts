import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  ContractSchedulePayload, InstallmentModuleOptions, InstallmentSummary, ManualInstallment,
  PaginatedInstallments, ScheduleConditions, SchedulePreview,
} from "../types/installment";

function queryString(filters: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return params.size ? `?${params.toString()}` : "";
}
export const getInstallmentOptions = () => apiRequest<InstallmentModuleOptions>("installments/options/");
export const getInstallmentSummary = () => apiRequest<InstallmentSummary>("installments/summary/");
export const listInstallments = (filters: Record<string, string | number | undefined>) =>
  apiRequest<PaginatedInstallments>(`installments/${queryString(filters)}`);
export const getContractSchedule = (id: number | string, page = 1) =>
  apiRequest<ContractSchedulePayload>(`contracts/${id}/installment-schedule/?page=${page}`);
export const generateContractSchedule = (id: number | string, manual_installments?: ManualInstallment[]) =>
  apiRequest<ContractSchedulePayload>(`contracts/${id}/installment-schedule/generate/`, {
    method: "POST", body: JSON.stringify({ manual_installments }),
  });
export const previewContractSchedule = (id: number | string, payload: ScheduleConditions) =>
  apiRequest<SchedulePreview>(`contracts/${id}/installment-schedule/preview/`, {
    method: "POST", body: JSON.stringify(payload),
  });
export const reprogramContractSchedule = (id: number | string, payload: ScheduleConditions) =>
  apiRequest<ContractSchedulePayload>(`contracts/${id}/installment-schedule/reprogram/`, {
    method: "POST", body: JSON.stringify(payload),
  });
export const downloadPaymentPlanPdf = (id: number | string) =>
  apiBlobRequest(`contracts/${id}/installment-schedule/pdf/`);
