export interface CashPermissions {
  view_cash_register: boolean; manage_cash_register: boolean; open_session: boolean;
  view_session: boolean; close_session: boolean; create_income: boolean;
  create_expense: boolean; void_movement: boolean; receive_collector_settlement: boolean;
  perform_cash_count: boolean; view_cash_history: boolean; export_cash: boolean;
  global_access: boolean;
}

export interface SelectOption { value: string; label: string }
export interface BranchOption { id: number; name: string; code: string }
export interface OpenSessionSummary { id: number; session_number: string; cashier: string; opened_at: string }
export interface CashRegister {
  id: number; organization: number; branch: number; branch_name: string; code: string;
  name: string; description: string; is_active: boolean; open_session: OpenSessionSummary | null;
  created_at: string; updated_at: string;
}
export interface CashDenomination { denomination: string; quantity: number; subtotal: string }
export interface CashCount {
  id: number; cash_session: number; expected_cash: string; counted_cash: string;
  difference: string; difference_reason: string; counted_by: number;
  counted_by_name: string; counted_at: string; denominations: CashDenomination[];
}
export interface CashSummary {
  opening_cash: string; cash_in: string; cash_out: string; expected_cash: string;
  financial_in?: string; financial_out?: string; financial_net?: string;
  method_totals: Record<string, string>; movement_count?: number; voided_count?: number;
  counted_cash?: string | null; difference?: string | null;
}
export interface CashSession {
  id: number; organization: number; branch: number; branch_name: string;
  cash_register: number; cash_register_code: string; cash_register_name: string;
  cashier: number; cashier_name: string; session_number: string; opened_at: string;
  closed_at: string | null; opening_cash: string; status: string; status_label: string;
  opened_by: number; opened_by_name: string; closed_by: number | null; closed_by_name: string;
  notes: string; summary: CashSummary; latest_count: CashCount | null;
  created_at: string; updated_at: string;
}
export interface MovementSource { type: string; id: number | null; label: string }
export interface CashMovement {
  id: number; organization: number; branch: number; branch_name: string; cash_session: number;
  session_number: string; session_status: string; cash_register_name: string; movement_number: string;
  movement_type: string; movement_type_label: string; direction: "in" | "out";
  direction_label: string; category: string; category_label: string; amount: string;
  payment_method: string; payment_method_label: string; affects_cash: boolean;
  description: string; reference: string; payment: number | null;
  settlement_reception: number | null; source: MovementSource; created_by: number;
  created_by_name: string; status: string; status_label: string; voided_at: string | null;
  void_reason: string; created_at: string;
}
export interface MovementTotals {
  total_in: string; total_out: string; net: string; cash_in: string; cash_out: string; cash_net: string;
}
export interface Paginated<T, Totals = Record<string, never>> {
  count: number; page: number; page_size: number; total_pages: number;
  next: string | null; previous: string | null; results: T[]; totals: Totals;
}
export interface PendingSettlement {
  id: number; settlement_number: string; collector: number; collector_name: string;
  branch: number; branch_name: string; work_session: number; work_date: string;
  total_collected: string; expected_cash: string; reported_cash: string; difference: string;
  transfer_total: string; card_total: string; check_total: string; other_total: string;
  status: string; status_label: string; submitted_at: string; notes: string; review_notes: string;
}
export interface SettlementReception {
  id: number; organization: number; branch: number; branch_name: string; cash_session: number;
  session_number: string; collector_settlement: number; settlement_number: string;
  work_date: string; collector_name: string; reception_number: string; expected_cash: string;
  reported_cash_by_collector: string; cash_received_by_cashier: string;
  collector_difference: string; delivery_difference: string; total_difference_vs_expected: string;
  transfer_total: string; card_total: string; check_total: string; other_total: string;
  received_by: number; received_by_name: string; received_at: string; notes: string;
  status: string; movement_number: string;
}
export interface CashDashboard {
  payment_total_today: string; payment_methods: Record<string, string>;
  cash_received_today: string; open_sessions: number; closed_sessions_today: number;
  cash_differences_today: string; pending_settlements: number; pending_settlement_cash: string;
}
export interface CashOptions {
  permissions: CashPermissions; branches: BranchOption[]; registers: CashRegister[];
  session_statuses: SelectOption[]; movement_statuses: SelectOption[];
  movement_types: SelectOption[]; directions: SelectOption[]; categories: SelectOption[];
  payment_methods: SelectOption[]; denominations: string[];
}
