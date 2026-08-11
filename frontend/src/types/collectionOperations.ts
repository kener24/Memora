import type { CollectionModulePermissions } from "./auth";
import type { PaginatedPortfolio, PortfolioRow } from "./collection";

export interface CollectorMetrics {
  assigned_contracts: number; assigned_customers: number; pending_portfolio: string; overdue_portfolio: string;
  overdue_installments: number; due_today: string; collected_today: string; collected_month: string;
  cash_today: string; transfer_today: string; payments_today: number; actions_today: number;
  customers_attended_today: number; pending_promises: number; last_settlement: string | null;
}
export interface Collector {
  id: number; username: string; name: string; email: string; branch: number | null; branch_name: string | null;
  employee_code: string | null; is_available: boolean; notes: string; is_active: boolean; metrics: CollectorMetrics;
}
export interface Paginated<T> {
  count: number; page: number; page_size: number; total_pages: number; next: string | null; previous: string | null; results: T[];
}
export interface Assignment {
  id: number; contract: number; contract_number: string; customer_name: string; collector: number; collector_name: string;
  assigned_by_name: string; assigned_at: string; effective_from: string; effective_until: string | null;
  status: string; status_label: string; reason: string; previous_assignment: number | null;
}
export interface Zone {
  id: number; branch: number; branch_name: string; code: string; name: string; description: string;
  is_active: boolean; customer_count: number;
}
export interface RouteVisit {
  id: number; visit_date: string; status: string; status_label: string; notes: string; collection_action: number | null;
}
export interface RouteStop {
  id: number; customer: number; customer_name: string; customer_phone: string; customer_address: string;
  position: number; notes: string; is_active: boolean; is_primary: boolean; today_visit: RouteVisit | null;
}
export interface CollectionRoute {
  id: number; branch: number; branch_name: string; zone: number | null; zone_name: string | null;
  name: string; description: string; collector: number | null; collector_name: string | null;
  day_of_week: number | null; day_of_week_label: string | null; is_active: boolean; stops: RouteStop[];
}
export interface WorkSessionSummary {
  total_collected: string; expected_cash: string; cash_total: string; transfer_total: string; card_total: string;
  check_total: string; other_total: string; payment_count: number; voided_count: number;
}
export interface WorkSession {
  id: number; branch: number; collector: number; collector_name: string; work_date: string; started_at: string;
  ended_at: string | null; status: string; status_label: string; notes: string; summary: WorkSessionSummary | null;
}
export interface SettlementPayment {
  id: number; payment: number; payment_number_snapshot: string; receipt_number_snapshot: string;
  customer_name_snapshot: string; contract_number_snapshot: string; payment_method_snapshot: string;
  payment_method_label: string; amount_snapshot: string; payment_date: string;
}
export interface Settlement {
  id: number; settlement_number: string; branch: number; branch_name: string; collector: number; collector_name: string;
  work_session: number; total_collected: string; expected_cash: string; reported_cash: string;
  transfer_total: string; card_total: string; check_total: string; other_total: string; difference: string;
  status: string; status_label: string; submitted_by_name: string; submitted_at: string; reviewed_by_name: string | null;
  reviewed_at: string | null; notes: string; review_notes: string; payments: SettlementPayment[];
}
export interface SettlementPreview extends WorkSessionSummary {
  work_session: number; payment_fingerprint: string;
  payments: Array<{ id: number; payment_number: string; receipt_number: string; customer: string; contract: string; method: string; method_label: string; amount: string; payment_date: string }>;
}
export interface OperationsOptions {
  collectors: Array<{ id: number; name: string; branch: number | null }>;
  branches: Array<{ id: number; name: string }>;
  zones: Array<{ id: number; name: string; branch: number }>;
  days: Array<{ value: number; label: string }>;
  visit_statuses: Array<{ value: string; label: string }>;
  settlement_statuses: Array<{ value: string; label: string }>;
  permissions: CollectionModulePermissions;
}
export type CollectorPortfolio = PaginatedPortfolio;
export type CollectorAgenda = Paginated<PortfolioRow> & { totals: PaginatedPortfolio["totals"] };
