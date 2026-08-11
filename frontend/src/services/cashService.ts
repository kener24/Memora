import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  CashCount, CashDashboard, CashMovement, CashOptions, CashRegister, CashSession,
  MovementTotals, Paginated, PendingSettlement, SettlementReception,
} from "../types/cash";

const json = (body: unknown) => JSON.stringify(body);
const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== "") search.set(key, String(value)); });
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
};
const idem = (key: string) => ({ "Idempotency-Key": key });

export const getCashOptions = () => apiRequest<CashOptions>("cash/options/");
export const getCashDashboard = () => apiRequest<CashDashboard>("cash/dashboard/");
export const getCurrentCashSession = () => apiRequest<CashSession | null>("cash/sessions/current/");
export const listCashRegisters = (params: Record<string, string | number | undefined> = {}) =>
  apiRequest<Paginated<CashRegister>>(`cash/registers/${query(params)}`);
export const createCashRegister = (payload: { branch: number; name: string; description: string }) =>
  apiRequest<CashRegister>("cash/registers/", { method: "POST", body: json(payload) });
export const updateCashRegister = (id: number, payload: Partial<Pick<CashRegister, "name" | "description" | "is_active">>) =>
  apiRequest<CashRegister>(`cash/registers/${id}/`, { method: "PATCH", body: json(payload) });
export const listCashSessions = (params: Record<string, string | number | undefined> = {}) =>
  apiRequest<Paginated<CashSession>>(`cash/sessions/${query(params)}`);
export const getCashSession = (id: number) => apiRequest<CashSession>(`cash/sessions/${id}/`);
export const openCashSession = (payload: { cash_register: number; opening_cash: string; notes: string }, key: string) =>
  apiRequest<CashSession>("cash/sessions/open/", { method: "POST", headers: idem(key), body: json(payload) });
export const performCashCount = (id: number, payload: { denominations?: Array<{ denomination: string; quantity: number }>; counted_cash?: string; difference_reason: string }, key: string) =>
  apiRequest<CashCount>(`cash/sessions/${id}/count/`, { method: "POST", headers: idem(key), body: json(payload) });
export const closeCashSession = (id: number, payload: { cash_count: number; notes: string }, key: string) =>
  apiRequest<CashSession>(`cash/sessions/${id}/close/`, { method: "POST", headers: idem(key), body: json(payload) });
export const listCashMovements = (params: Record<string, string | number | undefined> = {}) =>
  apiRequest<Paginated<CashMovement, MovementTotals>>(`cash/movements/${query(params)}`);
export const createCashMovement = (payload: { cash_session: number; direction: string; category: string; amount: string; payment_method: string; description: string; reference: string }, key: string) =>
  apiRequest<CashMovement>("cash/movements/", { method: "POST", headers: idem(key), body: json(payload) });
export const voidCashMovement = (id: number, reason: string) =>
  apiRequest<CashMovement>(`cash/movements/${id}/void/`, { method: "POST", body: json({ reason }) });
export const listPendingSettlements = () =>
  apiRequest<Paginated<PendingSettlement>>("cash/settlement-receptions/pending/?page_size=100");
export const listSettlementReceptions = (params: Record<string, string | number | undefined> = {}) =>
  apiRequest<Paginated<SettlementReception>>(`cash/settlement-receptions/${query(params)}`);
export const receiveSettlement = (payload: { cash_session: number; collector_settlement: number; cash_received_by_cashier: string; notes: string }, key: string) =>
  apiRequest<SettlementReception>("cash/settlement-receptions/", { method: "POST", headers: idem(key), body: json(payload) });
export const downloadCashClosingPdf = (id: number) => apiBlobRequest(`cash/sessions/${id}/closing-pdf/`);
export const downloadCashMovementsExcel = (params: Record<string, string | number | undefined> = {}) =>
  apiBlobRequest(`cash/movements/export.xlsx${query(params)}`);
