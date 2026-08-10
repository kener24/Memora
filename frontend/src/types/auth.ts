export interface NamedRole {
  codigo: string;
  nombre: string;
}

export interface OrganizationSummary {
  id: number;
  nombre: string;
}

export interface BranchSummary {
  id: number;
  nombre: string;
  codigo: string;
}

export interface BasicPermissions {
  es_staff: boolean;
  es_superusuario: boolean;
  acceso_admin: boolean;
  clientes: CustomerModulePermissions;
  planes: PlanModulePermissions;
  contratos: ContractModulePermissions;
  cuotas: InstallmentModulePermissions;
}

export interface InstallmentModulePermissions {
  view_installments: boolean;
  generate_schedule: boolean;
  reprogram_schedule: boolean;
  view_costs: boolean;
  global_access: boolean;
}

export interface ContractModulePermissions {
  view: boolean;
  create: boolean;
  edit_draft: boolean;
  cancel: boolean;
  apply_discount: boolean;
  view_costs: boolean;
  global_access: boolean;
}

export interface PlanModulePermissions {
  view: boolean;
  create: boolean;
  edit: boolean;
  change_status: boolean;
  duplicate: boolean;
  manage_services: boolean;
  view_costs: boolean;
  global_access: boolean;
}

export interface CustomerModulePermissions {
  view: boolean;
  create: boolean;
  edit: boolean;
  change_status: boolean;
  manage_beneficiaries: boolean;
  manage_contacts: boolean;
  global_access: boolean;
}

export interface AuthUser {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  rol: NamedRole | null;
  organizacion: OrganizationSummary | null;
  sucursal: BranchSummary | null;
  permisos: BasicPermissions;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
}

export interface ApiFailure {
  success: false;
  message: string;
  errors: Record<string, unknown>;
}
