import { apiBlobRequest, apiRequest } from "../api/client";
import type { PaginatedPortfolio } from "../types/collection";
import type {
  Assignment, CollectionRoute, Collector, CollectorMetrics, OperationsOptions, Paginated,
  Settlement, SettlementPreview, WorkSession, Zone,
} from "../types/collectionOperations";

function query(filters: Record<string, string | number | undefined> = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return params.size ? `?${params}` : "";
}
const json = (payload?: unknown) => payload === undefined ? undefined : JSON.stringify(payload);

export const getOperationsOptions = () => apiRequest<OperationsOptions>("collection-operations/options/");
export const listCollectors = (filters = {}) => apiRequest<Paginated<Collector>>(`collectors/${query(filters)}`);
export const updateCollector = (id: number, payload: { is_available?: boolean; notes?: string }) => apiRequest<Collector>(`collectors/${id}/`, { method: "PATCH", body: json(payload) });
export const getCollectorPortfolio = (id: number, filters = {}) => apiRequest<PaginatedPortfolio>(`collectors/${id}/portfolio/${query(filters)}`);
export const getCollectorMetrics = (id: number) => apiRequest<CollectorMetrics>(`collectors/${id}/metrics/`);
export const listAssignments = (filters = {}) => apiRequest<Paginated<Assignment>>(`collection-assignments/${query(filters)}`);
export const bulkAssign = (payload: { contracts: number[]; collector: number; reason?: string }) => apiRequest<Assignment[]>("collection-assignments/bulk/", { method: "POST", body: json(payload) });
export const reassign = (id: number, payload: { collector: number; reason: string }) => apiRequest<Assignment>(`collection-assignments/${id}/reassign/`, { method: "POST", body: json(payload) });
export const listZones = (filters = {}) => apiRequest<Paginated<Zone>>(`collection-zones/${query(filters)}`);
export const createZone = (payload: { branch: number; code: string; name: string; description?: string }) => apiRequest<Zone>("collection-zones/", { method: "POST", body: json(payload) });
export const updateZone = (id: number, payload: Partial<Zone>) => apiRequest<Zone>(`collection-zones/${id}/`, { method: "PATCH", body: json(payload) });
export const assignCustomerZone = (id: number, customer: number) => apiRequest(`collection-zones/${id}/assign-customer/`, { method: "POST", body: json({ customer }) });
export const listRoutes = (filters = {}) => apiRequest<Paginated<CollectionRoute>>(`collection-routes/${query(filters)}`);
export const createRoute = (payload: Record<string, unknown>) => apiRequest<CollectionRoute>("collection-routes/", { method: "POST", body: json(payload) });
export const updateRoute = (id: number, payload: Record<string, unknown>) => apiRequest<CollectionRoute>(`collection-routes/${id}/`, { method: "PATCH", body: json(payload) });
export const addRouteStop = (id: number, payload: { customer: number; notes?: string }) => apiRequest<CollectionRoute>(`collection-routes/${id}/stops/`, { method: "POST", body: json(payload) });
export const removeRouteStop = (route: number, stop: number) => apiRequest<CollectionRoute>(`collection-routes/${route}/stops/${stop}/remove/`, { method: "POST" });
export const reorderRoute = (id: number, stops: number[]) => apiRequest<CollectionRoute>(`collection-routes/${id}/reorder/`, { method: "POST", body: json({ stops }) });
export const recordRouteVisit = (stop: number, status: string, notes = "") => apiRequest(`collector/route-stops/${stop}/visit/`, { method: "POST", body: json({ status, notes }) });
export const getOwnPortfolio = (filters = {}) => apiRequest<PaginatedPortfolio>(`collector/portfolio/${query(filters)}`);
export const getTodayAgenda = () => apiRequest<PaginatedPortfolio>("collector/today/?page_size=100");
export const getOwnMetrics = () => apiRequest<CollectorMetrics>("collector/metrics/");
export const getOwnRoutes = (day?: number) => apiRequest<CollectionRoute[]>(`collector/routes/${query({ day })}`);
export const getCurrentSession = () => apiRequest<WorkSession | null>("collector-work-sessions/current/");
export const startSession = (notes = "") => apiRequest<WorkSession>("collector-work-sessions/start/", { method: "POST", body: json({ notes }) });
export const closeSession = (id: number, notes = "") => apiRequest<WorkSession>(`collector-work-sessions/${id}/close/`, { method: "POST", body: json({ notes }) });
export const listSettlements = (filters = {}) => apiRequest<Paginated<Settlement>>(`collector-settlements/${query(filters)}`);
export const previewSettlement = (work_session?: number) => apiRequest<SettlementPreview>("collector-settlements/preview/", { method: "POST", body: json(work_session ? { work_session } : {}) });
export const submitSettlement = (payload: { work_session: number; reported_cash: string; notes: string; payment_fingerprint: string }, key: string) => apiRequest<Settlement>("collector-settlements/submit/", { method: "POST", headers: { "Idempotency-Key": key }, body: json(payload) });
export const decideSettlement = (id: number, decision: "review" | "accept" | "reject", reason = "") => apiRequest<Settlement>(`collector-settlements/${id}/${decision}/`, { method: "POST", body: json({ reason }) });
export const downloadOperations = (path: string) => apiBlobRequest(path);
