import type { PaymentModulePermissions } from "./auth";
import type { FinancialSummary } from "./contract";
import type { BranchOption, SelectOption } from "./customer";

export interface PaymentApplication {
  id: number; installment: number; installment_number: number; schedule_version: number;
  due_date: string; amount_applied: string; created_at: string;
}
export interface Receipt {
  id: number; receipt_number: string; payment: number; issued_at: string; status: string; status_label: string;
  organization_name_snapshot: string; organization_address_snapshot: string; organization_phone_snapshot: string;
  customer_name_snapshot: string; customer_code_snapshot: string; customer_identity_snapshot: string;
  contract_number_snapshot: string; concept_snapshot: string; method_snapshot: string;
  reference_snapshot: string; received_by_snapshot: string; amount_snapshot: string;
  balance_before: string; balance_after: string;
  applications_snapshot: Array<{ kind: string; label?: string; installment_number?: number; due_date?: string; amount: string }>;
  created_at: string; updated_at: string;
}
export interface Payment {
  id: number; organization: number; branch: number; branch_name: string; contract: number; contract_number: string;
  customer: number; customer_name: string; customer_code: string; payment_number: string; payment_date: string;
  amount: string; payment_method: string; payment_method_label: string; reference: string;
  payment_type: string; payment_type_label: string; status: string; status_label: string; notes: string;
  received_by: { id: number; name: string }; created_by: { id: number; name: string };
  idempotency_key: string; initial_amount_applied: string; direct_amount_applied: string;
  voided_at: string | null; voided_by: { id: number; name: string } | null; void_reason: string;
  receipt: Receipt; applications: PaymentApplication[]; financial_summary: FinancialSummary | null;
  created_at: string; updated_at: string;
}
export interface PaginatedPayments {
  count: number; page: number; page_size: number; total_pages: number; next: string | null;
  previous: string | null; total_confirmed?: string; results: Payment[];
}
export interface PaymentOptions {
  payment_types: SelectOption[]; payment_methods: SelectOption[]; statuses: SelectOption[];
  branches: BranchOption[]; receivers: { id: number; name: string }[]; permissions: PaymentModulePermissions;
}
export interface PaymentInput {
  contract?: number; amount: string; payment_type: string; payment_method?: string;
  reference?: string; notes?: string; payment_date?: string;
}
export interface PaymentPreview {
  amount: string; balance_before: string; balance_after: string; initial_amount: string; direct_amount: string;
  applications: Array<{ installment_id: number; installment_number: number; due_date: string; amount: string }>;
  financial_summary: FinancialSummary;
}
export interface ContractPaymentsPayload { financial_summary: FinancialSummary; payments: PaginatedPayments }
