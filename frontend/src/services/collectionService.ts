import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  AgingSummary, CollectionAction, CollectionDetail, CollectionOptions, FollowUpAgenda,
  PaginatedPortfolio, PaymentPromise, PortfolioSummary,
} from "../types/collection";

export function collectionQuery(filters: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return params.size ? `?${params}` : "";
}
export const listPortfolio = (filters: Record<string, string | number | undefined>) => apiRequest<PaginatedPortfolio>(`collections/portfolio/${collectionQuery(filters)}`);
export const getPortfolioSummary = (filters: Record<string, string | number | undefined> = {}) => apiRequest<PortfolioSummary>(`collections/portfolio/summary/${collectionQuery(filters)}`);
export const getAgingSummary = (filters: Record<string, string | number | undefined> = {}) => apiRequest<AgingSummary>(`collections/portfolio/aging/${collectionQuery(filters)}`);
export const getCollectionOptions = () => apiRequest<CollectionOptions>("collections/portfolio/options/");
export const getContractCollection = (id: number) => apiRequest<CollectionDetail>(`collections/portfolio/contracts/${id}/`);
export const getFollowUps = () => apiRequest<FollowUpAgenda>("collections/collection-follow-ups/");
export const createCollectionAction = (payload: Record<string, unknown>) => apiRequest<CollectionAction>("collections/collection-actions/", { method: "POST", body: JSON.stringify(payload) });
export const createPaymentPromise = (payload: Record<string, unknown>) => apiRequest<PaymentPromise>("collections/payment-promises/", { method: "POST", body: JSON.stringify(payload) });
export const downloadPortfolio = (format: "xlsx" | "pdf", filters: Record<string, string | number | undefined>) => apiBlobRequest(`collections/portfolio/export.${format}${collectionQuery(filters)}`);

