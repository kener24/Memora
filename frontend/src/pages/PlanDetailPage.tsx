import { Activity, ArrowLeft, BadgeDollarSign, Building2, CheckCircle2, Clock3, Copy, Edit3, History, Layers3, MapPin, Power } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { changePlanStatus, duplicatePlan, getPlan } from "../services/planService";
import type { FuneralPlanDetail } from "../types/plan";
import { formatCurrency, formatDateTime } from "../utils/format";

export function PlanDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [plan, setPlan] = useState<FuneralPlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusOpen, setStatusOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [duplicateLoading, setDuplicateLoading] = useState(false);
  const permissions = user?.permisos.planes;
  useDocumentTitle(plan?.name ?? "Detalle del plan");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setPlan(await getPlan(Number(id))); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar el plan."); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  async function confirmStatus() {
    if (!plan) return; setActionLoading(true);
    try { await changePlanStatus(plan.id, !plan.is_active); showToast(plan.is_active ? "Plan inactivado." : "Plan reactivado."); setStatusOpen(false); await load(); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cambiar el estado.", "error"); }
    finally { setActionLoading(false); }
  }
  async function handleDuplicate() {
    if (!plan) return; setDuplicateLoading(true);
    try { const created = await duplicatePlan(plan.id); showToast("Plan duplicado correctamente."); navigate(`/planes/${created.id}`); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible duplicar el plan.", "error"); }
    finally { setDuplicateLoading(false); }
  }

  if (loading) return <div className="module-page"><div className="detail-skeleton detail-skeleton--hero" /><div className="summary-layout"><div className="detail-skeleton" /><div className="detail-skeleton" /></div></div>;
  if (error || !plan) return <div className="module-page detail-error"><Link to="/planes"><ArrowLeft size={16} /> Volver a planes</Link><h2>No pudimos abrir este plan</h2><p>{error}</p><button className="secondary-button" type="button" onClick={() => void load()}>Reintentar</button></div>;

  return <div className="module-page plan-detail-page">
    <Link className="back-link" to="/planes"><ArrowLeft size={16} /> Volver a planes</Link>
    <section className="plan-hero"><div className="plan-hero__mark"><Layers3 size={28} /></div><div className="plan-hero__copy"><div><span className="catalog-code">{plan.code}</span><span className={`status-dot status-dot--${plan.is_active ? "active" : "inactive"}`}>{plan.is_active ? "Activo" : "Inactivo"}</span></div><h2>{plan.name}</h2><p>{plan.description || "Sin descripción adicional."}</p><div className="plan-hero__facts"><span><BadgeDollarSign size={15} /> {formatCurrency(plan.base_price)}</span><span><Layers3 size={15} /> {plan.items_count} prestaciones</span><span><MapPin size={15} /> {plan.available_all_branches ? "Todas las sucursales" : `${plan.availability.branches.length} seleccionadas`}</span></div></div><div className="plan-hero__actions">{permissions?.edit && <Link className="secondary-button" to={`/planes/${plan.id}/editar`}><Edit3 size={16} /> Editar</Link>}{permissions?.duplicate && <button className="secondary-button" type="button" disabled={duplicateLoading} onClick={() => void handleDuplicate()}>{duplicateLoading ? <span className="button-spinner" /> : <Copy size={16} />} Duplicar</button>}{permissions?.change_status && <button className={plan.is_active ? "danger-button" : "primary-action"} type="button" onClick={() => setStatusOpen(true)}><Power size={16} /> {plan.is_active ? "Inactivar" : "Reactivar"}</button>}</div></section>

    <div className="plan-detail-grid"><section className="plan-detail-main"><article className="info-card plan-services-card"><header><span><Layers3 size={17} /></span><div><h3>Servicios incluidos</h3><p>Configuración comercial vigente del catálogo.</p></div></header><div className="included-services">{plan.items.map((item) => <div key={item.id}><span className="included-quantity">{Number(item.quantity).toLocaleString("es-HN", { maximumFractionDigits: 2 })} ×</span><div><strong>{item.service.name}</strong><small>{item.service.category_label} · {item.service.unit_label}{!item.service.is_active && " · Servicio inactivo"}</small>{item.notes && <p>{item.notes}</p>}</div>{permissions?.view_costs && <span className="included-cost">{formatCurrency(Number(item.service.estimated_cost ?? 0) * Number(item.quantity))}<small>estimado</small></span>}</div>)}</div></article>
      <article className="history-section"><header><div><p className="section-kicker">Trazabilidad</p><h3>Historial del plan</h3><p>Cambios administrativos relevantes.</p></div></header><ol className="activity-timeline">{plan.activities.map((activity) => <li key={activity.id}><span className="activity-timeline__dot"><Activity size={15} /></span><div><strong>{activity.action_label}</strong><p>{activity.description}</p>{activity.action === "price_changed" && activity.old_value !== null && <p className="price-change">{formatCurrency(activity.old_value)} → {formatCurrency(activity.new_value)}</p>}<small><Clock3 size={12} /> {formatDateTime(activity.created_at)} · {activity.user?.name ?? "Sistema"}</small></div></li>)}</ol>{plan.activities.length === 0 && <div className="compact-empty"><History size={24} /><p>No hay actividad registrada.</p></div>}</article>
    </section><aside className="plan-detail-aside"><article className="info-card"><header><span><BadgeDollarSign size={17} /></span><h3>Condiciones comerciales</h3></header><dl className="info-grid info-grid--single"><div><dt>Precio de venta</dt><dd>{formatCurrency(plan.base_price)}</dd></div><div><dt>Prima sugerida</dt><dd>{formatCurrency(plan.initial_payment)}</dd></div><div><dt>Financiamiento</dt><dd>{plan.allow_financing ? "Permitido" : "No permitido"}</dd></div></dl></article>
      {permissions?.view_costs && <article className="estimate-detail-card"><header><span><CheckCircle2 size={18} /></span><div><strong>Análisis estimado</strong><small>No representa utilidad contable real.</small></div></header><dl><div><dt>Precio de venta</dt><dd>{formatCurrency(plan.base_price)}</dd></div><div><dt>Costo estimado</dt><dd>{formatCurrency(plan.estimated_plan_cost)}</dd></div><div><dt>Margen estimado</dt><dd>{formatCurrency(plan.estimated_margin)}</dd></div><div><dt>Margen estimado %</dt><dd>{plan.estimated_margin_percent ? `${plan.estimated_margin_percent}%` : "—"}</dd></div></dl></article>}
      <article className="info-card"><header><span><Building2 size={17} /></span><h3>Disponibilidad</h3></header>{plan.available_all_branches ? <p className="availability-all"><CheckCircle2 size={16} /> Disponible en todas las sucursales.</p> : <ul className="availability-list">{plan.availability.branches.map((branch) => <li key={branch.id}><MapPin size={14} /><span><strong>{branch.name}</strong><small>{branch.code}</small></span></li>)}</ul>}</article>
    </aside></div>
    <ConfirmModal open={statusOpen} title={`${plan.is_active ? "Inactivar" : "Reactivar"} plan`} description={plan.is_active ? "El plan dejará de estar disponible para nuevas ventas. Su historial permanecerá conservado." : "El plan volverá a estar disponible en las sucursales configuradas."} confirmLabel={plan.is_active ? "Sí, inactivar" : "Sí, reactivar"} tone={plan.is_active ? "danger" : "primary"} loading={actionLoading} onConfirm={() => void confirmStatus()} onCancel={() => !actionLoading && setStatusOpen(false)} />
  </div>;
}
