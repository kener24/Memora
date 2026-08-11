import { AlertTriangle, Banknote, Building2, Clock3, HandCoins, Landmark, MapPin, ShieldCheck, Sparkles, TrendingUp, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { getPortfolioSummary } from "../services/collectionService";
import { getCashDashboard } from "../services/cashService";
import type { PortfolioSummary } from "../types/collection";
import type { CashDashboard } from "../types/cash";
import { formatCurrency } from "../utils/format";

export function DashboardPage() {
  useDocumentTitle("Inicio");
  const { user } = useAuth();
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [cashSummary, setCashSummary] = useState<CashDashboard | null>(null);
  const displayName = user?.nombre || user?.email || "usuario";

  useEffect(() => {
    if (user?.permisos.cobranza.view_portfolio) getPortfolioSummary().then(setSummary).catch(() => setSummary(null));
  }, [user?.permisos.cobranza.view_portfolio]);

  useEffect(() => {
    if (user?.permisos.caja.view_session) getCashDashboard().then(setCashSummary).catch(() => setCashSummary(null));
  }, [user?.permisos.caja.view_session]);

  return <div className="dashboard">
    <section className="welcome-card"><div className="welcome-card__content"><span className="welcome-card__kicker"><Sparkles size={15} /> Panorama operativo</span><h2>Bienvenido, {displayName}</h2><p>Consulta la operación real de Memora y atiende primero los compromisos que requieren seguimiento.</p></div><div className="welcome-card__monogram" aria-hidden="true">M</div></section>
    {summary && <section className="portfolio-kpis dashboard-kpis">
      <article><span><WalletCards size={19} /></span><small>Cartera pendiente</small><strong>{formatCurrency(summary.pending_portfolio)}</strong><p>Contratos activos</p></article>
      <article className="kpi-overdue"><span><AlertTriangle size={19} /></span><small>Cartera vencida</small><strong>{formatCurrency(summary.overdue_portfolio)}</strong><p>{summary.overdue_customers} clientes en mora</p></article>
      <article><span><HandCoins size={19} /></span><small>Cobrado este mes</small><strong>{formatCurrency(summary.collected_this_month)}</strong><p>Pagos confirmados</p></article>
      <article><span><TrendingUp size={19} /></span><small>Clientes al día</small><strong>{summary.current_customers}</strong><p>{summary.critical_customers} críticos</p></article>
    </section>}
    {user?.permisos.cobranza.view_portfolio && <Link className="primary-action dashboard-portfolio-link" to="/cartera">Abrir cartera y agenda de cobranza</Link>}
    {cashSummary && <><div className="section-heading dashboard-cash-heading"><div><p className="section-kicker">Caja de hoy</p><h2>Dinero cobrado y efectivo físico</h2></div><Link className="secondary-button" to="/caja"><Landmark size={16} /> Abrir caja</Link></div><section className="portfolio-kpis dashboard-kpis dashboard-cash-kpis">
      <article><span><WalletCards size={19} /></span><small>Pagos confirmados</small><strong>{formatCurrency(cashSummary.payment_total_today)}</strong><p>Todos los métodos</p></article>
      <article><span><Banknote size={19} /></span><small>Efectivo recibido</small><strong>{formatCurrency(cashSummary.cash_received_today)}</strong><p>Dinero físico en cajas</p></article>
      <article><span><Clock3 size={19} /></span><small>Pendiente de entregar</small><strong>{formatCurrency(cashSummary.pending_settlement_cash)}</strong><p>{cashSummary.pending_settlements} liquidaciones</p></article>
      <article className={Number(cashSummary.cash_differences_today) ? "kpi-overdue" : ""}><span><AlertTriangle size={19} /></span><small>Diferencias de caja</small><strong>{formatCurrency(cashSummary.cash_differences_today)}</strong><p>{cashSummary.open_sessions} cajas abiertas</p></article>
    </section></>}
    <section className="workspace-section" aria-labelledby="workspace-title"><div className="section-heading"><div><p className="section-kicker">Su espacio</p><h2 id="workspace-title">Información de acceso</h2></div><span className="security-badge"><ShieldCheck size={16} /> Sesión protegida</span></div><div className="identity-grid"><article className="identity-card"><span className="identity-card__icon"><Building2 size={20} /></span><div><span>Organización</span><strong>{user?.organizacion?.nombre ?? "Administración global"}</strong></div></article><article className="identity-card"><span className="identity-card__icon identity-card__icon--sage"><ShieldCheck size={20} /></span><div><span>Rol</span><strong>{user?.rol?.nombre ?? "Sin rol asignado"}</strong></div></article><article className="identity-card"><span className="identity-card__icon identity-card__icon--sand"><MapPin size={20} /></span><div><span>Sucursal</span><strong>{user?.sucursal?.nombre ?? "No asignada"}</strong></div></article></div></section>
  </div>;
}
