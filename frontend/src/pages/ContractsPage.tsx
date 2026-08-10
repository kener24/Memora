import { CircleAlert, FileSignature, Filter, Plus, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { Pagination } from "../components/Pagination";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { getContractOptions, listContracts } from "../services/contractService";
import type { ContractModuleOptions, PaginatedContracts } from "../types/contract";
import { formatCurrency, formatDate } from "../utils/format";

const emptyData: PaginatedContracts = { count: 0, page: 1, page_size: 15, total_pages: 1, next: null, previous: null, results: [] };

function statusClass(value: string) {
  return value === "active" ? "active" : value === "cancelled" ? "cancelled" : value === "completed" ? "completed" : "draft";
}

export function ContractsPage() {
  useDocumentTitle("Contratos");
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [data, setData] = useState(emptyData);
  const [options, setOptions] = useState<ContractModuleOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const queryKey = params.toString();

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await listContracts({ ...Object.fromEntries(params.entries()), page: Number(params.get("page") || 1) })); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar los contratos."); }
    finally { setLoading(false); }
  }, [queryKey]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void getContractOptions().then(setOptions).catch(() => setError("No fue posible cargar las opciones.")); }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (search.trim() === (params.get("search") ?? "")) return;
      const next = new URLSearchParams(params);
      if (search.trim()) next.set("search", search.trim()); else next.delete("search");
      next.delete("page"); setParams(next);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [search, params, setParams]);

  const filterCount = useMemo(() => ["status", "branch", "seller", "date_from", "date_to", "allow_financing"].filter((key) => params.get(key)).length, [queryKey]);
  function setFilter(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); next.delete("page"); setParams(next); }
  function clear() { setSearch(""); setParams({}); }

  return <div className="module-page contracts-page">
    <header className="module-header"><div><p className="section-kicker">Gestión comercial</p><h2>Contratos</h2><p>Ventas de planes funerarios con condiciones históricas, trazabilidad y documento contractual.</p></div>{user?.permisos.contratos.create && <Link className="primary-action" to="/contratos/nuevo"><Plus size={17} /> Nueva venta</Link>}</header>
    <div className="customer-toolbar contract-toolbar">
      <label className="search-control"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Contrato, cliente, identidad o beneficiario" />{search && <button type="button" onClick={() => setSearch("")} aria-label="Limpiar"><X size={15} /></button>}</label>
      <button type="button" className={`filter-toggle ${filterCount ? "filter-toggle--active" : ""}`} onClick={() => setFiltersOpen((open) => !open)}><Filter size={16} /> Filtros {filterCount > 0 && <span>{filterCount}</span>}</button>
      <select value={params.get("ordering") ?? "-created_at"} onChange={(e) => setFilter("ordering", e.target.value)}><option value="-created_at">Más recientes</option><option value="sale_date">Venta ascendente</option><option value="-sale_date">Venta descendente</option><option value="total_price">Menor valor</option><option value="-total_price">Mayor valor</option></select>
    </div>
    {filtersOpen && <section className="filters-panel contract-filters">
      <label className="filter-field"><span>Estado</span><select value={params.get("status") ?? ""} onChange={(e) => setFilter("status", e.target.value)}><option value="">Todos</option>{options?.statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label className="filter-field"><span>Sucursal</span><select value={params.get("branch") ?? ""} onChange={(e) => setFilter("branch", e.target.value)}><option value="">Todas</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="filter-field"><span>Vendedor</span><select value={params.get("seller") ?? ""} onChange={(e) => setFilter("seller", e.target.value)}><option value="">Todos</option>{options?.sellers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="filter-field"><span>Desde</span><input type="date" value={params.get("date_from") ?? ""} onChange={(e) => setFilter("date_from", e.target.value)} /></label>
      <label className="filter-field"><span>Hasta</span><input type="date" value={params.get("date_to") ?? ""} onChange={(e) => setFilter("date_to", e.target.value)} /></label>
      <label className="filter-field"><span>Modalidad</span><select value={params.get("allow_financing") ?? ""} onChange={(e) => setFilter("allow_financing", e.target.value)}><option value="">Todas</option><option value="true">Financiado</option><option value="false">Contado</option></select></label>
      <button className="clear-filters" type="button" onClick={clear}><X size={14} /> Limpiar</button>
    </section>}
    {error && <div className="module-error" role="alert"><CircleAlert size={18} /><span>{error}</span><button onClick={() => void load()}>Reintentar</button></div>}
    <section className="data-card"><div className="data-card__summary"><span>{data.count} contrato{data.count === 1 ? "" : "s"}</span>{filterCount > 0 && <span className="filtered-label"><Filter size={12} /> Vista filtrada</span>}</div>
      {loading ? <div className="table-skeleton">{Array.from({ length: 6 }, (_, index) => <div key={index}><i /><i /><i /><i /></div>)}</div> : data.results.length === 0 ? <div className="empty-state"><span className="empty-state__icon"><FileSignature size={25} /></span><h3>No hay contratos en esta vista</h3><p>Prueba otros filtros o inicia una venta nueva.</p>{user?.permisos.contratos.create && <Link className="primary-action" to="/contratos/nuevo"><Plus size={16} /> Nueva venta</Link>}</div> : <div className="customer-table-wrap"><table className="customer-table contract-table"><thead><tr><th>Contrato</th><th>Cliente / beneficiario</th><th>Plan</th><th>Venta</th><th>Vendedor</th><th>Total</th><th>Estado</th></tr></thead><tbody>{data.results.map((item) => <tr key={item.id}><td><Link className="contract-number-link" to={`/contratos/${item.id}`}>{item.contract_number}</Link><small className="cell-secondary">{item.branch_name}</small></td><td><strong className="cell-primary">{item.customer_name}</strong><small className="cell-secondary">Benef.: {item.beneficiary_name}</small></td><td>{item.plan_name}<small className="cell-secondary">{item.allow_financing ? "Financiado" : "Contado"}</small></td><td>{formatDate(item.sale_date)}</td><td>{item.seller_name}</td><td><strong>{formatCurrency(item.total_price)}</strong></td><td><span className={`contract-status contract-status--${statusClass(item.status)}`}>{item.status_label}</span></td></tr>)}</tbody></table></div>}
      {!loading && data.results.length > 0 && <Pagination page={data.page} totalPages={data.total_pages} hasNext={Boolean(data.next)} hasPrevious={Boolean(data.previous)} onChange={(page) => setFilter("page", String(page))} />}
    </section>
  </div>;
}
