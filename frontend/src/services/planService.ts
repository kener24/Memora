import { apiRequest } from "../api/client";
import type {
  FuneralPlanDetail, FuneralPlanListItem, FuneralPlanPayload, PaginatedResult,
  PlanModuleOptions, ServiceCatalogItem, ServicePayload,
} from "../types/plan";

function queryString(filters: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.size ? `?${params.toString()}` : "";
}

export function getPlanOptions(): Promise<PlanModuleOptions> {
  return apiRequest<PlanModuleOptions>("plans/options/");
}

export function listPlans(filters: Record<string, string | number | undefined>): Promise<PaginatedResult<FuneralPlanListItem>> {
  return apiRequest<PaginatedResult<FuneralPlanListItem>>(`plans/${queryString(filters)}`);
}

export function getPlan(id: number | string): Promise<FuneralPlanDetail> {
  return apiRequest<FuneralPlanDetail>(`plans/${id}/`);
}

export function createPlan(payload: FuneralPlanPayload): Promise<FuneralPlanDetail> {
  return apiRequest<FuneralPlanDetail>("plans/", { method: "POST", body: JSON.stringify(payload) });
}

export function updatePlan(id: number, payload: Partial<FuneralPlanPayload>): Promise<FuneralPlanDetail> {
  return apiRequest<FuneralPlanDetail>(`plans/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function changePlanStatus(id: number, active: boolean): Promise<FuneralPlanDetail> {
  return apiRequest<FuneralPlanDetail>(`plans/${id}/${active ? "activate" : "deactivate"}/`, { method: "POST" });
}

export function duplicatePlan(id: number): Promise<FuneralPlanDetail> {
  return apiRequest<FuneralPlanDetail>(`plans/${id}/duplicate/`, { method: "POST" });
}

export function listServices(filters: Record<string, string | number | undefined>): Promise<PaginatedResult<ServiceCatalogItem>> {
  return apiRequest<PaginatedResult<ServiceCatalogItem>>(`plans/services/${queryString(filters)}`);
}

export function createService(payload: ServicePayload): Promise<ServiceCatalogItem> {
  return apiRequest<ServiceCatalogItem>("plans/services/", { method: "POST", body: JSON.stringify(payload) });
}

export function updateService(id: number, payload: Partial<ServicePayload>): Promise<ServiceCatalogItem> {
  return apiRequest<ServiceCatalogItem>(`plans/services/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function changeServiceStatus(id: number, active: boolean): Promise<ServiceCatalogItem> {
  return apiRequest<ServiceCatalogItem>(`plans/services/${id}/${active ? "activate" : "deactivate"}/`, { method: "POST" });
}
