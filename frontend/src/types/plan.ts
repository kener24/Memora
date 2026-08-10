import type { PlanModulePermissions } from "./auth";
import type { BranchOption, OrganizationOption, SelectOption } from "./customer";

export interface PlanModuleOptions {
  categories: SelectOption[];
  units: SelectOption[];
  branches: BranchOption[];
  organizations: OrganizationOption[];
  permissions: PlanModulePermissions;
}

export interface ServiceCatalogItem {
  id: number;
  code: string;
  name: string;
  description: string;
  category: string;
  category_label: string;
  unit: string;
  unit_label: string;
  estimated_cost?: string;
  default_sale_price: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServicePayload {
  organization?: number | "";
  code: string;
  name: string;
  description: string;
  category: string;
  unit: string;
  estimated_cost: string;
  default_sale_price: string;
}

export interface PlanItemService {
  id: number;
  code: string;
  name: string;
  category: string;
  category_label: string;
  unit: string;
  unit_label: string;
  is_active: boolean;
  estimated_cost?: string;
}

export interface PlanItem {
  id: number;
  service: PlanItemService;
  quantity: string;
  included: boolean;
  notes: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PlanActivity {
  id: number;
  action: string;
  action_label: string;
  description: string;
  old_value: string | null;
  new_value: string | null;
  user: { id: number; name: string } | null;
  created_at: string;
}

export interface PlanAvailability {
  all_branches: boolean;
  branches: BranchOption[];
}

export interface FuneralPlanListItem {
  id: number;
  code: string;
  name: string;
  description: string;
  base_price: string;
  initial_payment: string;
  allow_financing: boolean;
  available_all_branches: boolean;
  availability: PlanAvailability;
  items_count: number;
  estimated_plan_cost?: string;
  estimated_margin?: string;
  estimated_margin_percent?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FuneralPlanDetail extends FuneralPlanListItem {
  organization: { id: number; name: string };
  created_by: { id: number; name: string };
  items: PlanItem[];
  activities: PlanActivity[];
}

export interface PlanItemPayload {
  service_id: number;
  quantity: string;
  included: boolean;
  notes: string;
  sort_order: number;
}

export interface FuneralPlanPayload {
  organization?: number | "";
  name: string;
  description: string;
  base_price: string;
  initial_payment: string;
  allow_financing: boolean;
  available_all_branches: boolean;
  available_branch_ids: number[];
  items: PlanItemPayload[];
}

export interface PaginatedResult<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
