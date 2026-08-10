import { CalendarClock, CircleAlert, Clock3, Search, WalletCards } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { Pagination } from "../components/Pagination";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { getInstallmentOptions, getInstallmentSummary, listInstallments } from "../services/installmentService";
import type { InstallmentModuleOptions, InstallmentSummary, PaginatedInstallments } from "../types/installment";
import { formatCurrency, formatDate } from "../utils/format";

const emptyList: PaginatedInstallments = { count: 0, page: 1, page_size: 20, total_pages: 0, next: null, previous: null, results: [] };

export function InstallmentsPage() {
  useDocumentTitle("Cuotas");
  const [options, setOptions] = useState<InstallmentModuleOptions | null>(null);
  const [summary, setSummary] = useState<InstallmentSummary | null>(null);
  const [data, setData] = useState(emptyList);
  const [filters, setFilters] = useState({ search: "", status: "", preset: "", date_from: "", date_to: "", branch: "", seller: "", plan: "", ordering: "due_date", page: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [items, totals] = await Promise.all([listInstallments(filters), getInstallmentSummary()]);
      setData(items); setSummary(totals);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar las cuotas."); }
    finally { setLoading(false); }
  }, [filters]);
  useEffect(() => { getInstallmentOptions().then(setOptions).catch(() => setError("No fue posible cargar las opciones.")); }, []);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer); }, [load]);
  const update = (field: string, value: string | number) => setFilters((current) => ({ ...current, [field]: value, page: field === "page" ? Number(value) : 1 }));

  return <div className="module-page installments-page">
    <header className="module-heading"><div><p className="section-kicker">Cartera programada</p><h2>Cuotas</h2><p>Obligaciones contractuales pendientes. Los pagos y recibos se registrarán en un sprint posterior.</p></div></header>
    <section className="installment-metrics">
      <article><span><CalendarClock size={19} /></span><div><small>Vencen hoy</small><strong>{summary?.due_today ?? "—"}</strong></div></article>
      <article className="metric-overdue"><span><Clock3 size={19} /></span><div><small>Vencidas</small><strong>{summary?.overdue ?? "—"}</strong></div></article>
      <article><span><WalletCards size={19} /></span><div><small>Programado este mes</small><strong>{summary ? formatCurrency(summary.scheduled_this_month) : "—"}</strong></div></article>
    </section>
    <section className="filter-panel installment-filters">
      <label className="search-field"><Search size={17} /><input value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Contrato, cliente o código" /></label>
      <select value={filters.status} onChange={(e) => update("status", e.target.value)} aria-label="Estado"><option value="">Todos los estados</option>{options?.statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.preset} onChange={(e) => update("preset", e.target.value)} aria-label="Periodo"><option value="">Cualquier periodo</option><option value="today">Hoy</option><option value="week">Próximos 7 días</option><option value="month">Este mes</option><option value="overdue">Vencidas</option></select>
      <select value={filters.branch} onChange={(e) => update("branch", e.target.value)} aria-label="Sucursal"><option value="">Todas las sucursales</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select value={filters.seller} onChange={(e) => update("seller", e.target.value)} aria-label="Vendedor"><option value="">Todos los vendedores</option>{options?.sellers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select value={filters.plan} onChange={(e) => update("plan", e.target.value)} aria-label="Plan"><option value="">Todos los planes</option>{options?.plans.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <label><span>Desde</span><input type="date" value={filters.date_from} onChange={(e) => update("date_from", e.target.value)} /></label>
      <label><span>Hasta</span><input type="date" value={filters.date_to} onChange={(e) => update("date_to", e.target.value)} /></label>
    </section>
    {error && <div className="inline-error"><CircleAlert size={17} />{error}<button onClick={() => void load()}>Reintentar</button></div>}
    <section className="data-card installment-table-card">
      {loading ? <div className="table-loading">Cargando obligaciones…</div> : data.results.length === 0 ? <div className="empty-state"><CalendarClock size={30} /><h3>No hay cuotas con estos filtros</h3><p>Ajusta la búsqueda o el periodo para revisar otra parte de la cartera.</p></div> : <>
        <div className="table-scroll"><table className="data-table installment-table"><thead><tr><th>Vencimiento</th><th>Contrato / cliente</th><th>Cuota</th><th>Monto</th><th>Pendiente</th><th>Estado</th><th>Sucursal</th></tr></thead><tbody>{data.results.map((item) => <tr key={item.id}><td><strong>{formatDate(item.due_date)}</strong></td><td><Link to={`/contratos/${item.contract}`}>{item.contract_number}</Link><small>{item.customer_name} · {item.customer_code}</small></td><td>#{item.installment_number} <small>v{item.schedule_version}</small></td><td>{formatCurrency(item.current_amount)}</td><td>{formatCurrency(item.pending_amount)}</td><td><span className={`installment-status installment-status--${item.effective_status}`}>{item.effective_status_label}</span></td><td>{item.branch_name}<small>{item.seller_name}</small></td></tr>)}</tbody></table></div>
        <Pagination page={data.page} totalPages={data.total_pages} hasNext={Boolean(data.next)} hasPrevious={Boolean(data.previous)} onChange={(page) => update("page", page)} />
      </>}
    </section>
  </div>;
}
