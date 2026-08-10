import type { InstallmentModulePermissions } from "./auth";
import type { BranchOption, SelectOption } from "./customer";

export interface NamedOption { id: number; name: string; code?: string }
export interface InstallmentModuleOptions {
  statuses: SelectOption[]; frequencies: SelectOption[]; branches: BranchOption[];
  sellers: NamedOption[]; plans: NamedOption[]; permissions: InstallmentModulePermissions;
}
export interface Installment {
  id: number; contract: number; contract_number: string; customer_name: string; customer_code: string;
  branch_name: string; seller_name: string; plan_name: string; schedule: number; schedule_version: number;
  installment_number: number; due_date: string; original_amount: string; current_amount: string;
  paid_amount: string; pending_amount: string; status: string; effective_status: string;
  effective_status_label: string; generated_at: string; created_at: string;
}
export interface PaginatedInstallments {
  count: number; page: number; page_size: number; total_pages: number; next: string | null;
  previous: string | null; results: Installment[];
}
export interface ScheduleSummary {
  id: number; contract: number; previous_schedule: number | null; version: number; status: string;
  status_label: string; total_financed: string; regular_installment_amount: string; frequency: string;
  frequency_label: string; first_due_date: string; last_due_date: string; total_installments: number;
  generated_by: NamedOption; generated_at: string; reprogramming_reason: string;
  reprogrammed_by: NamedOption | null; reprogrammed_at: string | null; created_at: string; updated_at: string;
}
export interface ContractSchedulePayload {
  schedule: ScheduleSummary | null; installments: PaginatedInstallments | null;
  history: ScheduleSummary[]; reason?: "cash" | "not_generated";
}
export interface ManualInstallment { due_date: string; amount: string }
export interface ScheduleConditions {
  frequency: string; installment_amount?: string; first_due_date?: string | null;
  manual_installments?: ManualInstallment[]; reason?: string;
}
export interface SchedulePreview {
  total: string; frequency: string; frequency_label: string; regular_installment_amount: string;
  first_due_date: string; last_due_date: string; total_installments: number;
  items: { installment_number: number; due_date: string; amount: string }[];
}
export interface InstallmentSummary { due_today: number; overdue: number; scheduled_this_month: string }
