export interface SelectOption { value: string; label: string }
export interface NamedOption { id: number; name: string }
export interface CollectionPermissions {
  view_portfolio: boolean; view_overdue: boolean; create_action: boolean; view_action: boolean;
  void_action: boolean; create_promise: boolean; view_promise: boolean; resolve_promise: boolean;
  export_portfolio: boolean; global_access: boolean;
}
export interface CollectionOptions {
  statuses: SelectOption[]; priorities: SelectOption[]; action_types: SelectOption[]; outcomes: SelectOption[];
  aging_buckets: SelectOption[]; branches: NamedOption[]; plans: NamedOption[]; sellers: NamedOption[];
  permissions: CollectionPermissions;
}
export interface PortfolioRow {
  contract_id: number; contract_number: string; customer_id: number; customer_code: string;
  customer_name: string; identity: string; phone: string; address: string;
  branch: NamedOption; seller: NamedOption; plan: NamedOption; total_price: string; total_paid: string;
  balance: string; overdue_amount: string; upcoming_amount: string; initial_pending: string;
  overdue_installments: number; days_overdue: number; oldest_overdue_date: string | null; next_due_date: string | null;
  collection_status: string; collection_status_label: string; priority: string; priority_label: string;
  last_payment: { date: string; amount: string; number: string } | null;
  last_collection_action: { date: string; outcome: string } | null;
  active_promise: { date: string; amount: string; effective_status: string } | null;
}
export interface PortfolioTotals {
  contracts: number; customers: number; pending: string; overdue: string; upcoming: string; overdue_installments: number;
}
export interface PaginatedPortfolio {
  count: number; page: number; page_size: number; total_pages: number; next: string | null; previous: string | null;
  results: PortfolioRow[]; totals: PortfolioTotals;
}
export interface PortfolioSummary {
  pending_portfolio: string; overdue_portfolio: string; upcoming_portfolio: string; overdue_customers: number;
  overdue_installments: number; current_customers: number; critical_customers: number; collected_this_month: string;
}
export interface AgingSummary { buckets: Array<{ value: string; label: string; amount: string; installments: number }>; total_overdue: string }
export interface CollectionAction {
  id: number; contract: number; contract_number: string; customer: number; customer_name: string; customer_phone: string;
  action_type: string; action_type_label: string; outcome: string; outcome_label: string; notes: string;
  contact_date: string; next_follow_up_date: string | null; status: string; created_by_name: string;
  payment_promise: PaymentPromise | null;
}
export interface PaymentPromise {
  id: number; contract: number; contract_number: string; customer_name: string; promised_amount: string;
  promised_date: string; status: string; effective_status: string; status_label: string; created_by_name: string;
}
export interface CollectionDetail { portfolio: PortfolioRow; actions: CollectionAction[]; promises: PaymentPromise[] }
export interface FollowUpAgenda { overdue: CollectionAction[]; today: CollectionAction[]; upcoming: CollectionAction[] }

