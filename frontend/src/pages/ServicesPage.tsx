import { Edit3, Filter, Library, Plus, Search, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { Pagination } from "../components/Pagination";
import { PlanTabs } from "../components/plans/PlanTabs";
import { ServiceModal } from "../components/plans/ServiceModal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { changeServiceStatus, getPlanOptions, listServices } from "../services/planService";
import type { PaginatedResult, PlanModuleOptions, ServiceCatalogItem } from "../types/plan";
import { formatCurrency } from "../utils/format";

const emptyPage: PaginatedResult<ServiceCatalogItem> = { count: 0, page: 1, page_size: 12, total_pages: 1, next: null, previous: null, results: [] };

export function ServicesPage() {
  useDocumentTitle("Catálogo de servicios");
  const { user } = useAuth();
  const { showToast } = useToast();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [data, setData] = useState(emptyPage);
  const [options, setOptions] = useState<PlanModuleOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ServiceCatalogItem | null>(null);
  const [statusTarget, setStatusTarget] = useState<ServiceCatalogItem | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const permissions = user?.permisos.planes;
  const queryKey = params.toString();

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await listServices({ ...Object.fromEntries(params.entries()), page: Number(params.get("page") || 1) })); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar el catálogo."); }
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

  const activeFilters = useMemo(() => ["category", "is_active"].filter((key) => params.get(key)).length, [queryKey]);
  function setFilter(name: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(name, value); else next.delete(name); next.delete("page"); setParams(next); }
  function clearFilters() { setSearch(""); setParams({}); }
  function openCreate() { setEditing(null); setModalOpen(true); }
  function openEdit(service: ServiceCatalogItem) { setEditing(service); setModalOpen(true); }
  async function confirmStatus() {
    if (!statusTarget) return; setActionLoading(true);
    try { await changeServiceStatus(statusTarget.id, !statusTarget.is_active); showToast(statusTarget.is_active ? "Servicio inactivado." : "Servicio reactivado."); setStatusTarget(null); await load(); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cambiar el estado.", "error"); }
    finally { setActionLoading(false); }
  }

  return <div className="module-page plans-module-page">
    <header className="module-header"><div><p className="section-kicker">Oferta comercial</p><h2>Planes y servicios</h2><p>Configura lo que ofrece la funeraria y las prestaciones que componen cada plan.</p></div>{permissions?.manage_services && <button className="primary-action" type="button" onClick={openCreate}><Plus size={18} /> Agregar servicio</button>}</header>
    <PlanTabs />
    <section className="customer-toolbar" aria-label="Búsqueda y filtros del catálogo">
      <label className="search-control"><Search size={18} /><span className="sr-only">Buscar servicios</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por código, nombre o descripción…" />{search && <button type="button" onClick={() => setSearch("")} aria-label="Limpiar búsqueda"><X size={16} /></button>}</label>
      <button className={`filter-toggle ${filtersOpen ? "filter-toggle--active" : ""}`} type="button" onClick={() => setFiltersOpen((open) => !open)}><SlidersHorizontal size={17} /> Filtros {activeFilters > 0 && <span>{activeFilters}</span>}</button>
      <select aria-label="Ordenar servicios" value={params.get("ordering") ?? "name"} onChange={(e) => setFilter("ordering", e.target.value)}><option value="name">Nombre A–Z</option><option value="-name">Nombre Z–A</option><option value="code">Código</option><option value="-created_at">Más recientes</option></select>
    </section>
    {filtersOpen && <section className="filters-panel filters-panel--compact"><div className="filter-field"><label htmlFor="service-category">Categoría</label><select id="service-category" value={params.get("category") ?? ""} onChange={(e) => setFilter("category", e.target.value)}><option value="">Todas</option>{options?.categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div><div className="filter-field"><label htmlFor="service-status">Estado</label><select id="service-status" value={params.get("is_active") ?? ""} onChange={(e) => setFilter("is_active", e.target.value)}><option value="">Todos</option><option value="true">Activos</option><option value="false">Inactivos</option></select></div><button type="button" className="clear-filters" onClick={clearFilters}><X size={15} /> Limpiar filtros</button></section>}
    {error && <div className="module-error"><span>{error}</span><button type="button" onClick={() => void load()}>Reintentar</button></div>}
    <section className="data-card" aria-busy={loading}><div className="data-card__summary"><span>{loading ? "Cargando…" : `${data.count} ${data.count === 1 ? "servicio" : "servicios"}`}</span>{activeFilters > 0 && <span className="filtered-label"><Filter size={13} /> Vista filtrada</span>}</div>
      {loading ? <div className="catalog-grid catalog-grid--loading">{Array.from({ length: 6 }).map((_, index) => <div className="catalog-card skeleton-card" key={index} />)}</div> : data.results.length === 0 ? <div className="empty-state"><span className="empty-state__icon"><Library size={28} /></span><h3>{search || activeFilters ? "No encontramos servicios" : "El catálogo todavía no tiene servicios"}</h3><p>{search || activeFilters ? "Prueba otros términos o limpia los filtros." : "Agrega prestaciones para construir planes funerarios normalizados."}</p>{search || activeFilters ? <button className="secondary-button" type="button" onClick={clearFilters}>Limpiar filtros</button> : permissions?.manage_services && <button className="primary-action" type="button" onClick={openCreate}><Plus size={17} /> Agregar servicio</button>}</div> : <div className="catalog-grid">{data.results.map((service) => <article className={`catalog-card ${!service.is_active ? "catalog-card--inactive" : ""}`} key={service.id}><header><div><span className="catalog-code">{service.code}</span><h3>{service.name}</h3></div><span className={`status-dot status-dot--${service.is_active ? "active" : "inactive"}`}>{service.is_active ? "Activo" : "Inactivo"}</span></header><p>{service.description || "Sin descripción adicional."}</p><div className="catalog-tags"><span>{service.category_label}</span><span>Por {service.unit_label.toLowerCase()}</span></div><dl className="catalog-money">{permissions?.view_costs && <div><dt>Costo estimado</dt><dd>{formatCurrency(service.estimated_cost)}</dd></div>}<div><dt>Precio sugerido</dt><dd>{formatCurrency(service.default_sale_price)}</dd></div></dl>{permissions?.manage_services && <footer><button type="button" onClick={() => openEdit(service)}><Edit3 size={15} /> Editar</button>{permissions.change_status && <button type="button" className={service.is_active ? "danger-text" : ""} onClick={() => setStatusTarget(service)}>{service.is_active ? "Inactivar" : "Reactivar"}</button>}</footer>}</article>)}</div>}
      {!loading && data.count > 0 && <Pagination page={data.page} totalPages={data.total_pages} hasNext={Boolean(data.next)} hasPrevious={Boolean(data.previous)} onChange={(page) => setFilter("page", String(page))} />}
    </section>
    {options && <ServiceModal open={modalOpen} service={editing} options={options} onClose={() => setModalOpen(false)} onSaved={(message) => { setModalOpen(false); showToast(message); void load(); }} />}
    <ConfirmModal open={Boolean(statusTarget)} title={`${statusTarget?.is_active ? "Inactivar" : "Reactivar"} servicio`} description={statusTarget?.is_active ? "El servicio dejará de estar disponible para nuevas configuraciones, pero permanecerá en los planes existentes." : "El servicio podrá volver a agregarse a nuevos planes."} confirmLabel={statusTarget?.is_active ? "Sí, inactivar" : "Sí, reactivar"} tone={statusTarget?.is_active ? "danger" : "primary"} loading={actionLoading} onConfirm={() => void confirmStatus()} onCancel={() => !actionLoading && setStatusTarget(null)} />
  </div>;
}
