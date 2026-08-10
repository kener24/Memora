import { ArrowRight, BadgeDollarSign, Copy, Filter, Layers3, MapPin, Plus, Search, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { Pagination } from "../components/Pagination";
import { PlanTabs } from "../components/plans/PlanTabs";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { changePlanStatus, duplicatePlan, getPlanOptions, listPlans } from "../services/planService";
import type { FuneralPlanListItem, PaginatedResult, PlanModuleOptions } from "../types/plan";
import { formatCurrency } from "../utils/format";

const emptyPage: PaginatedResult<FuneralPlanListItem> = { count: 0, page: 1, page_size: 12, total_pages: 1, next: null, previous: null, results: [] };

export function PlansPage() {
  useDocumentTitle("Planes funerarios");
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [data, setData] = useState(emptyPage);
  const [options, setOptions] = useState<PlanModuleOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<FuneralPlanListItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);
  const permissions = user?.permisos.planes;
  const queryKey = params.toString();

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await listPlans({ ...Object.fromEntries(params.entries()), page: Number(params.get("page") || 1) })); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar los planes."); }
    finally { setLoading(false); }
  }, [queryKey]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void getPlanOptions().then(setOptions).catch(() => setError("No fue posible cargar las opciones.")); }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (search.trim() === (params.get("search") ?? "")) return;
      const next = new URLSearchParams(params); if (search.trim()) next.set("search", search.trim()); else next.delete("search"); next.delete("page"); setParams(next);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [search, params, setParams]);

  const activeFilters = useMemo(() => ["is_active", "branch", "allow_financing", "min_price", "max_price"].filter((key) => params.get(key)).length, [queryKey]);
  function setFilter(name: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(name, value); else next.delete(name); if (name !== "page") next.delete("page"); setParams(next); }
  function clearFilters() { setSearch(""); setParams({}); }
  async function confirmStatus() {
    if (!statusTarget) return; setActionLoading(true);
    try { await changePlanStatus(statusTarget.id, !statusTarget.is_active); showToast(statusTarget.is_active ? "Plan inactivado." : "Plan reactivado."); setStatusTarget(null); await load(); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cambiar el estado.", "error"); }
    finally { setActionLoading(false); }
  }
  async function handleDuplicate(plan: FuneralPlanListItem) {
    setDuplicatingId(plan.id);
    try { const created = await duplicatePlan(plan.id); showToast("Plan duplicado correctamente."); navigate(`/planes/${created.id}`); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible duplicar el plan.", "error"); }
    finally { setDuplicatingId(null); }
  }

  return <div className="module-page plans-module-page">
    <header className="module-header"><div><p className="section-kicker">Oferta comercial</p><h2>Planes funerarios</h2><p>Crea productos claros, calcula su estimación y controla dónde están disponibles.</p></div>{permissions?.create && <Link className="primary-action" to="/planes/nuevo"><Plus size={18} /> Crear plan</Link>}</header>
    <PlanTabs />
    <section className="customer-toolbar" aria-label="Búsqueda y filtros de planes"><label className="search-control"><Search size={18} /><span className="sr-only">Buscar planes</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por código, nombre o descripción…" />{search && <button type="button" onClick={() => setSearch("")} aria-label="Limpiar búsqueda"><X size={16} /></button>}</label><button className={`filter-toggle ${filtersOpen ? "filter-toggle--active" : ""}`} type="button" onClick={() => setFiltersOpen((open) => !open)}><SlidersHorizontal size={17} /> Filtros {activeFilters > 0 && <span>{activeFilters}</span>}</button><select aria-label="Ordenar planes" value={params.get("ordering") ?? "-created_at"} onChange={(e) => setFilter("ordering", e.target.value)}><option value="-created_at">Más recientes</option><option value="name">Nombre A–Z</option><option value="base_price">Menor precio</option><option value="-base_price">Mayor precio</option><option value="code">Código</option></select></section>
    {filtersOpen && <section className="filters-panel"><div className="filter-field"><label htmlFor="plan-status">Estado</label><select id="plan-status" value={params.get("is_active") ?? ""} onChange={(e) => setFilter("is_active", e.target.value)}><option value="">Todos</option><option value="true">Activos</option><option value="false">Inactivos</option></select></div><div className="filter-field"><label htmlFor="plan-branch">Sucursal</label><select id="plan-branch" value={params.get("branch") ?? ""} onChange={(e) => setFilter("branch", e.target.value)}><option value="">Todas</option>{options?.branches.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select></div><div className="filter-field"><label htmlFor="plan-financing">Financiamiento</label><select id="plan-financing" value={params.get("allow_financing") ?? ""} onChange={(e) => setFilter("allow_financing", e.target.value)}><option value="">Todos</option><option value="true">Permite</option><option value="false">No permite</option></select></div><div className="filter-field"><label htmlFor="min-price">Precio mínimo</label><input id="min-price" type="number" min="0" value={params.get("min_price") ?? ""} onChange={(e) => setFilter("min_price", e.target.value)} /></div><div className="filter-field"><label htmlFor="max-price">Precio máximo</label><input id="max-price" type="number" min="0" value={params.get("max_price") ?? ""} onChange={(e) => setFilter("max_price", e.target.value)} /></div><button type="button" className="clear-filters" onClick={clearFilters}><X size={15} /> Limpiar filtros</button></section>}
    {error && <div className="module-error"><span>{error}</span><button type="button" onClick={() => void load()}>Reintentar</button></div>}
    <section className="data-card" aria-busy={loading}><div className="data-card__summary"><span>{loading ? "Cargando…" : `${data.count} ${data.count === 1 ? "plan" : "planes"}`}</span>{activeFilters > 0 && <span className="filtered-label"><Filter size={13} /> Vista filtrada</span>}</div>
      {loading ? <div className="plans-grid">{Array.from({ length: 6 }).map((_, index) => <div className="plan-card skeleton-card" key={index} />)}</div> : data.results.length === 0 ? <div className="empty-state"><span className="empty-state__icon"><Layers3 size={28} /></span><h3>{search || activeFilters ? "No encontramos planes" : "No hay planes funerarios registrados"}</h3><p>{search || activeFilters ? "Prueba otros términos o limpia los filtros." : "Crea el primer producto comercial de la funeraria."}</p>{search || activeFilters ? <button className="secondary-button" type="button" onClick={clearFilters}>Limpiar filtros</button> : permissions?.create && <Link className="primary-action" to="/planes/nuevo"><Plus size={17} /> Crear primer plan</Link>}</div> : <div className="plans-grid">{data.results.map((plan) => <article className={`plan-card ${!plan.is_active ? "plan-card--inactive" : ""}`} key={plan.id}><header><div><span className="catalog-code">{plan.code}</span><Link to={`/planes/${plan.id}`}>{plan.name}</Link></div><span className={`status-dot status-dot--${plan.is_active ? "active" : "inactive"}`}>{plan.is_active ? "Activo" : "Inactivo"}</span></header><p>{plan.description || "Sin descripción adicional."}</p><div className="plan-price"><small>Precio de venta</small><strong>{formatCurrency(plan.base_price)}</strong></div>{permissions?.view_costs && <div className="plan-cost-strip"><div><span>Costo estimado</span><strong>{formatCurrency(plan.estimated_plan_cost)}</strong></div><div><span>Margen estimado</span><strong>{formatCurrency(plan.estimated_margin)}</strong></div></div>}<div className="plan-facts"><span><Layers3 size={14} /> {plan.items_count} prestaciones</span><span><MapPin size={14} /> {plan.available_all_branches ? "Todas las sucursales" : `${plan.availability.branches.length} sucursales`}</span>{plan.allow_financing && <span><BadgeDollarSign size={14} /> Financiamiento</span>}</div><footer><Link to={`/planes/${plan.id}`}>Ver detalle <ArrowRight size={15} /></Link>{permissions?.duplicate && <button type="button" disabled={duplicatingId === plan.id} onClick={() => void handleDuplicate(plan)}>{duplicatingId === plan.id ? <span className="button-spinner" /> : <Copy size={14} />} Duplicar</button>}{permissions?.change_status && <button type="button" className={plan.is_active ? "danger-text" : ""} onClick={() => setStatusTarget(plan)}>{plan.is_active ? "Inactivar" : "Reactivar"}</button>}</footer></article>)}</div>}
      {!loading && data.count > 0 && <Pagination page={data.page} totalPages={data.total_pages} hasNext={Boolean(data.next)} hasPrevious={Boolean(data.previous)} onChange={(page) => setFilter("page", String(page))} />}
    </section>
    <ConfirmModal open={Boolean(statusTarget)} title={`${statusTarget?.is_active ? "Inactivar" : "Reactivar"} plan`} description={statusTarget?.is_active ? "El plan dejará de estar disponible para nuevas ventas. Su historial permanecerá conservado." : "El plan volverá a estar disponible en las sucursales configuradas."} confirmLabel={statusTarget?.is_active ? "Sí, inactivar" : "Sí, reactivar"} tone={statusTarget?.is_active ? "danger" : "primary"} loading={actionLoading} onConfirm={() => void confirmStatus()} onCancel={() => !actionLoading && setStatusTarget(null)} />
  </div>;
}
