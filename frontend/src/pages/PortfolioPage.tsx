import {
  AlertTriangle, CalendarCheck, Download, FileSpreadsheet, HandCoins, History, Phone,
  Search, ShieldAlert, TrendingUp, UserRoundCheck, WalletCards,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { Pagination } from "../components/Pagination";
import { useToast } from "../contexts/ToastContext";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  createCollectionAction, downloadPortfolio, getAgingSummary, getCollectionOptions,
  getContractCollection, getFollowUps, getPortfolioSummary, listPortfolio,
} from "../services/collectionService";
import type {
  AgingSummary, CollectionDetail, CollectionOptions, FollowUpAgenda, PaginatedPortfolio,
  PortfolioRow, PortfolioSummary,
} from "../types/collection";
import { formatCurrency, formatDate, formatDateTime } from "../utils/format";

const emptyPortfolio: PaginatedPortfolio = {
  count: 0, page: 1, page_size: 25, total_pages: 0, next: null, previous: null, results: [],
  totals: { contracts: 0, customers: 0, pending: "0", overdue: "0", upcoming: "0", overdue_installments: 0 },
};
const today = new Date().toISOString().slice(0, 10);

export function PortfolioPage() {
  useDocumentTitle("Cartera y cobranza");
  const { showToast } = useToast();
  const { user } = useAuth();
  const [options, setOptions] = useState<CollectionOptions | null>(null);
  const [portfolio, setPortfolio] = useState<PaginatedPortfolio>(emptyPortfolio);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [aging, setAging] = useState<AgingSummary | null>(null);
  const [agenda, setAgenda] = useState<FollowUpAgenda | null>(null);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<"xlsx" | "pdf" | null>(null);
  const [actionTarget, setActionTarget] = useState<PortfolioRow | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [filters, setFilters] = useState<Record<string, string | number>>({
    search: "", status: "", preset: "", branch: "", seller: "", plan: "", ordering: "-days_overdue", page: 1,
  });

  const activeFilters = Object.fromEntries(Object.entries(filters).filter(([key]) => key !== "page"));
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [rows, totals, age] = await Promise.all([
        listPortfolio(filters), getPortfolioSummary(activeFilters), getAgingSummary(activeFilters),
      ]);
      setPortfolio(rows); setSummary(totals); setAging(age);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar la cartera."); }
    finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  useEffect(() => {
    Promise.all([getCollectionOptions(), getFollowUps()]).then(([available, followUps]) => {
      setOptions(available); setAgenda(followUps);
    }).catch(() => setError("No fue posible cargar las opciones de cobranza."));
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer); }, [load]);
  const update = (key: string, value: string | number) => setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));

  async function openDetail(contractId: number) {
    try { setDetail(await getContractCollection(contractId)); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible abrir el detalle.", "error"); }
  }
  async function exportFile(format: "xlsx" | "pdf") {
    setDownloading(format);
    try {
      const blob = await downloadPortfolio(format, activeFilters); const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = `Cartera_Memora.${format}`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible exportar.", "error"); }
    finally { setDownloading(null); }
  }
  async function saveAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!actionTarget) return;
    const form = new FormData(event.currentTarget); const outcome = String(form.get("outcome"));
    const payload: Record<string, unknown> = {
      contract: actionTarget.contract_id, action_type: form.get("action_type"), outcome,
      notes: form.get("notes"), next_follow_up_date: form.get("next_follow_up_date") || null,
    };
    if (outcome === "promise_to_pay") { payload.promised_amount = form.get("promised_amount"); payload.promised_date = form.get("promised_date"); }
    setSubmitting(true);
    try {
      await createCollectionAction(payload); showToast("Gestión registrada correctamente.", "success");
      setActionTarget(null); setAgenda(await getFollowUps()); await load();
      if (detail?.portfolio.contract_id === actionTarget.contract_id) setDetail(await getContractCollection(actionTarget.contract_id));
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible registrar la gestión.", "error"); }
    finally { setSubmitting(false); }
  }

  const agendaCount = (agenda?.overdue.length ?? 0) + (agenda?.today.length ?? 0);
  return <div className="module-page portfolio-page">
    <header className="module-heading portfolio-heading"><div><p className="section-kicker">Control financiero operativo</p><h2>Cartera y cobranza</h2><p>Saldos derivados de contratos, cuotas activas y pagos confirmados. Sin deuda ingresada manualmente.</p></div><div className="portfolio-actions">{options?.permissions.export_portfolio && <><button className="secondary-button" disabled={Boolean(downloading)} onClick={() => void exportFile("xlsx")}><FileSpreadsheet size={16} /> Excel</button><button className="secondary-button" disabled={Boolean(downloading)} onClick={() => void exportFile("pdf")}><Download size={16} /> PDF</button></>}</div></header>

    <section className="portfolio-kpis">
      <article><span><WalletCards size={19} /></span><small>Cartera pendiente</small><strong>{formatCurrency(summary?.pending_portfolio)}</strong><p>{portfolio.totals.contracts} contratos activos</p></article>
      <article className="kpi-overdue"><span><ShieldAlert size={19} /></span><small>Cartera vencida</small><strong>{formatCurrency(summary?.overdue_portfolio)}</strong><p>{summary?.overdue_customers ?? 0} clientes en mora</p></article>
      <article><span><TrendingUp size={19} /></span><small>Por vencer</small><strong>{formatCurrency(summary?.upcoming_portfolio)}</strong><p>{summary?.current_customers ?? 0} clientes al día</p></article>
      <article><span><HandCoins size={19} /></span><small>Cobrado este mes</small><strong>{formatCurrency(summary?.collected_this_month)}</strong><p>Solo pagos confirmados</p></article>
      <article className="kpi-critical"><span><AlertTriangle size={19} /></span><small>Prioridad crítica</small><strong>{summary?.critical_customers ?? 0}</strong><p>Más de 90 días o promesa rota</p></article>
    </section>

    <section className="aging-card"><header><div><p className="section-kicker">Antigüedad de saldos</p><h3>Distribución de cuotas vencidas</h3></div><strong>{formatCurrency(aging?.total_overdue)}</strong></header><div className="aging-grid">{aging?.buckets.map((bucket) => <button key={bucket.value} onClick={() => update("preset", bucket.value)}><span>{bucket.label}</span><strong>{formatCurrency(bucket.amount)}</strong><small>{bucket.installments} cuota{bucket.installments === 1 ? "" : "s"}</small></button>)}</div></section>

    <section className="filter-panel portfolio-filters">
      <label className="search-field"><Search size={17} /><input value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Contrato, cliente, identidad o teléfono" /></label>
      <select value={filters.status} onChange={(e) => update("status", e.target.value)}><option value="">Todos los estados</option>{options?.statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.preset} onChange={(e) => update("preset", e.target.value)}><option value="">Sin vista rápida</option><option value="due_today">Vence hoy</option><option value="next_7_days">Próximos 7 días</option><option value="over_90">Más de 90 días</option><option value="no_recent_payment">Sin pago reciente</option>{options?.aging_buckets.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.branch} onChange={(e) => update("branch", e.target.value)}><option value="">Todas las sucursales</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select value={filters.plan} onChange={(e) => update("plan", e.target.value)}><option value="">Todos los planes</option>{options?.plans.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select value={filters.ordering} onChange={(e) => update("ordering", e.target.value)}><option value="-days_overdue">Mayor mora</option><option value="-overdue">Mayor monto vencido</option><option value="-balance">Mayor saldo</option><option value="next_due">Próximo vencimiento</option><option value="customer">Cliente A–Z</option></select>
    </section>
    {error && <div className="inline-error"><AlertTriangle size={17} />{error}<button onClick={() => void load()}>Reintentar</button></div>}

    <section className="data-card portfolio-table-card">
      {loading ? <div className="table-loading">Calculando cartera…</div> : !portfolio.results.length ? <div className="empty-state"><UserRoundCheck size={30} /><h3>No hay contratos en esta vista</h3><p>Ajusta los filtros o revisa la cartera pagada.</p></div> : <><div className="table-scroll"><table className="data-table portfolio-table"><thead><tr><th>Cliente / contrato</th><th>Contacto</th><th>Saldo</th><th>Vencido</th><th>Mora</th><th>Próxima cuota</th><th>Estado</th><th>Prioridad</th><th>Gestión</th></tr></thead><tbody>{portfolio.results.map((row) => <tr key={row.contract_id}><td><button className="table-link" onClick={() => void openDetail(row.contract_id)}><strong>{row.customer_name}</strong><small>{row.contract_number} · {row.plan.name}</small></button></td><td>{row.phone ? <a className="phone-link" href={`tel:${row.phone}`}><Phone size={13} />{row.phone}</a> : "Sin teléfono"}<small>{row.branch.name}</small></td><td><strong>{formatCurrency(row.balance)}</strong><small>Pagado {formatCurrency(row.total_paid)}</small></td><td className="overdue-money">{formatCurrency(row.overdue_amount)}<small>{row.overdue_installments} cuota(s)</small></td><td><strong>{row.days_overdue} días</strong><small>{formatDate(row.oldest_overdue_date)}</small></td><td>{formatDate(row.next_due_date)}</td><td><span className={`collection-status collection-status--${row.collection_status}`}>{row.collection_status_label}</span></td><td><span className={`priority-badge priority-badge--${row.priority}`}>{row.priority_label}</span></td><td>{options?.permissions.create_action && <button className="table-icon-action" title="Registrar gestión" onClick={() => setActionTarget(row)}><History size={15} /></button>}</td></tr>)}</tbody></table></div><Pagination page={portfolio.page} totalPages={portfolio.total_pages} hasNext={Boolean(portfolio.next)} hasPrevious={Boolean(portfolio.previous)} onChange={(page) => update("page", page)} /></>}
    </section>

    <section className="agenda-card"><header><div><p className="section-kicker">Agenda de seguimiento</p><h3>Contactos pendientes</h3></div><span>{agendaCount} requieren atención</span></header><div className="agenda-columns">{(["overdue", "today", "upcoming"] as const).map((group) => <article key={group}><h4>{group === "overdue" ? "Atrasados" : group === "today" ? "Para hoy" : "Próximos 7 días"}</h4>{agenda?.[group].length ? agenda[group].slice(0, 5).map((item) => <button key={item.id} onClick={() => void openDetail(item.contract)}><strong>{item.customer_name}</strong><span>{item.contract_number}</span><small><CalendarCheck size={12} /> {formatDate(item.next_follow_up_date)}</small></button>) : <p>Sin seguimientos</p>}</article>)}</div></section>

    <Modal open={Boolean(actionTarget)} onClose={() => setActionTarget(null)} title="Registrar gestión de cobranza" description={actionTarget ? `${actionTarget.customer_name} · ${actionTarget.contract_number}` : ""}>
      <form className="collection-form" onSubmit={(event) => void saveAction(event)}><div className="payment-context"><div><small>Saldo</small><strong>{formatCurrency(actionTarget?.balance)}</strong></div><div><small>Vencido</small><strong>{formatCurrency(actionTarget?.overdue_amount)}</strong></div><div><small>Mora</small><strong>{actionTarget?.days_overdue ?? 0} días</strong></div><div><small>Teléfono</small><strong>{actionTarget?.phone || "No registrado"}</strong></div></div><div className="payment-fields"><label><span>Tipo de contacto</span><select name="action_type" required>{options?.action_types.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Resultado</span><select name="outcome" required defaultValue="contacted">{options?.outcomes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Próximo seguimiento</span><input name="next_follow_up_date" type="date" min={today} /></label><label><span>Fecha de promesa (si aplica)</span><input name="promised_date" type="date" min={today} /></label><label><span>Monto prometido (si aplica)</span><input name="promised_amount" type="number" min="0.01" step="0.01" /></label><label className="field-wide"><span>Notas de la gestión</span><textarea name="notes" rows={4} required maxLength={2000} placeholder="Documenta qué se conversó y el siguiente paso acordado." /></label></div><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setActionTarget(null)}>Cancelar</button><button className="primary-action" disabled={submitting}>{submitting ? "Guardando…" : "Guardar gestión"}</button></div></form>
    </Modal>

    <Modal open={Boolean(detail)} onClose={() => setDetail(null)} title="Detalle de cartera" description={detail ? `${detail.portfolio.customer_name} · ${detail.portfolio.contract_number}` : ""}>
      {detail && <div className="collection-detail"><section className="detail-balance"><div><small>Saldo pendiente</small><strong>{formatCurrency(detail.portfolio.balance)}</strong></div><div><small>Vencido</small><strong>{formatCurrency(detail.portfolio.overdue_amount)}</strong></div><div><small>Por vencer</small><strong>{formatCurrency(detail.portfolio.upcoming_amount)}</strong></div><div><small>Prioridad</small><span className={`priority-badge priority-badge--${detail.portfolio.priority}`}>{detail.portfolio.priority_label}</span></div></section><div className="collection-detail-actions"><a className="secondary-button" href={`tel:${detail.portfolio.phone}`}><Phone size={15} /> Llamar</a><Link className="secondary-button" to={`/contratos/${detail.portfolio.contract_id}`}>Ver contrato</Link>{user?.permisos.pagos.create_payment && Number(detail.portfolio.balance) > 0 && <Link className="primary-action" to={`/contratos/${detail.portfolio.contract_id}?tab=payments&payment=new`}><WalletCards size={15} /> Registrar pago</Link>}{options?.permissions.create_action && <button className="primary-action" onClick={() => { setActionTarget(detail.portfolio); setDetail(null); }}>Nueva gestión</button>}</div><section className="collection-timeline"><h3>Historial de cobranza</h3>{detail.actions.length ? detail.actions.map((item) => <article key={item.id}><span><History size={15} /></span><div><strong>{item.action_type_label} · {item.outcome_label}</strong><p>{item.notes}</p><small>{formatDateTime(item.contact_date)} · {item.created_by_name}</small>{item.next_follow_up_date && <em>Seguimiento: {formatDate(item.next_follow_up_date)}</em>}</div></article>) : <p className="empty-copy">Aún no se han registrado gestiones.</p>}</section></div>}
    </Modal>
  </div>;
}
