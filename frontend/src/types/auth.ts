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

