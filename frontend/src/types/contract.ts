import type { ContractModulePermissions } from "./auth";
import type { BranchOption, OrganizationOption, SelectOption } from "./customer";

export interface SellerOption { id: number; name: string; role: string; organization_id: number }
export interface ContractModuleOptions {
  statuses: SelectOption[];
  payment_frequencies: SelectOption[];
  branches: BranchOption[];
  sellers: SellerOption[];
  organizations: OrganizationOption[];
  permissions: ContractModulePermissions;
}

export interface ContractListItem {
  id: number; contract_number: string; customer_name: string; beneficiary_name: string;
  plan_name: string; seller_name: string; branch_name: string; sale_date: string;
  total_price: string; allow_financing: boolean; status: string; status_label: string;
  created_at: string; updated_at: string;
}

export interface ContractPlanItem {
  id: number; service_code_snapshot: string; service_name_snapshot: string;
  service_description_snapshot: string; category_snapshot: string; quantity: string;
  unit_snapshot: string; notes_snapshot: string; estimated_cost_snapshot?: string; sort_order: number;
}

export interface ContractActivity {
  id: number; action: string; action_label: string; description: string;
  user: { id: number; name: string } | null; created_at: string;
}

export interface ContractDetail extends ContractListItem {
  organization: { id: number; name: string }; branch: BranchOption;
  customer: { id: number; code: string; name: string };
  beneficiary: { id: number; name: string } | null;
  plan: { id: number; code: string; name: string }; seller: { id: number; name: string };
  start_date: string; plan_name_snapshot: string; plan_description_snapshot: string;
  customer_name_snapshot: string; customer_identity_snapshot: string;
  customer_address_snapshot: string; customer_phone_snapshot: string;
  beneficiary_name_snapshot: string; beneficiary_identity_snapshot: string;
  beneficiary_relationship_snapshot: string; subtotal: string; discount: string;
  initial_payment_agreed: string; financed_amount: string; payment_frequency: string;
  payment_frequency_label: string; installment_amount: string; first_due_date: string | null;
  notes: string; cancelled_at: string | null; cancelled_by: { id: number; name: string } | null;
  cancellation_reason: string; created_by: { id: number; name: string };
  plan_items: ContractPlanItem[]; activities: ContractActivity[];
  financial_summary: FinancialSummary;
}

export interface FinancialSummary {
  total_price: string; total_paid: string; contract_balance: string;
  financial_status: string; financial_status_label: string;
  initial_payment_agreed: string; initial_payment_paid: string; initial_payment_pending: string;
  financed_amount: string; financed_paid: string; financed_pending: string; direct_paid: string;
}

export interface ContractDraftPayload {
  organization?: number | ""; branch: number; customer: number; beneficiary: number | null;
  plan: number; seller: number; sale_date: string; start_date: string; discount: string;
  allow_financing: boolean; initial_payment_agreed: string; payment_frequency: string;
  installment_amount: string; first_due_date: string | null; notes: string;
}

export interface PaginatedContracts {
  count: number; page: number; page_size: number; total_pages: number;
  next: string | null; previous: string | null; results: ContractListItem[];
}
