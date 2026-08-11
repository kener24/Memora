import {
  Banknote, CalendarCheck, Check, CheckCircle2, ChevronRight, Clock3, MapPin, Phone, Play,
  ReceiptText, RefreshCw, Route as RouteIcon, Square, UserRoundCheck, WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  closeSession, getCurrentSession, getOwnMetrics, getOwnPortfolio, getOwnRoutes, getTodayAgenda,
  listSettlements, previewSettlement, recordRouteVisit, startSession, submitSettlement,
} from "../services/collectionOperationsService";
import type { PaginatedPortfolio, PortfolioRow } from "../types/collection";
import type {
  CollectionRoute, CollectorMetrics, Paginated, Settlement, SettlementPreview, WorkSession,
} from "../types/collectionOperations";
import { formatCurrency, formatDate, formatDateTime } from "../utils/format";

type Tab = "today" | "portfolio" | "routes" | "session";
const emptyTotals = { contracts: 0, customers: 0, pending: "0", overdue: "0", upcoming: "0", overdue_installments: 0 };
const emptyPortfolio: PaginatedPortfolio = { count: 0, page: 1, page_size: 100, total_pages: 1, next: null, previous: null, results: [], totals: emptyTotals };
const emptySettlements: Paginated<Settlement> = { count: 0, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results: [] };

export function CollectorWorkspacePage() {
  useDocumentTitle("Mi jornada de cobro");
  const { user } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("today");
  const [metrics, setMetrics] = useState<CollectorMetrics | null>(null);
  const [today, setToday] = useState<PaginatedPortfolio>(emptyPortfolio);
  const [portfolio, setPortfolio] = useState<PaginatedPortfolio>(emptyPortfolio);
  const [routes, setRoutes] = useState<CollectionRoute[]>([]);
  const [session, setSession] = useState<WorkSession | null>(null);
  const [settlements, setSettlements] = useState<Paginated<Settlement>>(emptySettlements);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [preview, setPreview] = useState<SettlementPreview | null>(null);
  const [reportedCash, setReportedCash] = useState("");
  const [settlementNotes, setSettlementNotes] = useState("");
  const permissions = user?.permisos.cobranza;
  const settledToday = settlements.results.some((item) => new Date(item.submitted_at).toDateString() === new Date().toDateString());

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [metricData, todayData, portfolioData, routeData, sessionData, settlementData] = await Promise.all([
        getOwnMetrics(), getTodayAgenda(), getOwnPortfolio({ page_size: 100 }), getOwnRoutes(new Date().getDay() === 0 ? 6 : new Date().getDay() - 1),
        getCurrentSession(), listSettlements({ page_size: 20 }),
      ]);
      setMetrics(metricData); setToday(todayData); setPortfolio(portfolioData); setRoutes(routeData);
      setSession(sessionData); setSettlements(settlementData);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible preparar tu jornada."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const filteredPortfolio = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es");
    if (!term) return portfolio.results;
    return portfolio.results.filter((row) => `${row.customer_name} ${row.contract_number} ${row.phone}`.toLocaleLowerCase("es").includes(term));
  }, [portfolio.results, search]);

  async function run(action: () => Promise<unknown>, message: string) {
    setWorking(true);
    try { await action(); showToast(message); await load(); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible completar la operación.", "error"); }
    finally { setWorking(false); }
  }

  async function openSettlementPreview() {
    setWorking(true);
    try { const data = await previewSettlement(); setPreview(data); setReportedCash(data.expected_cash); setSettlementNotes(""); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible calcular la liquidación.", "error"); }
    finally { setWorking(false); }
  }

  async function sendSettlement() {
    if (!preview) return;
    setWorking(true);
    try {
      await submitSettlement({ work_session: preview.work_session, reported_cash: reportedCash, notes: settlementNotes, payment_fingerprint: preview.payment_fingerprint }, crypto.randomUUID());
      showToast("Liquidación presentada correctamente."); setPreview(null); await load();
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible presentar la liquidación.", "error"); }
    finally { setWorking(false); }
  }

  if (!permissions?.view_own_portfolio) return <div className="permission-state"><UserRoundCheck size={34} /><h2>Espacio exclusivo de cobradores</h2><p>Tu rol actual no tiene una cartera individual asignada.</p></div>;

  return <div className="collector-workspace">
    <header className="collector-hero">
      <div><p className="section-kicker">Trabajo de campo</p><h2>Hola, {user?.nombre || "cobrador"}</h2><p>{session ? `Jornada iniciada ${formatDateTime(session.started_at)}` : "Inicia tu jornada antes de registrar pagos."}</p></div>
      <div className={`session-pill ${session ? "session-pill--open" : ""}`}><span /><strong>{session ? "Jornada abierta" : "Jornada cerrada"}</strong></div>
    </header>
    {error && <div className="error-banner">{error}<button onClick={() => void load()}>Reintentar</button></div>}
    {loading ? <div className="table-loading">Preparando tu agenda…</div> : <>
      <section className="collector-quick-stats">
        <article><span><Banknote size={19} /></span><small>Cobrado hoy</small><strong>{formatCurrency(metrics?.collected_today)}</strong><em>{metrics?.payments_today || 0} pagos</em></article>
        <article><span><WalletCards size={19} /></span><small>Cartera asignada</small><strong>{formatCurrency(metrics?.pending_portfolio)}</strong><em>{metrics?.assigned_contracts || 0} contratos</em></article>
        <article><span><CalendarCheck size={19} /></span><small>Vence / mora hoy</small><strong>{formatCurrency(metrics?.due_today)}</strong><em>{metrics?.overdue_installments || 0} cuotas vencidas</em></article>
        <article><span><CheckCircle2 size={19} /></span><small>Atendidos</small><strong>{metrics?.customers_attended_today || 0}</strong><em>{metrics?.actions_today || 0} gestiones</em></article>
      </section>
      <nav className="collector-mobile-tabs">
        <button className={tab === "today" ? "active" : ""} onClick={() => setTab("today")}><CalendarCheck size={17} />Hoy</button>
        <button className={tab === "portfolio" ? "active" : ""} onClick={() => setTab("portfolio")}><WalletCards size={17} />Cartera</button>
        <button className={tab === "routes" ? "active" : ""} onClick={() => setTab("routes")}><RouteIcon size={17} />Ruta</button>
        <button className={tab === "session" ? "active" : ""} onClick={() => setTab("session")}><Clock3 size={17} />Jornada</button>
      </nav>

      {tab === "today" && <section className="collector-panel"><header><div><h3>Clientes para hoy</h3><p>Vencimientos, mora, seguimientos y promesas comprometidas.</p></div><button className="icon-button" onClick={() => void load()}><RefreshCw size={17} /></button></header>{today.results.length ? <div className="collector-customer-list">{today.results.map((row) => <CustomerCard key={row.contract_id} row={row} sessionOpen={Boolean(session)} />)}</div> : <div className="empty-state"><CalendarCheck size={30} /><h3>Agenda al día</h3><p>No hay cobros, promesas o seguimientos pendientes para hoy.</p></div>}</section>}

      {tab === "portfolio" && <section className="collector-panel"><header><div><h3>Mi cartera</h3><p>Solo contratos con una asignación activa a tu usuario.</p></div></header><label className="collector-search"><SearchIcon /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar cliente, contrato o teléfono" /></label><div className="collector-customer-list">{filteredPortfolio.map((row) => <CustomerCard key={row.contract_id} row={row} sessionOpen={Boolean(session)} />)}</div></section>}

      {tab === "routes" && <section className="collector-panel"><header><div><h3>Mi ruta de hoy</h3><p>Marca el resultado en cada parada. “No encontrado” genera una gestión trazable.</p></div></header>{routes.length ? routes.map((route) => <article className="mobile-route" key={route.id}><header><span><RouteIcon size={18} /></span><div><strong>{route.name}</strong><small>{route.zone_name || "Sin zona"} · {route.stops.length} paradas</small></div></header><div>{route.stops.map((stop) => <section className={`mobile-stop ${stop.today_visit ? "mobile-stop--done" : ""}`} key={stop.id}><span>{stop.position}</span><div><strong>{stop.customer_name}</strong><small><MapPin size={12} /> {stop.customer_address || "Dirección no registrada"}</small>{stop.customer_phone && <a href={`tel:${stop.customer_phone}`}><Phone size={13} /> {stop.customer_phone}</a>}</div><div className="visit-actions">{stop.today_visit ? <em>{stop.today_visit.status_label}</em> : <><button disabled={working} onClick={() => void run(() => recordRouteVisit(stop.id, "visited"), "Visita registrada.")}><Check size={14} /> Visitado</button><button disabled={working} onClick={() => void run(() => recordRouteVisit(stop.id, "not_found", "Cliente no encontrado durante la ruta."), "Visita y gestión registradas.")}>No encontrado</button><button disabled={working} onClick={() => void run(() => recordRouteVisit(stop.id, "postponed", "Visita pospuesta."), "Visita pospuesta.")}>Posponer</button></>}</div></section>)}</div></article>) : <div className="empty-state"><RouteIcon size={30} /><h3>Sin ruta para hoy</h3><p>Tu cartera sigue disponible aunque no tengas un recorrido asignado.</p></div>}</section>}

      {tab === "session" && <section className="collector-panel session-panel"><header><div><h3>Jornada y liquidación</h3><p>Todos tus pagos de campo quedan vinculados a la jornada abierta.</p></div></header>{session ? <div className="active-session-card"><span><Clock3 size={23} /></span><div><small>Jornada en curso</small><strong>Inició {formatDateTime(session.started_at)}</strong><p>{formatCurrency(session.summary?.total_collected)} confirmados · {session.summary?.payment_count || 0} pagos</p></div><button className="danger-outline-button" disabled={working} onClick={() => void run(() => closeSession(session.id, "Cierre desde espacio del cobrador."), "Jornada cerrada. Ya puedes liquidar.")}><Square size={14} /> Finalizar jornada</button></div> : <div className="start-session-card"><span><Play size={25} /></span><h3>Inicia antes del primer cobro</h3><p>Esto separa los pagos de cada día y permite calcular el efectivo esperado.</p><button className="primary-action" disabled={working} onClick={() => void run(() => startSession("Jornada iniciada desde dispositivo de campo."), "Jornada iniciada.")}><Play size={16} /> Iniciar jornada</button></div>}
        {!session && !settledToday && <button className="settlement-launch" disabled={working} onClick={() => void openSettlementPreview()}><span><ReceiptText size={21} /></span><div><strong>Preparar liquidación pendiente</strong><small>Revisa pagos, efectivo esperado y diferencia antes de enviar.</small></div><ChevronRight size={18} /></button>}
        <div className="settlement-history"><h4>Mis liquidaciones</h4>{settlements.results.map((item) => <article key={item.id}><div><strong>{item.settlement_number}</strong><small>{formatDateTime(item.submitted_at)}</small></div><div><strong>{formatCurrency(item.total_collected)}</strong><small>Diferencia {formatCurrency(item.difference)}</small></div><span className={`operation-status operation-status--${item.status}`}>{item.status_label}</span></article>)}</div>
      </section>}
    </>}

    <Modal open={Boolean(preview)} onClose={() => setPreview(null)} title="Presentar liquidación" description="El detalle queda congelado al enviar">
      {preview && <div className="collector-settlement-form"><div className="settlement-kpis"><div><small>Total cobrado</small><strong>{formatCurrency(preview.total_collected)}</strong></div><div><small>Efectivo esperado</small><strong>{formatCurrency(preview.expected_cash)}</strong></div><div><small>Transferencias</small><strong>{formatCurrency(preview.transfer_total)}</strong></div><div><small>Otros medios</small><strong>{formatCurrency(Number(preview.card_total) + Number(preview.check_total) + Number(preview.other_total))}</strong></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Pago / recibo</th><th>Cliente</th><th>Método</th><th>Monto</th></tr></thead><tbody>{preview.payments.map((payment) => <tr key={payment.id}><td><strong>{payment.payment_number}</strong><small>{payment.receipt_number}</small></td><td>{payment.customer}<small>{payment.contract}</small></td><td>{payment.method_label}</td><td>{formatCurrency(payment.amount)}</td></tr>)}</tbody></table></div><div className="payment-fields"><label><span>Efectivo que entregas *</span><input inputMode="decimal" value={reportedCash} onChange={(e) => setReportedCash(e.target.value)} /></label><label className="field-wide"><span>Notas {Number(reportedCash) !== Number(preview.expected_cash) ? "(obligatorias por diferencia)" : ""}</span><textarea rows={3} value={settlementNotes} onChange={(e) => setSettlementNotes(e.target.value)} /></label></div><div className={`difference-preview ${Number(reportedCash) !== Number(preview.expected_cash) ? "difference-preview--alert" : ""}`}><span>Diferencia reportada - esperada</span><strong>{formatCurrency(Number(reportedCash || 0) - Number(preview.expected_cash))}</strong></div><button className="primary-action settlement-submit" disabled={working || !reportedCash || (Number(reportedCash) !== Number(preview.expected_cash) && settlementNotes.trim().length < 5)} onClick={() => void sendSettlement()}>Presentar liquidación</button></div>}
    </Modal>
  </div>;
}

function SearchIcon() { return <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>; }

function CustomerCard({ row, sessionOpen }: { row: PortfolioRow; sessionOpen: boolean }) {
  return <article className="collector-customer-card"><header><div><strong>{row.customer_name}</strong><small>{row.contract_number} · {row.plan.name}</small></div><span className={`priority-badge priority-badge--${row.priority}`}>{row.priority_label}</span></header><div className="customer-collection-facts"><span><small>Saldo</small><strong>{formatCurrency(row.balance)}</strong></span><span><small>Vencido</small><strong>{formatCurrency(row.overdue_amount)}</strong></span><span><small>Mora</small><strong>{row.days_overdue} días</strong></span><span><small>Próxima</small><strong>{formatDate(row.next_due_date)}</strong></span></div><footer>{row.phone && <a className="secondary-button" href={`tel:${row.phone}`}><Phone size={15} /> Llamar</a>}<Link className="secondary-button" to="/cartera">Gestión</Link><Link className={`primary-action ${!sessionOpen ? "is-disabled" : ""}`} aria-disabled={!sessionOpen} onClick={(e) => { if (!sessionOpen) e.preventDefault(); }} to={`/contratos/${row.contract_id}?tab=payments&payment=new`}><WalletCards size={15} /> Cobrar</Link></footer>{!sessionOpen && <p className="session-required-note">Inicia tu jornada para registrar el pago.</p>}</article>;
}
