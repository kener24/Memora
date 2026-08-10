import type { CustomerModulePermissions } from "./auth";

export interface SelectOption {
  value: string;
  label: string;
}

export interface BranchOption {
  id: number;
  name: string;
  code: string;
  organization_id: number;
}

export interface OrganizationOption {
  id: number;
  name: string;
}

export interface CustomerModuleOptions {
  departments: SelectOption[];
  genders: SelectOption[];
  marital_statuses: SelectOption[];
  relationships: SelectOption[];
  branches: BranchOption[];
  organizations: OrganizationOption[];
  permissions: CustomerModulePermissions;
}

export interface CustomerListItem {
  id: number;
  customer_code: string;
  full_name: string;
  identity_number: string | null;
  phone: string;
  email: string;
  branch: BranchOption | null;
  department: string;
  department_label: string;
  beneficiaries_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedCustomers {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: CustomerListItem[];
}

export interface CustomerFilters {
  search?: string;
  is_active?: string;
  branch?: string;
  department?: string;
  created_from?: string;
  created_to?: string;
  ordering?: string;
  page?: number;
}

export interface CustomerPayload {
  organization?: number | "";
  branch?: number | "" | null;
  first_name: string;
  middle_name: string;
  last_name: string;
  second_last_name: string;
  identity_number: string;
  birth_date: string | null;
  gender: string;
  marital_status: string;
  phone: string;
  secondary_phone: string;
  email: string;
  address: string;
  city: string;
  department: string;
  country: string;
  occupation: string;
  notes: string;
}

export interface Beneficiary {
  id: number;
  is_customer: boolean;
  first_name: string;
  middle_name: string;
  last_name: string;
  second_last_name: string;
  full_name: string;
  identity_number: string | null;
  birth_date: string | null;
  age: number | null;
  relationship: string;
  relationship_label: string;
  phone: string;
  address: string;
  notes: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type BeneficiaryPayload = Omit<Beneficiary, "id" | "full_name" | "age" | "relationship_label" | "created_at" | "updated_at">;

export interface CustomerContact {
  id: number;
  name: string;
  relationship: string;
  phone: string;
  secondary_phone: string;
  notes: string;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type CustomerContactPayload = Omit<CustomerContact, "id" | "created_at" | "updated_at">;

export interface CustomerActivity {
  id: number;
  action: string;
  action_label: string;
  description: string;
  user: { id: number; name: string } | null;
  created_at: string;
}

export interface CustomerDetail extends Omit<CustomerPayload, "organization" | "branch"> {
  id: number;
  customer_code: string;
  full_name: string;
  organization: { id: number; name: string };
  branch: BranchOption | null;
  gender_label: string;
  marital_status_label: string;
  department_label: string;
  is_active: boolean;
  created_by: { id: number; name: string };
  created_at: string;
  updated_at: string;
  beneficiaries: Beneficiary[];
  contacts: CustomerContact[];
  activities: CustomerActivity[];
}

export interface DuplicateMatch {
  id: number;
  customer_code: string;
  full_name: string;
  same_identity: boolean;
  same_phone: boolean;
}
