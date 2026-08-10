import { ChevronLeft, ChevronRight, Eye, Filter, Plus, Search, SlidersHorizontal, UserRound, Users, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { changeCustomerStatus, getCustomerOptions, listCustomers } from "../services/customerService";
import type { CustomerListItem, CustomerModuleOptions, PaginatedCustomers } from "../types/customer";
import { formatDate } from "../utils/format";

const emptyPage: PaginatedCustomers = { count: 0, page: 1, page_size: 12, total_pages: 1, next: null, previous: null, results: [] };

export function CustomersPage() {
  useDocumentTitle("Clientes");
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [data, setData] = useState<PaginatedCustomers>(emptyPage);
  const [options, setOptions] = useState<CustomerModuleOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<CustomerListItem | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const permission = user?.permisos.clientes;
  const queryKey = searchParams.toString();

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const filters = Object.fromEntries(searchParams.entries());
      const result = await listCustomers({ ...filters, page: Number(filters.page || 1) });
      setData(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible cargar los clientes.");
    } finally {
      setLoading(false);
    }
  }, [queryKey]);

  useEffect(() => { void loadCustomers(); }, [loadCustomers]);
  useEffect(() => {
    void getCustomerOptions().then(setOptions).catch(() => setError("No fue posible cargar las opciones del módulo."));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const current = searchParams.get("search") ?? "";
      if (search.trim() === current) return;
      const next = new URLSearchParams(searchParams);
      if (search.trim()) next.set("search", search.trim()); else next.delete("search");
      next.delete("page");
      setSearchParams(next);
    }, 450);
    return () => window.clearTimeout(timer);
  }, [search, searchParams, setSearchParams]);

  const activeFilterCount = useMemo(
    () => ["is_active", "branch", "department", "created_from", "created_to"].filter((key) => searchParams.get(key)).length,
    [queryKey],
  );

  function setFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(name, value); else next.delete(name);
    next.delete("page");
    setSearchParams(next);
  }

  function clearFilters() {
    setSearch("");
    setSearchParams({});
  }

  async function confirmStatusChange() {
    if (!statusTarget) return;
    setStatusLoading(true);
    try {
      await changeCustomerStatus(statusTarget.id, !statusTarget.is_active);
      showToast(statusTarget.is_active ? "Cliente inactivado." : "Cliente reactivado.");
      setStatusTarget(null);
      await loadCustomers();
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "No fue posible cambiar el estado.", "error");
    } finally {
      setStatusLoading(false);
    }
  }

  return (
    <div className="module-page customers-page">
      <header className="module-header">
        <div>
          <p className="section-kicker">Gestión de personas</p>
          <h2>Clientes</h2>
          <p>Administra la información de clientes, beneficiarios y contactos de referencia.</p>
        </div>
        {permission?.create && <Link className="primary-action" to="/clientes/nuevo"><Plus size={18} /> Registrar cliente</Link>}
      </header>

      <section className="customer-toolbar" aria-label="Búsqueda y filtros">
        <label className="search-control">
          <Search size={18} aria-hidden="true" />
          <span className="sr-only">Buscar clientes</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre, código, identidad o teléfono…" />
          {search && <button type="button" onClick={() => setSearch("")} aria-label="Limpiar búsqueda"><X size={16} /></button>}
        </label>
        <button className={`filter-toggle ${filtersOpen ? "filter-toggle--active" : ""}`} type="button" onClick={() => setFiltersOpen((open) => !open)} aria-expanded={filtersOpen}>
          <SlidersHorizontal size={17} /> Filtros {activeFilterCount > 0 && <span>{activeFilterCount}</span>}
        </button>
        <select aria-label="Ordenar clientes" value={searchParams.get("ordering") ?? "-created_at"} onChange={(event) => setFilter("ordering", event.target.value)}>
          <option value="-created_at">Más recientes</option>
          <option value="created_at">Más antiguos</option>
          <option value="name">Nombre A–Z</option>
          <option value="-name">Nombre Z–A</option>
          <option value="customer_code">Código ascendente</option>
          <option value="-updated_at">Última actualización</option>
        </select>
      </section>

      {filtersOpen && (
        <section className="filters-panel">
          <div className="filter-field"><label htmlFor="status-filter">Estado</label><select id="status-filter" value={searchParams.get("is_active") ?? ""} onChange={(e) => setFilter("is_active", e.target.value)}><option value="">Todos</option><option value="true">Activos</option><option value="false">Inactivos</option></select></div>
          <div className="filter-field"><label htmlFor="branch-filter">Sucursal</label><select id="branch-filter" value={searchParams.get("branch") ?? ""} onChange={(e) => setFilter("branch", e.target.value)}><option value="">Todas</option>{options?.branches.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select></div>
          <div className="filter-field"><label htmlFor="department-filter">Departamento</label><select id="department-filter" value={searchParams.get("department") ?? ""} onChange={(e) => setFilter("department", e.target.value)}><option value="">Todos</option>{options?.departments.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></div>
          <div className="filter-field"><label htmlFor="created-from">Desde</label><input id="created-from" type="date" value={searchParams.get("created_from") ?? ""} onChange={(e) => setFilter("created_from", e.target.value)} /></div>
          <div className="filter-field"><label htmlFor="created-to">Hasta</label><input id="created-to" type="date" value={searchParams.get("created_to") ?? ""} onChange={(e) => setFilter("created_to", e.target.value)} /></div>
          <button type="button" className="clear-filters" onClick={clearFilters}><X size={15} /> Limpiar filtros</button>
        </section>
      )}

      {error && <div className="module-error" role="alert"><span>{error}</span><button type="button" onClick={() => void loadCustomers()}>Reintentar</button></div>}

      <section className="data-card" aria-busy={loading}>
        <div className="data-card__summary"><span>{loading ? "Cargando…" : `${data.count} ${data.count === 1 ? "cliente" : "clientes"}`}</span>{activeFilterCount > 0 && <span className="filtered-label"><Filter size={13} /> Vista filtrada</span>}</div>
        {loading ? (
          <div className="table-skeleton" role="status"><span className="sr-only">Cargando clientes</span>{Array.from({ length: 6 }).map((_, index) => <div key={index}><i /><i /><i /><i /></div>)}</div>
        ) : data.results.length === 0 ? (
          <div className="empty-state"><span className="empty-state__icon"><Users size={28} /></span><h3>{search || activeFilterCount ? "No encontramos clientes" : "No hay clientes registrados"}</h3><p>{search || activeFilterCount ? "Prueba con otros términos o limpia los filtros aplicados." : "Registra el primer cliente para comenzar a gestionar su información."}</p>{search || activeFilterCount ? <button type="button" className="secondary-button" onClick={clearFilters}>Limpiar filtros</button> : permission?.create && <Link className="primary-action" to="/clientes/nuevo"><Plus size={17} /> Registrar primer cliente</Link>}</div>
        ) : (
          <>
            <div className="customer-table-wrap">
              <table className="customer-table">
                <thead><tr><th>Cliente</th><th>Identidad</th><th>Contacto</th><th>Sucursal</th><th>Beneficiarios</th><th>Estado</th><th>Registro</th><th><span className="sr-only">Acciones</span></th></tr></thead>
                <tbody>{data.results.map((customer) => (
                  <tr key={customer.id} onDoubleClick={() => navigate(`/clientes/${customer.id}`)}>
                    <td><div className="customer-cell"><span><UserRound size={17} /></span><div><Link to={`/clientes/${customer.id}`}>{customer.full_name}</Link><small>{customer.customer_code}</small></div></div></td>
                    <td>{customer.identity_number || <span className="muted-value">Sin identidad</span>}</td>
                    <td><strong className="cell-primary">{customer.phone}</strong>{customer.email && <small className="cell-secondary">{customer.email}</small>}</td>
                    <td>{customer.branch?.name ?? <span className="muted-value">Sin sucursal</span>}</td>
                    <td><span className="count-pill">{customer.beneficiaries_count}</span></td>
                    <td><button type="button" className={`status-pill status-pill--${customer.is_active ? "active" : "inactive"}`} onClick={() => permission?.change_status && setStatusTarget(customer)} disabled={!permission?.change_status}>{customer.is_active ? "Activo" : "Inactivo"}</button></td>
                    <td>{formatDate(customer.created_at)}</td>
                    <td><Link className="row-action" to={`/clientes/${customer.id}`} aria-label={`Ver ficha de ${customer.full_name}`}><Eye size={18} /></Link></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="customer-cards">{data.results.map((customer) => (
              <article className="customer-mobile-card" key={customer.id}>
                <div className="customer-mobile-card__top"><div><small>{customer.customer_code}</small><Link to={`/clientes/${customer.id}`}>{customer.full_name}</Link></div><span className={`status-dot status-dot--${customer.is_active ? "active" : "inactive"}`}>{customer.is_active ? "Activo" : "Inactivo"}</span></div>
                <dl><div><dt>Teléfono</dt><dd>{customer.phone}</dd></div><div><dt>Sucursal</dt><dd>{customer.branch?.name ?? "Sin sucursal"}</dd></div><div><dt>Identidad</dt><dd>{customer.identity_number ?? "No registrada"}</dd></div><div><dt>Beneficiarios</dt><dd>{customer.beneficiaries_count}</dd></div></dl>
                <Link to={`/clientes/${customer.id}`}>Abrir ficha <ChevronRight size={16} /></Link>
              </article>
            ))}</div>
          </>
        )}
        {!loading && data.count > 0 && <footer className="pagination"><span>Página {data.page} de {data.total_pages}</span><div><button type="button" disabled={!data.previous} onClick={() => setFilter("page", String(data.page - 1))}><ChevronLeft size={16} /> Anterior</button><button type="button" disabled={!data.next} onClick={() => setFilter("page", String(data.page + 1))}>Siguiente <ChevronRight size={16} /></button></div></footer>}
      </section>

      <ConfirmModal
        open={Boolean(statusTarget)}
        title={`${statusTarget?.is_active ? "Inactivar" : "Reactivar"} cliente`}
        description={statusTarget?.is_active ? `¿Deseas inactivar a ${statusTarget.full_name}? El cliente permanecerá en el historial y podrá reactivarse posteriormente.` : `¿Deseas reactivar a ${statusTarget?.full_name}? El registro volverá a estar habilitado operativamente.`}
        confirmLabel={statusTarget?.is_active ? "Sí, inactivar" : "Sí, reactivar"}
        tone={statusTarget?.is_active ? "danger" : "primary"}
        loading={statusLoading}
        onConfirm={() => void confirmStatusChange()}
        onCancel={() => !statusLoading && setStatusTarget(null)}
      />
    </div>
  );
}
