import { apiRequest } from "../api/client";
import type {
  Beneficiary,
  BeneficiaryPayload,
  CustomerContact,
  CustomerContactPayload,
  CustomerDetail,
  CustomerFilters,
  CustomerModuleOptions,
  CustomerPayload,
  DuplicateMatch,
  PaginatedCustomers,
} from "../types/customer";

function buildQuery(filters: CustomerFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "" && value !== null) params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}
export function listCustomers(filters: CustomerFilters): Promise<PaginatedCustomers> {
  return apiRequest<PaginatedCustomers>(`customers/${buildQuery(filters)}`);
}

export function getCustomer(id: number | string): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>(`customers/${id}/`);
}

export function getCustomerOptions(): Promise<CustomerModuleOptions> {
  return apiRequest<CustomerModuleOptions>("customers/options/");
}

export function createCustomer(payload: CustomerPayload): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>("customers/", { method: "POST", body: JSON.stringify(payload) });
}

export function updateCustomer(id: number, payload: Partial<CustomerPayload>): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>(`customers/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function changeCustomerStatus(id: number, active: boolean): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>(`customers/${id}/${active ? "activate" : "deactivate"}/`, { method: "POST" });
}

export function checkDuplicates(identity_number: string, phone: string): Promise<DuplicateMatch[]> {
  return apiRequest<DuplicateMatch[]>("customers/check-duplicates/", {
    method: "POST",
    body: JSON.stringify({ identity_number, phone }),
  });
}

export function createBeneficiary(customerId: number, payload: BeneficiaryPayload): Promise<Beneficiary> {
  return apiRequest<Beneficiary>(`customers/${customerId}/beneficiaries/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateBeneficiary(customerId: number, id: number, payload: Partial<BeneficiaryPayload>): Promise<Beneficiary> {
  return apiRequest<Beneficiary>(`customers/${customerId}/beneficiaries/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createContact(customerId: number, payload: CustomerContactPayload): Promise<CustomerContact> {
  return apiRequest<CustomerContact>(`customers/${customerId}/contacts/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateContact(customerId: number, id: number, payload: Partial<CustomerContactPayload>): Promise<CustomerContact> {
  return apiRequest<CustomerContact>(`customers/${customerId}/contacts/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
