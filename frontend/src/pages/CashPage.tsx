import {
  AlertTriangle, ArrowDownLeft, ArrowUpRight, Banknote, Calculator, CheckCircle2,
  Clock3, Download, FileSpreadsheet, History, Landmark, LockKeyhole, Plus,
  ReceiptText, RefreshCw, Scale, Settings2, ShieldCheck, WalletCards, XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  closeCashSession, createCashMovement, createCashRegister, downloadCashClosingPdf,
  downloadCashMovementsExcel, getCashDashboard, getCashSession, getCurrentCashSession,
  getCashOptions, listCashMovements, listCashRegisters, listCashSessions,
  listPendingSettlements, listSettlementReceptions, openCashSession, performCashCount,
  receiveSettlement, updateCashRegister, voidCashMovement,
} from "../services/cashService";
import type {
  CashDashboard, CashMovement, CashOptions, CashRegister, CashSession, MovementTotals,
  Paginated, PendingSettlement, SettlementReception,
} from "../types/cash";
import { formatCurrency, formatDate, formatDateTime } from "../utils/format";

type Tab = "current" | "movements" | "settlements" | "history" | "registers";
const emptyTotals: MovementTotals = { total_in: "0", total_out: "0", net: "0", cash_in: "0", cash_out: "0", cash_net: "0" };
const emptyPage = <T, U = Record<string, never>>(totals = {} as U): Paginated<T, U> => ({
  count: 0, page: 1, page_size: 25, total_pages: 1, next: null, previous: null, results: [], totals,
});
const incomeCategories = new Set(["extraordinary_income", "temporary_contribution", "other_income"]);
const expenseCategories = new Set(["operating_expense", "minor_purchase", "authorized_refund", "other_expense"]);

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

export function CashPage() {
  useDocumentTitle("Caja");
  const { user } = useAuth();
  const { showToast } = useToast();
  const permissions = user?.permisos.caja;
  const [tab, setTab] = useState<Tab>("current");
  const [options, setOptions] = useState<CashOptions | null>(null);
  const [dashboard, setDashboard] = useState<CashDashboard | null>(null);
  const [current, setCurrent] = useState<CashSession | null>(null);
  const [registers, setRegisters] = useState<Paginated<CashRegister>>(emptyPage());
  const [sessions, setSessions] = useState<Paginated<CashSession>>(emptyPage());
  const [movements, setMovements] = useState<Paginated<CashMovement, MovementTotals>>(emptyPage(emptyTotals));
  const [pending, setPending] = useState<Paginated<PendingSettlement>>(emptyPage());
  const [receptions, setReceptions] = useState<Paginated<SettlementReception>>(emptyPage());
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ direction: "", payment_method: "", status: "", date_from: "", date_to: "" });
  const [openForm, setOpenForm] = useState({ cash_register: "", opening_cash: "", notes: "" });
  const [movementOpen, setMovementOpen] = useState(false);
  const [movementForm, setMovementForm] = useState({ direction: "in", category: "extraordinary_income", amount: "", payment_method: "cash", description: "", reference: "" });
  const [receptionTarget, setReceptionTarget] = useState<PendingSettlement | null>(null);
  const [receivedCash, setReceivedCash] = useState("");
  const [receptionNotes, setReceptionNotes] = useState("");
  const [countOpen, setCountOpen] = useState(false);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [manualCount, setManualCount] = useState("");
  const [differenceReason, setDifferenceReason] = useState("");
  const [closeOpen, setCloseOpen] = useState(false);
  const [closeNotes, setCloseNotes] = useState("");
  const [historyTarget, setHistoryTarget] = useState<CashSession | null>(null);
  const [historyMovements, setHistoryMovements] = useState<CashMovement[]>([]);
  const [registerForm, setRegisterForm] = useState({ branch: "", name: "", description: "" });

  const load = useCallback(async () => {
    if (!permissions?.view_session) return;
    setLoading(true); setError("");
    try {
      const [opts, dash, active, registerData, movementData, sessionData, receptionData, pendingData] = await Promise.all([
        getCashOptions(), getCashDashboard(), getCurrentCashSession(),
        listCashRegisters({ page_size: 100 }), listCashMovements({ ...filters, page_size: 100 }),
        listCashSessions({ page_size: 100 }), listSettlementReceptions({ page_size: 100 }),
        permissions.receive_collector_settlement ? listPendingSettlements() : Promise.resolve(emptyPage<PendingSettlement>()),
      ]);
      setOptions(opts); setDashboard(dash); setCurrent(active); setRegisters(registerData);
      setMovements(movementData); setSessions(sessionData); setReceptions(receptionData); setPending(pendingData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible cargar el módulo de caja.");
    } finally { setLoading(false); }
  }, [filters, permissions?.receive_collector_settlement, permissions?.view_session]);

  useEffect(() => { void load(); }, [load]);

  const denominationTotal = useMemo(() => options?.denominations.reduce(
    (total, denomination) => total + Number(denomination) * Number(quantities[denomination] || 0), 0,
  ) || 0, [options?.denominations, quantities]);
  const countedTotal = denominationTotal || Number(manualCount || 0);
  const countDifference = countedTotal - Number(current?.summary.expected_cash || 0);
  const deliveryDifference = Number(receivedCash || 0) - Number(receptionTarget?.reported_cash || 0);
  const totalReceptionDifference = Number(receivedCash || 0) - Number(receptionTarget?.expected_cash || 0);

  async function run(action: () => Promise<unknown>, message: string): Promise<boolean> {
    setWorking(true);
    try { await action(); showToast(message); await load(); return true; }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible completar la operación.", "error"); return false; }
    finally { setWorking(false); }
  }

  async function openHistory(item: CashSession) {
    setWorking(true);
    try {
      const [detail, movementData] = await Promise.all([
        getCashSession(item.id), listCashMovements({ session: item.id, page_size: 100 }),
      ]);
      setHistoryTarget(detail); setHistoryMovements(movementData.results);
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cargar el cierre.", "error"); }
    finally { setWorking(false); }
  }

  async function downloadPdf(item: CashSession) {
    setWorking(true);
    try { saveBlob(await downloadCashClosingPdf(item.id), `Cierre_Caja_${item.session_number}.pdf`); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible generar el PDF.", "error"); }
    finally { setWorking(false); }
  }

  if (!permissions?.view_session) return <div className="permission-state"><ShieldCheck size={34} /><h2>Acceso restringido</h2><p>Tu rol no opera ni consulta la caja general.</p></div>;

  const tabs: Array<[Tab, string, ReactElement]> = [
    ["current", "Caja actual", <Landmark size={16} />],
    ["movements", "Movimientos", <ReceiptText size={16} />],
    ...(permissions.receive_collector_settlement ? [["settlements", "Liquidaciones", <WalletCards size={16} />] as [Tab, string, ReactElement]] : []),
    ...(permissions.view_cash_history ? [["history", "Historial", <History size={16} />] as [Tab, string, ReactElement]] : []),
    ...(permissions.manage_cash_register ? [["registers", "Configuración", <Settings2 size={16} />] as [Tab, string, ReactElement]] : []),
  ];

  return <div className="cash-page">
    <header className="module-heading cash-heading">
      <div><p className="section-kicker">Control monetario por sesión</p><h2>Caja</h2><p>Concilia efectivo real sin alterar pagos, contratos ni cartera.</p></div>
      <button className="secondary-button" disabled={loading} onClick={() => void load()}><RefreshCw size={16} /> Actualizar</button>
    </header>
    {dashboard && <section className="cash-global-kpis">
      <article><span><WalletCards size={18} /></span><small>Cobrado hoy</small><strong>{formatCurrency(dashboard.payment_total_today)}</strong><p>Todos los métodos</p></article>
      <article><span><Banknote size={18} /></span><small>Efectivo recibido</small><strong>{formatCurrency(dashboard.cash_received_today)}</strong><p>Movimientos físicos</p></article>
      <article><span><Clock3 size={18} /></span><small>Pendiente de entregar</small><strong>{formatCurrency(dashboard.pending_settlement_cash)}</strong><p>{dashboard.pending_settlements} liquidaciones</p></article>
      <article className={Number(dashboard.cash_differences_today) ? "is-alert" : ""}><span><Scale size={18} /></span><small>Diferencias del día</small><strong>{formatCurrency(dashboard.cash_differences_today)}</strong><p>{dashboard.open_sessions} cajas abiertas</p></article>
    </section>}
    <nav className="module-tabs cash-tabs" aria-label="Secciones de caja">
      {tabs.map(([value, label, icon]) => <button key={value} className={`module-tab ${tab === value ? "module-tab--active" : ""}`} onClick={() => setTab(value)}>{icon}{label}</button>)}
    </nav>
    {error && <div className="error-banner">{error}<button onClick={() => void load()}>Reintentar</button></div>}
    {loading ? <div className="table-loading">Conciliando la información de caja…</div> : <>
      {tab === "current" && <section className="cash-current-section">
        {current ? <>
          <div className="cash-session-banner"><div><span className="cash-live-dot" /><p>Caja abierta</p><h3>{current.cash_register_name}</h3><small>{current.cash_register_code} · {current.session_number} · desde {formatDateTime(current.opened_at)}</small></div><div><small>Cajero</small><strong>{current.cashier_name}</strong><small>{current.branch_name}</small></div></div>
          <div className="cash-session-kpis">
            <article><small>Fondo inicial</small><strong>{formatCurrency(current.summary.opening_cash)}</strong></article>
            <article className="cash-in"><small>Entradas efectivo</small><strong>{formatCurrency(current.summary.cash_in)}</strong></article>
            <article className="cash-out"><small>Salidas efectivo</small><strong>{formatCurrency(current.summary.cash_out)}</strong></article>
            <article className="cash-expected"><small>Efectivo esperado</small><strong>{formatCurrency(current.summary.expected_cash)}</strong></article>
          </div>
          <div className="cash-current-grid">
            <article className="cash-method-card"><header><div><p className="section-kicker">Resumen financiero</p><h3>Otros métodos</h3></div><span>No afectan billetes</span></header><div><span><small>Transferencias</small><strong>{formatCurrency(current.summary.method_totals.transfer)}</strong></span><span><small>Tarjetas</small><strong>{formatCurrency(current.summary.method_totals.card)}</strong></span><span><small>Cheques</small><strong>{formatCurrency(current.summary.method_totals.check)}</strong></span><span><small>Otros</small><strong>{formatCurrency(current.summary.method_totals.other)}</strong></span></div></article>
            <article className="cash-action-card"><p className="section-kicker">Operar sesión</p><h3>Acciones disponibles</h3><div>{permissions.create_income && <button onClick={() => { setMovementForm({ direction: "in", category: "extraordinary_income", amount: "", payment_method: "cash", description: "", reference: "" }); setMovementOpen(true); }}><ArrowDownLeft size={17} /> Registrar ingreso</button>}{permissions.create_expense && <button onClick={() => { setMovementForm({ direction: "out", category: "operating_expense", amount: "", payment_method: "cash", description: "", reference: "" }); setMovementOpen(true); }}><ArrowUpRight size={17} /> Registrar egreso</button>}{permissions.receive_collector_settlement && <button onClick={() => setTab("settlements")}><WalletCards size={17} /> Recibir liquidación</button>}{permissions.perform_cash_count && <button onClick={() => { setQuantities({}); setManualCount(""); setDifferenceReason(""); setCountOpen(true); }}><Calculator size={17} /> Realizar arqueo</button>}</div>{current.latest_count && <div className={`latest-count ${Number(current.latest_count.difference) ? "has-difference" : ""}`}><span>Último arqueo · {formatDateTime(current.latest_count.counted_at)}</span><strong>{formatCurrency(current.latest_count.counted_cash)}</strong><small>Diferencia {formatCurrency(current.latest_count.difference)}</small></div>}{permissions.close_session && <button className="primary-action cash-close-action" disabled={!current.latest_count || working} onClick={() => setCloseOpen(true)}><LockKeyhole size={16} /> Cerrar caja</button>}</article>
          </div>
        </> : <div className="cash-empty-open"><span><Landmark size={30} /></span><h3>No hay una caja abierta</h3><p>Selecciona una caja disponible y declara el fondo inicial para comenzar.</p>{permissions.open_session && <form onSubmit={(event) => { event.preventDefault(); void run(async () => { await openCashSession({ cash_register: Number(openForm.cash_register), opening_cash: openForm.opening_cash, notes: openForm.notes }, crypto.randomUUID()); setOpenForm({ cash_register: "", opening_cash: "", notes: "" }); }, "Caja abierta correctamente."); }}><label><span>Caja *</span><select required value={openForm.cash_register} onChange={(e) => setOpenForm({ ...openForm, cash_register: e.target.value })}><option value="">Seleccionar…</option>{registers.results.filter((item) => item.is_active && !item.open_session).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} · {item.branch_name}</option>)}</select></label><label><span>Fondo inicial *</span><input required inputMode="decimal" value={openForm.opening_cash} onChange={(e) => setOpenForm({ ...openForm, opening_cash: e.target.value })} placeholder="0.00" /></label><label className="field-wide"><span>Notas</span><textarea rows={3} value={openForm.notes} onChange={(e) => setOpenForm({ ...openForm, notes: e.target.value })} /></label><button className="primary-action" disabled={working}><Landmark size={16} /> Confirmar apertura</button></form>}</div>}
      </section>}

      {tab === "movements" && <section className="operations-section cash-movements-section">
        <header><div><h3>Movimientos de caja</h3><p>El total filtrado proviene del backend y no solamente de la página visible.</p></div>{permissions.export_cash && <button className="secondary-button" disabled={working} onClick={() => void (async () => { setWorking(true); try { saveBlob(await downloadCashMovementsExcel(filters), "Movimientos_Caja.xlsx"); } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible exportar.", "error"); } finally { setWorking(false); } })()}><FileSpreadsheet size={16} /> Excel</button>}</header>
        <div className="cash-filter-row"><select value={filters.direction} onChange={(e) => setFilters({ ...filters, direction: e.target.value })}><option value="">Entradas y salidas</option><option value="in">Entradas</option><option value="out">Salidas</option></select><select value={filters.payment_method} onChange={(e) => setFilters({ ...filters, payment_method: e.target.value })}><option value="">Todos los métodos</option>{options?.payment_methods.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">Todos los estados</option>{options?.movement_statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} aria-label="Fecha desde" /><input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} aria-label="Fecha hasta" /></div>
        <div className="cash-filter-totals"><span><small>Entradas</small><strong>{formatCurrency(movements.totals.total_in)}</strong></span><span><small>Salidas</small><strong>{formatCurrency(movements.totals.total_out)}</strong></span><span><small>Neto</small><strong>{formatCurrency(movements.totals.net)}</strong></span><span><small>Neto efectivo</small><strong>{formatCurrency(movements.totals.cash_net)}</strong></span></div>
        {movements.results.length ? <div className="table-scroll"><table className="data-table cash-movement-table"><thead><tr><th>Hora / movimiento</th><th>Tipo / descripción</th><th>Caja</th><th>Método</th><th>Entrada</th><th>Salida</th><th>Estado</th><th /></tr></thead><tbody>{movements.results.map((item) => <tr key={item.id}><td><strong>{formatDateTime(item.created_at)}</strong><small>{item.movement_number}</small></td><td><strong>{item.movement_type_label}</strong><small>{item.description}</small><em>{item.source.label}</em></td><td>{item.cash_register_name}<small>{item.session_number}</small></td><td>{item.payment_method_label}{!item.affects_cash && <small>No físico</small>}</td><td className="cash-positive">{item.direction === "in" ? formatCurrency(item.amount) : "—"}</td><td className="cash-negative">{item.direction === "out" ? formatCurrency(item.amount) : "—"}</td><td><span className={`operation-status operation-status--${item.status}`}>{item.status_label}</span></td><td>{permissions.void_movement && item.session_status === "open" && item.status === "confirmed" && item.source.type === "manual" && <button className="table-icon-action" title="Anular" onClick={() => { const reason = window.prompt("Motivo de anulación (mínimo 5 caracteres)"); if (reason) void run(() => voidCashMovement(item.id, reason), "Movimiento anulado."); }}><XCircle size={15} /></button>}</td></tr>)}</tbody></table></div> : <div className="cash-inline-empty"><ReceiptText size={25} /><p>No existen movimientos con estos filtros.</p></div>}
      </section>}

      {tab === "settlements" && <section className="operations-section cash-settlement-section"><header><div><h3>Liquidaciones pendientes de recibir</h3><p>La caja registra el efectivo contado por el cajero, no el monto esperado.</p></div><span className="pending-cash-chip">{pending.count} pendientes · {formatCurrency(pending.results.reduce((sum, item) => sum + Number(item.reported_cash), 0))}</span></header>{pending.results.length ? <div className="cash-settlement-grid">{pending.results.map((item) => <article key={item.id}><header><span>{item.collector_name.charAt(0)}</span><div><strong>{item.collector_name}</strong><small>{item.settlement_number} · {formatDate(item.work_date)}</small></div></header><div><span><small>Esperado</small><strong>{formatCurrency(item.expected_cash)}</strong></span><span><small>Reportado</small><strong>{formatCurrency(item.reported_cash)}</strong></span><span className={Number(item.difference) ? "has-difference" : ""}><small>Diferencia cobrador</small><strong>{formatCurrency(item.difference)}</strong></span><span><small>Total cobrado</small><strong>{formatCurrency(item.total_collected)}</strong></span></div><footer><small>{item.branch_name}</small><button className="primary-action" disabled={!current} onClick={() => { setReceptionTarget(item); setReceivedCash(item.reported_cash); setReceptionNotes(""); }}>Recibir en caja</button></footer>{!current && <p className="session-required-note">Abre una caja para recibir esta liquidación.</p>}</article>)}</div> : <div className="cash-inline-empty"><CheckCircle2 size={28} /><h3>No hay liquidaciones pendientes</h3><p>Las liquidaciones aceptadas aparecerán aquí hasta que Caja las reciba.</p></div>}{receptions.results.length > 0 && <><h3 className="subsection-title">Recepciones recientes</h3><div className="table-scroll"><table className="data-table"><thead><tr><th>Recepción</th><th>Cobrador</th><th>Recibido</th><th>Dif. entrega</th><th>Dif. total</th><th>Fecha</th></tr></thead><tbody>{receptions.results.slice(0, 10).map((item) => <tr key={item.id}><td><strong>{item.reception_number}</strong><small>{item.settlement_number}</small></td><td>{item.collector_name}</td><td>{formatCurrency(item.cash_received_by_cashier)}</td><td>{formatCurrency(item.delivery_difference)}</td><td>{formatCurrency(item.total_difference_vs_expected)}</td><td>{formatDateTime(item.received_at)}</td></tr>)}</tbody></table></div></>}</section>}

      {tab === "history" && <section className="operations-section"><header><div><h3>Historial de cajas</h3><p>Los cierres conservan sus totales y arqueos como snapshots inmutables.</p></div></header>{sessions.results.length ? <div className="table-scroll"><table className="data-table cash-history-table"><thead><tr><th>Sesión</th><th>Caja / cajero</th><th>Apertura / cierre</th><th>Fondo</th><th>Entradas</th><th>Salidas</th><th>Esperado</th><th>Contado</th><th>Diferencia</th><th /></tr></thead><tbody>{sessions.results.map((item) => <tr key={item.id}><td><strong>{item.session_number}</strong><small><span className={`operation-status operation-status--${item.status}`}>{item.status_label}</span></small></td><td>{item.cash_register_name}<small>{item.cashier_name}</small></td><td>{formatDateTime(item.opened_at)}<small>{formatDateTime(item.closed_at)}</small></td><td>{formatCurrency(item.opening_cash)}</td><td>{formatCurrency(item.summary.cash_in)}</td><td>{formatCurrency(item.summary.cash_out)}</td><td>{formatCurrency(item.summary.expected_cash)}</td><td>{formatCurrency(item.summary.counted_cash)}</td><td className={Number(item.summary.difference) ? "settlement-difference" : ""}>{formatCurrency(item.summary.difference)}</td><td><button className="table-icon-action" onClick={() => void openHistory(item)} title="Ver detalle"><History size={15} /></button></td></tr>)}</tbody></table></div> : <div className="cash-inline-empty"><History size={25} /><p>No existen cierres anteriores.</p></div>}</section>}

      {tab === "registers" && <section className="cash-register-layout"><div className="operations-section"><header><div><h3>Configuración de cajas</h3><p>Las cajas se inactivan; el historial nunca se elimina.</p></div></header><div className="cash-register-list">{registers.results.map((item) => <article key={item.id}><span><Landmark size={19} /></span><div><strong>{item.code} · {item.name}</strong><small>{item.branch_name}</small><p>{item.description || "Sin descripción"}</p>{item.open_session && <em>Abierta por {item.open_session.cashier}</em>}</div><button className={item.is_active ? "danger-outline-button" : "secondary-button"} disabled={working || Boolean(item.open_session)} onClick={() => void run(() => updateCashRegister(item.id, { is_active: !item.is_active }), `Caja ${item.is_active ? "inactivada" : "activada"}.`)}>{item.is_active ? "Inactivar" : "Activar"}</button></article>)}</div></div><form className="operation-form cash-register-form" onSubmit={(event) => { event.preventDefault(); void run(async () => { await createCashRegister({ branch: Number(registerForm.branch), name: registerForm.name, description: registerForm.description }); setRegisterForm({ branch: "", name: "", description: "" }); }, "Caja creada."); }}><p className="section-kicker">Nueva caja</p><h3>Crear punto de control</h3><label><span>Sucursal *</span><select required value={registerForm.branch} onChange={(e) => setRegisterForm({ ...registerForm, branch: e.target.value })}><option value="">Seleccionar…</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Nombre *</span><input required value={registerForm.name} onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })} placeholder="Caja Principal" /></label><label><span>Descripción</span><textarea rows={4} value={registerForm.description} onChange={(e) => setRegisterForm({ ...registerForm, description: e.target.value })} /></label><button className="primary-action" disabled={working}><Plus size={16} /> Crear caja</button></form></section>}
    </>}

    <Modal open={movementOpen} onClose={() => setMovementOpen(false)} title={movementForm.direction === "in" ? "Registrar ingreso" : "Registrar egreso"} description={movementForm.direction === "in" ? "Este movimiento no representa un pago de cliente." : "Este registro no sustituye el futuro módulo de Gastos."} size="small"><form className="operation-form modal-operation-form" onSubmit={(event) => { event.preventDefault(); if (!current) return; void run(() => createCashMovement({ cash_session: current.id, ...movementForm }, crypto.randomUUID()), movementForm.direction === "in" ? "Ingreso registrado." : "Egreso registrado.").then(() => setMovementOpen(false)); }}><div className="cash-manual-warning"><AlertTriangle size={16} /><span>{movementForm.direction === "in" ? "Los pagos de clientes deben registrarse desde Pagos." : `Disponible esperado: ${formatCurrency(current?.summary.expected_cash)}`}</span></div><label><span>Categoría *</span><select required value={movementForm.category} onChange={(e) => setMovementForm({ ...movementForm, category: e.target.value })}>{options?.categories.filter((item) => (movementForm.direction === "in" ? incomeCategories : expenseCategories).has(item.value)).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Monto *</span><input required inputMode="decimal" value={movementForm.amount} onChange={(e) => setMovementForm({ ...movementForm, amount: e.target.value })} /></label><label><span>Método *</span><select value={movementForm.payment_method} onChange={(e) => setMovementForm({ ...movementForm, payment_method: e.target.value })}>{options?.payment_methods.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Referencia</span><input value={movementForm.reference} onChange={(e) => setMovementForm({ ...movementForm, reference: e.target.value })} /></label><label><span>Descripción obligatoria *</span><textarea required minLength={5} rows={4} value={movementForm.description} onChange={(e) => setMovementForm({ ...movementForm, description: e.target.value })} /></label><button className="primary-action" disabled={working}>{movementForm.direction === "in" ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />} Confirmar movimiento</button></form></Modal>

    <Modal open={Boolean(receptionTarget)} onClose={() => setReceptionTarget(null)} title="Recibir liquidación" description={receptionTarget ? `${receptionTarget.collector_name} · ${receptionTarget.settlement_number}` : ""} size="small">{receptionTarget && <div className="cash-reception-form"><div className="reception-comparison"><span><small>Efectivo esperado</small><strong>{formatCurrency(receptionTarget.expected_cash)}</strong></span><span><small>Reportado por cobrador</small><strong>{formatCurrency(receptionTarget.reported_cash)}</strong></span><span className={Number(receptionTarget.difference) ? "has-difference" : ""}><small>Diferencia cobrador</small><strong>{formatCurrency(receptionTarget.difference)}</strong></span></div><label><span>Dinero contado por cajero *</span><input autoFocus inputMode="decimal" value={receivedCash} onChange={(e) => setReceivedCash(e.target.value)} /></label><div className="reception-differences"><span><small>Diferencia vs reportado</small><strong>{formatCurrency(deliveryDifference)}</strong></span><span><small>Total vs esperado</small><strong>{formatCurrency(totalReceptionDifference)}</strong></span></div><label><span>Observación {deliveryDifference ? "*" : ""}</span><textarea rows={4} minLength={deliveryDifference ? 5 : undefined} required={Boolean(deliveryDifference)} value={receptionNotes} onChange={(e) => setReceptionNotes(e.target.value)} /></label><button className="primary-action" disabled={working || !receivedCash || (Boolean(deliveryDifference) && receptionNotes.trim().length < 5)} onClick={() => { if (!current) return; void run(() => receiveSettlement({ cash_session: current.id, collector_settlement: receptionTarget.id, cash_received_by_cashier: receivedCash, notes: receptionNotes }, crypto.randomUUID()), "Liquidación recibida en caja.").then(() => setReceptionTarget(null)); }}><CheckCircle2 size={16} /> Confirmar recepción</button></div>}</Modal>

    <Modal open={countOpen} onClose={() => setCountOpen(false)} title="Arqueo físico" description="El backend calculará nuevamente el total de las denominaciones."><div className="cash-count-form"><div className="denomination-grid">{options?.denominations.map((denomination) => <label key={denomination}><span>{formatCurrency(denomination)} ×</span><input inputMode="numeric" min="0" type="number" value={quantities[denomination] || ""} onChange={(e) => setQuantities({ ...quantities, [denomination]: e.target.value })} /></label>)}</div><div className="manual-count-divider"><span>o introduce el total contado</span></div><label className="manual-count-field"><span>Total manual</span><input inputMode="decimal" disabled={Boolean(denominationTotal)} value={manualCount} onChange={(e) => setManualCount(e.target.value)} placeholder="0.00" /></label><div className="count-summary"><span><small>Total contado</small><strong>{formatCurrency(countedTotal)}</strong></span><span><small>Efectivo esperado</small><strong>{formatCurrency(current?.summary.expected_cash)}</strong></span><span className={countDifference ? "has-difference" : ""}><small>Diferencia</small><strong>{formatCurrency(countDifference)}</strong></span></div><label><span>Motivo de diferencia {countDifference ? "*" : ""}</span><textarea rows={3} required={Boolean(countDifference)} minLength={countDifference ? 5 : undefined} value={differenceReason} onChange={(e) => setDifferenceReason(e.target.value)} /></label><button className="primary-action" disabled={working || (!denominationTotal && !manualCount) || (Boolean(countDifference) && differenceReason.trim().length < 5)} onClick={() => { if (!current) return; const rows = Object.entries(quantities).filter(([, value]) => Number(value) > 0).map(([denomination, quantity]) => ({ denomination, quantity: Number(quantity) })); void run(() => performCashCount(current.id, { ...(rows.length ? { denominations: rows } : { counted_cash: manualCount }), difference_reason: differenceReason }, crypto.randomUUID()), "Arqueo registrado.").then(() => setCountOpen(false)); }}><Calculator size={16} /> Guardar arqueo</button></div></Modal>

    <Modal open={closeOpen} onClose={() => setCloseOpen(false)} title="Confirmar cierre de caja" description="Una vez cerrada no se podrán registrar nuevos movimientos en esta sesión." size="small">{current?.latest_count && <div className="cash-close-confirm"><div className="close-confirm-summary"><span><small>Fondo inicial</small><strong>{formatCurrency(current.summary.opening_cash)}</strong></span><span><small>Entradas efectivo</small><strong>{formatCurrency(current.summary.cash_in)}</strong></span><span><small>Salidas efectivo</small><strong>{formatCurrency(current.summary.cash_out)}</strong></span><span><small>Esperado</small><strong>{formatCurrency(current.summary.expected_cash)}</strong></span><span><small>Contado</small><strong>{formatCurrency(current.latest_count.counted_cash)}</strong></span><span className={Number(current.latest_count.difference) ? "has-difference" : ""}><small>Diferencia</small><strong>{formatCurrency(current.latest_count.difference)}</strong></span></div>{Number(current.latest_count.difference) !== 0 && <div className="cash-manual-warning"><AlertTriangle size={17} /><span>La caja presenta una diferencia de {formatCurrency(current.latest_count.difference)}. Quedará visible en el cierre.</span></div>}<label><span>Observaciones de cierre</span><textarea rows={3} value={closeNotes} onChange={(e) => setCloseNotes(e.target.value)} /></label><button className="primary-action" disabled={working} onClick={() => void run(() => closeCashSession(current.id, { cash_count: current.latest_count!.id, notes: closeNotes }, crypto.randomUUID()), "Caja cerrada correctamente.").then(() => { setCloseOpen(false); setTab("history"); })}><LockKeyhole size={16} /> Confirmar cierre definitivo</button></div>}</Modal>

    <Modal open={Boolean(historyTarget)} onClose={() => setHistoryTarget(null)} title={historyTarget?.session_number || "Cierre de caja"} description={historyTarget ? `${historyTarget.cash_register_name} · ${historyTarget.cashier_name}` : ""}>{historyTarget && <div className="cash-history-detail"><div className="close-confirm-summary"><span><small>Fondo inicial</small><strong>{formatCurrency(historyTarget.summary.opening_cash)}</strong></span><span><small>Entradas</small><strong>{formatCurrency(historyTarget.summary.cash_in)}</strong></span><span><small>Salidas</small><strong>{formatCurrency(historyTarget.summary.cash_out)}</strong></span><span><small>Esperado</small><strong>{formatCurrency(historyTarget.summary.expected_cash)}</strong></span><span><small>Contado</small><strong>{formatCurrency(historyTarget.summary.counted_cash)}</strong></span><span className={Number(historyTarget.summary.difference) ? "has-difference" : ""}><small>Diferencia</small><strong>{formatCurrency(historyTarget.summary.difference)}</strong></span></div><div className="history-detail-meta"><span>Abierta {formatDateTime(historyTarget.opened_at)}</span><span>Cerrada {formatDateTime(historyTarget.closed_at)}</span><button className="secondary-button" disabled={working || historyTarget.status !== "closed"} onClick={() => void downloadPdf(historyTarget)}><Download size={15} /> PDF de cierre</button></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Movimiento</th><th>Descripción</th><th>Entrada</th><th>Salida</th><th>Estado</th></tr></thead><tbody>{historyMovements.map((item) => <tr key={item.id}><td><strong>{item.movement_number}</strong><small>{formatDateTime(item.created_at)}</small></td><td>{item.description}<small>{item.payment_method_label}</small></td><td>{item.direction === "in" ? formatCurrency(item.amount) : "—"}</td><td>{item.direction === "out" ? formatCurrency(item.amount) : "—"}</td><td>{item.status_label}</td></tr>)}</tbody></table></div></div>}</Modal>
  </div>;
}
