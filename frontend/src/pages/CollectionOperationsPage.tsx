import {
  ArrowDown, ArrowUp, Check, Download, FileSpreadsheet, MapPinned, Plus, RefreshCw,
  Route as RouteIcon, Search, ShieldCheck, UserRoundCog, UsersRound, WalletCards, X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { listPortfolio } from "../services/collectionService";
import {
  addRouteStop, bulkAssign, createRoute, createZone, decideSettlement, downloadOperations,
  getCollectorPortfolio, getOperationsOptions, listAssignments, listCollectors, listRoutes,
  listSettlements, listZones, reassign, removeRouteStop, reorderRoute, updateCollector,
  updateRoute, updateZone,
} from "../services/collectionOperationsService";
import { listCustomers } from "../services/customerService";
import type { PaginatedPortfolio } from "../types/collection";
import type { CustomerListItem } from "../types/customer";
import type {
  Assignment, CollectionRoute, Collector, OperationsOptions, Paginated, Settlement, Zone,
} from "../types/collectionOperations";
import { formatCurrency, formatDate, formatDateTime } from "../utils/format";

type Tab = "collectors" | "assignments" | "zones" | "routes" | "settlements";
const emptyPage = <T,>(): Paginated<T> => ({ count: 0, page: 1, page_size: 20, total_pages: 1, next: null, previous: null, results: [] });
const emptyPortfolio: PaginatedPortfolio = { ...emptyPage(), totals: { contracts: 0, customers: 0, pending: "0", overdue: "0", upcoming: "0", overdue_installments: 0 } };

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

export function CollectionOperationsPage() {
  useDocumentTitle("Operación de cobranza");
  const { user } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("collectors");
  const [options, setOptions] = useState<OperationsOptions | null>(null);
  const [collectors, setCollectors] = useState<Paginated<Collector>>(emptyPage());
  const [assignments, setAssignments] = useState<Paginated<Assignment>>(emptyPage());
  const [zones, setZones] = useState<Paginated<Zone>>(emptyPage());
  const [routes, setRoutes] = useState<Paginated<CollectionRoute>>(emptyPage());
  const [settlements, setSettlements] = useState<Paginated<Settlement>>(emptyPage());
  const [unassigned, setUnassigned] = useState<PaginatedPortfolio>(emptyPortfolio);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [selectedContracts, setSelectedContracts] = useState<number[]>([]);
  const [assignCollector, setAssignCollector] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [reassignTarget, setReassignTarget] = useState<Assignment | null>(null);
  const [collectorPortfolio, setCollectorPortfolio] = useState<{ collector: Collector; data: PaginatedPortfolio } | null>(null);
  const [zoneForm, setZoneForm] = useState({ branch: "", code: "", name: "", description: "" });
  const [routeForm, setRouteForm] = useState({ branch: "", zone: "", collector: "", day_of_week: "", name: "", description: "" });
  const [routeTarget, setRouteTarget] = useState<CollectionRoute | null>(null);
  const [stopCustomer, setStopCustomer] = useState("");
  const [settlementTarget, setSettlementTarget] = useState<Settlement | null>(null);
  const permissions = user?.permisos.cobranza;

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [opts, people, assignmentData, zoneData, routeData, settlementData, available, customerData] = await Promise.all([
        getOperationsOptions(), listCollectors({ page_size: 100 }),
        permissions?.assign_portfolio ? listAssignments({ page_size: 100 }) : Promise.resolve(emptyPage<Assignment>()),
        permissions?.manage_zones ? listZones({ page_size: 100 }) : Promise.resolve(emptyPage<Zone>()),
        permissions?.manage_routes ? listRoutes({ page_size: 100 }) : Promise.resolve(emptyPage<CollectionRoute>()),
        permissions?.view_settlement ? listSettlements({ page_size: 100 }) : Promise.resolve(emptyPage<Settlement>()),
        permissions?.assign_portfolio ? listPortfolio({ assignment: "unassigned", status: "pending", page_size: 100 }) : Promise.resolve(emptyPortfolio),
        permissions?.manage_routes ? listCustomers({ is_active: "true", page_size: 100 }) : Promise.resolve({ results: [] as CustomerListItem[] }),
      ]);
      setOptions(opts); setCollectors(people); setAssignments(assignmentData); setZones(zoneData);
      setRoutes(routeData); setSettlements(settlementData); setUnassigned(available); setCustomers(customerData.results);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible cargar la operación de cobranza.");
    } finally { setLoading(false); }
  }, [permissions?.assign_portfolio, permissions?.manage_routes, permissions?.manage_zones, permissions?.view_settlement]);

  useEffect(() => { void load(); }, [load]);
  const activeAssignments = useMemo(() => assignments.results.filter((item) => item.status === "active"), [assignments]);

  async function run(action: () => Promise<unknown>, message: string) {
    setWorking(true);
    try { await action(); showToast(message); await load(); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible completar la operación.", "error"); }
    finally { setWorking(false); }
  }

  async function openPortfolio(collector: Collector) {
    setWorking(true);
    try { setCollectorPortfolio({ collector, data: await getCollectorPortfolio(collector.id, { page_size: 100 }) }); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cargar la cartera.", "error"); }
    finally { setWorking(false); }
  }

  async function exportBlob(path: string, filename: string) {
    setWorking(true);
    try { saveBlob(await downloadOperations(path), filename); showToast("Archivo generado correctamente."); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible generar el archivo.", "error"); }
    finally { setWorking(false); }
  }

  if (!permissions?.view_collector_metrics) return <div className="permission-state"><ShieldCheck size={34} /><h2>Acceso restringido</h2><p>No tienes permisos para administrar la operación de cobradores.</p></div>;

  return <div className="operations-page">
    <header className="module-heading operations-heading">
      <div><p className="section-kicker">Control de campo y cierre diario</p><h2>Operación de cobranza</h2><p>Asigna cartera, organiza recorridos y controla liquidaciones sin duplicar pagos ni saldos.</p></div>
      <button className="secondary-button" disabled={loading} onClick={() => void load()}><RefreshCw size={16} /> Actualizar</button>
    </header>
    <nav className="module-tabs operations-tabs" aria-label="Secciones de operación">
      {([
        ["collectors", "Cobradores", <UsersRound size={16} />], ["assignments", "Asignación", <UserRoundCog size={16} />],
        ["zones", "Zonas", <MapPinned size={16} />], ["routes", "Rutas", <RouteIcon size={16} />],
        ["settlements", "Liquidaciones", <WalletCards size={16} />],
      ] as Array<[Tab, string, ReactElement]>).filter(([value]) => value === "collectors" ||
        (value === "assignments" && permissions.assign_portfolio) ||
        (value === "zones" && permissions.manage_zones) ||
        (value === "routes" && permissions.manage_routes) ||
        (value === "settlements" && permissions.view_settlement)
      ).map(([value, label, icon]) => <button key={value} className={`module-tab ${tab === value ? "module-tab--active" : ""}`} onClick={() => setTab(value)}>{icon}{label}</button>)}
    </nav>
    {error && <div className="error-banner">{error}<button onClick={() => void load()}>Reintentar</button></div>}
    {loading ? <div className="table-loading">Preparando operación de cobranza…</div> : <>
      {tab === "collectors" && <section className="operations-section">
        <header><div><h3>Cobradores activos</h3><p>Productividad calculada desde asignaciones, cuotas y pagos confirmados.</p></div>{permissions.export_collections && <button className="secondary-button" disabled={working} onClick={() => void exportBlob("collectors/productivity/export.xlsx", "Productividad_Cobradores.xlsx")}><FileSpreadsheet size={16} /> Exportar productividad</button>}</header>
        <div className="collector-grid">{collectors.results.map((collector) => <article className={`collector-card ${!collector.is_available ? "collector-card--off" : ""}`} key={collector.id}>
          <header><span>{collector.name.charAt(0)}</span><div><strong>{collector.name}</strong><small>{collector.employee_code || "Código pendiente"} · {collector.branch_name || "Sin sucursal"}</small></div><button className={`availability-switch ${collector.is_available ? "availability-switch--on" : ""}`} disabled={!permissions.manage_collectors || working} onClick={() => void run(() => updateCollector(collector.id, { is_available: !collector.is_available }), "Disponibilidad actualizada.")} aria-label="Cambiar disponibilidad"><i /></button></header>
          <div className="collector-kpis"><div><small>Cartera</small><strong>{formatCurrency(collector.metrics.pending_portfolio)}</strong></div><div><small>Vencida</small><strong>{formatCurrency(collector.metrics.overdue_portfolio)}</strong></div><div><small>Cobrado hoy</small><strong>{formatCurrency(collector.metrics.collected_today)}</strong></div><div><small>Gestiones</small><strong>{collector.metrics.actions_today}</strong></div></div>
          <footer><span>{collector.metrics.assigned_contracts} contratos · {collector.metrics.pending_promises} promesas</span><button onClick={() => void openPortfolio(collector)}>Ver cartera</button></footer>
        </article>)}</div>
      </section>}

      {tab === "assignments" && <section className="operations-section">
        <header><div><h3>Asignación de cartera</h3><p>La operación masiva es atómica: si un contrato dejó de estar disponible, no se asigna ninguno.</p></div></header>
        <div className="assignment-layout">
          <div className="assignment-picker"><div className="assignment-toolbar"><label><span>Cobrador destino</span><select value={assignCollector} onChange={(e) => setAssignCollector(e.target.value)}><option value="">Seleccionar…</option>{options?.collectors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Motivo / nota</span><input value={assignReason} onChange={(e) => setAssignReason(e.target.value)} placeholder="Asignación semanal" /></label><button className="primary-action" disabled={working || !assignCollector || !selectedContracts.length} onClick={() => void run(async () => { await bulkAssign({ contracts: selectedContracts, collector: Number(assignCollector), reason: assignReason }); setSelectedContracts([]); }, "Cartera asignada correctamente.")}><Check size={16} /> Asignar {selectedContracts.length || ""}</button></div>
            <div className="table-scroll"><table className="data-table"><thead><tr><th><input type="checkbox" checked={Boolean(unassigned.results.length) && selectedContracts.length === unassigned.results.length} onChange={(e) => setSelectedContracts(e.target.checked ? unassigned.results.map((item) => item.contract_id) : [])} /></th><th>Cliente / contrato</th><th>Saldo</th><th>Vencido</th><th>Prioridad</th></tr></thead><tbody>{unassigned.results.map((row) => <tr key={row.contract_id}><td><input type="checkbox" checked={selectedContracts.includes(row.contract_id)} onChange={(e) => setSelectedContracts((current) => e.target.checked ? [...current, row.contract_id] : current.filter((id) => id !== row.contract_id))} /></td><td><strong>{row.customer_name}</strong><small>{row.contract_number}</small></td><td>{formatCurrency(row.balance)}</td><td>{formatCurrency(row.overdue_amount)}</td><td><span className={`priority-badge priority-badge--${row.priority}`}>{row.priority_label}</span></td></tr>)}</tbody></table></div>
          </div>
          <aside className="assignment-summary"><small>Sin asignar</small><strong>{unassigned.count}</strong><span>{formatCurrency(unassigned.totals.pending)} en cartera</span><small>Asignaciones activas</small><strong>{activeAssignments.length}</strong></aside>
        </div>
        <h3 className="subsection-title">Historial de asignaciones</h3><div className="table-scroll"><table className="data-table"><thead><tr><th>Contrato / cliente</th><th>Cobrador</th><th>Vigencia</th><th>Estado</th><th>Motivo</th><th /></tr></thead><tbody>{assignments.results.map((item) => <tr key={item.id}><td><strong>{item.contract_number}</strong><small>{item.customer_name}</small></td><td>{item.collector_name}</td><td>{formatDate(item.effective_from)}<small>{item.effective_until ? `hasta ${formatDate(item.effective_until)}` : "vigente"}</small></td><td><span className={`operation-status operation-status--${item.status}`}>{item.status_label}</span></td><td>{item.reason || "Sin nota"}</td><td>{item.status === "active" && permissions.reassign_portfolio && <button className="table-icon-action" title="Reasignar" onClick={() => setReassignTarget(item)}><UserRoundCog size={15} /></button>}</td></tr>)}</tbody></table></div>
      </section>}

      {tab === "zones" && <section className="operations-section two-panel-operation">
        <div><header><div><h3>Zonas de cobranza</h3><p>Agrupaciones operativas por sucursal.</p></div></header><div className="operation-list">{zones.results.map((zone) => <article key={zone.id}><span className="zone-mark"><MapPinned size={18} /></span><div><strong>{zone.code} · {zone.name}</strong><small>{zone.branch_name} · {zone.customer_count} clientes</small><p>{zone.description || "Sin descripción"}</p></div><button className={zone.is_active ? "danger-text" : "secondary-button"} disabled={working} onClick={() => void run(() => updateZone(zone.id, { is_active: !zone.is_active }), `Zona ${zone.is_active ? "inactivada" : "reactivada"}.`)}>{zone.is_active ? "Inactivar" : "Reactivar"}</button></article>)}</div></div>
        <form className="operation-form" onSubmit={(e) => { e.preventDefault(); void run(async () => { await createZone({ branch: Number(zoneForm.branch), code: zoneForm.code, name: zoneForm.name, description: zoneForm.description }); setZoneForm({ branch: "", code: "", name: "", description: "" }); }, "Zona creada."); }}><p className="section-kicker">Nueva zona</p><h3>Definir agrupación</h3><label><span>Sucursal *</span><select required value={zoneForm.branch} onChange={(e) => setZoneForm({ ...zoneForm, branch: e.target.value })}><option value="">Seleccionar…</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Código *</span><input required value={zoneForm.code} onChange={(e) => setZoneForm({ ...zoneForm, code: e.target.value })} placeholder="NORTE" /></label><label><span>Nombre *</span><input required value={zoneForm.name} onChange={(e) => setZoneForm({ ...zoneForm, name: e.target.value })} /></label><label><span>Descripción</span><textarea rows={4} value={zoneForm.description} onChange={(e) => setZoneForm({ ...zoneForm, description: e.target.value })} /></label><button className="primary-action" disabled={working}><Plus size={16} /> Crear zona</button></form>
      </section>}

      {tab === "routes" && <section className="operations-section two-panel-operation">
        <div><header><div><h3>Rutas y paradas</h3><p>Recorridos ordenados sin depender de GPS ni proveedores externos.</p></div></header><div className="operation-list">{routes.results.map((route) => <article className="route-list-item" key={route.id}><span className="zone-mark"><RouteIcon size={18} /></span><div><strong>{route.name}</strong><small>{route.branch_name} · {route.collector_name || "Sin cobrador"} · {route.day_of_week_label || "Cualquier día"}</small><p>{route.stops.length} paradas · {route.zone_name || "Sin zona"}</p></div><button onClick={() => { setRouteTarget(route); setStopCustomer(""); }}>Administrar</button></article>)}</div></div>
        <form className="operation-form" onSubmit={(e) => { e.preventDefault(); void run(async () => { await createRoute({ branch: Number(routeForm.branch), zone: routeForm.zone ? Number(routeForm.zone) : null, collector: routeForm.collector ? Number(routeForm.collector) : null, day_of_week: routeForm.day_of_week === "" ? null : Number(routeForm.day_of_week), name: routeForm.name, description: routeForm.description }); setRouteForm({ branch: "", zone: "", collector: "", day_of_week: "", name: "", description: "" }); }, "Ruta creada."); }}><p className="section-kicker">Nueva ruta</p><h3>Planificar recorrido</h3><label><span>Sucursal *</span><select required value={routeForm.branch} onChange={(e) => setRouteForm({ ...routeForm, branch: e.target.value, zone: "", collector: "" })}><option value="">Seleccionar…</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Nombre *</span><input required value={routeForm.name} onChange={(e) => setRouteForm({ ...routeForm, name: e.target.value })} /></label><label><span>Cobrador</span><select value={routeForm.collector} onChange={(e) => setRouteForm({ ...routeForm, collector: e.target.value })}><option value="">Sin asignar</option>{options?.collectors.filter((item) => !routeForm.branch || item.branch === Number(routeForm.branch)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Zona</span><select value={routeForm.zone} onChange={(e) => setRouteForm({ ...routeForm, zone: e.target.value })}><option value="">Sin zona</option>{options?.zones.filter((item) => !routeForm.branch || item.branch === Number(routeForm.branch)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Día</span><select value={routeForm.day_of_week} onChange={(e) => setRouteForm({ ...routeForm, day_of_week: e.target.value })}><option value="">Cualquier día</option>{options?.days.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><button className="primary-action" disabled={working}><Plus size={16} /> Crear ruta</button></form>
      </section>}

      {tab === "settlements" && <section className="operations-section">
        <header><div><h3>Liquidaciones diarias</h3><p>El efectivo esperado proviene exclusivamente de pagos en efectivo confirmados durante la jornada.</p></div>{permissions.export_collections && <button className="secondary-button" onClick={() => void exportBlob("collector-settlements/export.xlsx", "Liquidaciones_Cobradores.xlsx")}><FileSpreadsheet size={16} /> Excel</button>}</header>
        <div className="table-scroll"><table className="data-table settlement-table"><thead><tr><th>Liquidación</th><th>Cobrador</th><th>Total</th><th>Efectivo</th><th>Diferencia</th><th>Estado</th><th /></tr></thead><tbody>{settlements.results.map((item) => <tr key={item.id}><td><strong>{item.settlement_number}</strong><small>{formatDateTime(item.submitted_at)}</small></td><td>{item.collector_name}<small>{item.branch_name}</small></td><td>{formatCurrency(item.total_collected)}</td><td>{formatCurrency(item.reported_cash)}<small>esperado {formatCurrency(item.expected_cash)}</small></td><td className={Number(item.difference) ? "settlement-difference" : ""}>{formatCurrency(item.difference)}</td><td><span className={`operation-status operation-status--${item.status}`}>{item.status_label}</span></td><td><button className="table-icon-action" title="Ver" onClick={() => setSettlementTarget(item)}><Search size={15} /></button></td></tr>)}</tbody></table></div>
      </section>}
    </>}

    <Modal open={Boolean(collectorPortfolio)} onClose={() => setCollectorPortfolio(null)} title={collectorPortfolio?.collector.name || "Cartera"} description="Cartera individual derivada de la asignación activa">
      {collectorPortfolio && <><div className="modal-summary-row"><div><small>Contratos</small><strong>{collectorPortfolio.data.totals.contracts}</strong></div><div><small>Pendiente</small><strong>{formatCurrency(collectorPortfolio.data.totals.pending)}</strong></div><div><small>Vencido</small><strong>{formatCurrency(collectorPortfolio.data.totals.overdue)}</strong></div><button className="secondary-button" onClick={() => void exportBlob(`collectors/${collectorPortfolio.collector.id}/portfolio/export.xlsx`, `Cartera_${collectorPortfolio.collector.employee_code || collectorPortfolio.collector.id}.xlsx`)}><Download size={15} /> Excel</button></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Cliente / contrato</th><th>Saldo</th><th>Vencido</th><th>Mora</th></tr></thead><tbody>{collectorPortfolio.data.results.map((row) => <tr key={row.contract_id}><td><strong>{row.customer_name}</strong><small>{row.contract_number}</small></td><td>{formatCurrency(row.balance)}</td><td>{formatCurrency(row.overdue_amount)}</td><td>{row.days_overdue} días</td></tr>)}</tbody></table></div></>}
    </Modal>

    <Modal open={Boolean(reassignTarget)} onClose={() => setReassignTarget(null)} title="Reasignar cartera" description={reassignTarget ? `${reassignTarget.contract_number} · ${reassignTarget.customer_name}` : ""} size="small">
      {reassignTarget && <form className="operation-form modal-operation-form" onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); void run(() => reassign(reassignTarget.id, { collector: Number(data.get("collector")), reason: String(data.get("reason")) }), "Cartera reasignada.").then(() => setReassignTarget(null)); }}><label><span>Nuevo cobrador *</span><select name="collector" required defaultValue=""><option value="">Seleccionar…</option>{options?.collectors.filter((item) => item.id !== reassignTarget.collector).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Motivo obligatorio *</span><textarea name="reason" minLength={5} required rows={4} placeholder="Explica por qué se reasigna" /></label><button className="primary-action" disabled={working}>Confirmar reasignación</button></form>}
    </Modal>

    <Modal open={Boolean(routeTarget)} onClose={() => setRouteTarget(null)} title={routeTarget?.name || "Ruta"} description="Ordena o retira paradas sin perder su historial">
      {routeTarget && <><div className="route-admin-toolbar"><select value={stopCustomer} onChange={(e) => setStopCustomer(e.target.value)}><option value="">Seleccionar cliente…</option>{customers.filter((item) => !routeTarget.stops.some((stop) => stop.customer === item.id)).map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.customer_code}</option>)}</select><button className="primary-action" disabled={!stopCustomer || working} onClick={() => void run(() => addRouteStop(routeTarget.id, { customer: Number(stopCustomer) }), "Parada agregada.").then(() => setRouteTarget(null))}><Plus size={15} /> Agregar parada</button><button className={routeTarget.is_active ? "danger-outline-button" : "secondary-button"} onClick={() => void run(() => updateRoute(routeTarget.id, { is_active: !routeTarget.is_active }), "Estado de ruta actualizado.").then(() => setRouteTarget(null))}>{routeTarget.is_active ? "Inactivar ruta" : "Reactivar ruta"}</button></div><div className="route-stop-admin">{routeTarget.stops.map((stop, index) => <article key={stop.id}><span>{index + 1}</span><div><strong>{stop.customer_name}</strong><small>{stop.customer_phone || "Sin teléfono"} · {stop.customer_address || "Sin dirección"}</small></div><div><button disabled={index === 0 || working} onClick={() => { const ids = routeTarget.stops.map((item) => item.id); [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]]; void run(() => reorderRoute(routeTarget.id, ids), "Ruta reordenada.").then(() => setRouteTarget(null)); }}><ArrowUp size={14} /></button><button disabled={index === routeTarget.stops.length - 1 || working} onClick={() => { const ids = routeTarget.stops.map((item) => item.id); [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]]; void run(() => reorderRoute(routeTarget.id, ids), "Ruta reordenada.").then(() => setRouteTarget(null)); }}><ArrowDown size={14} /></button><button className="danger-text" onClick={() => void run(() => removeRouteStop(routeTarget.id, stop.id), "Parada retirada.").then(() => setRouteTarget(null))}><X size={14} /></button></div></article>)}</div></>}
    </Modal>

    <Modal open={Boolean(settlementTarget)} onClose={() => setSettlementTarget(null)} title={settlementTarget?.settlement_number || "Liquidación"} description={settlementTarget ? `${settlementTarget.collector_name} · ${settlementTarget.status_label}` : ""}>
      {settlementTarget && <div className="settlement-detail"><div className="settlement-kpis"><div><small>Total</small><strong>{formatCurrency(settlementTarget.total_collected)}</strong></div><div><small>Efectivo esperado</small><strong>{formatCurrency(settlementTarget.expected_cash)}</strong></div><div><small>Reportado</small><strong>{formatCurrency(settlementTarget.reported_cash)}</strong></div><div className={Number(settlementTarget.difference) ? "is-difference" : ""}><small>Diferencia</small><strong>{formatCurrency(settlementTarget.difference)}</strong></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Pago / recibo</th><th>Cliente / contrato</th><th>Método</th><th>Monto</th></tr></thead><tbody>{settlementTarget.payments.map((payment) => <tr key={payment.id}><td><strong>{payment.payment_number_snapshot}</strong><small>{payment.receipt_number_snapshot}</small></td><td>{payment.customer_name_snapshot}<small>{payment.contract_number_snapshot}</small></td><td>{payment.payment_method_label}</td><td>{formatCurrency(payment.amount_snapshot)}</td></tr>)}</tbody></table></div><div className="settlement-actions"><button className="secondary-button" onClick={() => void exportBlob(`collector-settlements/${settlementTarget.id}/pdf/`, `Liquidacion_${settlementTarget.settlement_number}.pdf`)}>Imprimir PDF</button>{permissions.review_settlement && settlementTarget.status === "submitted" && <button className="secondary-button" onClick={() => void run(() => decideSettlement(settlementTarget.id, "review", "Revisión administrativa realizada."), "Liquidación revisada.").then(() => setSettlementTarget(null))}>Marcar revisada</button>}{permissions.accept_settlement && ["submitted", "reviewed"].includes(settlementTarget.status) && <button className="primary-action" onClick={() => void run(() => decideSettlement(settlementTarget.id, "accept", Number(settlementTarget.difference) ? "Diferencia revisada y aceptada." : ""), "Liquidación aceptada.").then(() => setSettlementTarget(null))}>Aceptar</button>}{permissions.reject_settlement && ["submitted", "reviewed"].includes(settlementTarget.status) && <button className="danger-outline-button" onClick={() => { const reason = window.prompt("Motivo del rechazo (mínimo 5 caracteres)"); if (reason) void run(() => decideSettlement(settlementTarget.id, "reject", reason), "Liquidación rechazada.").then(() => setSettlementTarget(null)); }}>Rechazar</button>}</div></div>}
    </Modal>
  </div>;
}
