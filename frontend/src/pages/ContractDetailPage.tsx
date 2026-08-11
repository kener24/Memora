import { ArrowLeft, CalendarClock, CalendarDays, CircleAlert, Download, FileText, HandCoins, History, Printer, ReceiptText, ShieldCheck, UserRound, XCircle } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { ContractInstallmentsTab } from "../components/installments/ContractInstallmentsTab";
import { ContractCollectionTab } from "../components/collections/ContractCollectionTab";
import { ContractPaymentsTab } from "../components/payments/ContractPaymentsTab";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { cancelContract, downloadContractPdf, getContract } from "../services/contractService";
import type { ContractDetail } from "../types/contract";
import { displayValue, formatCurrency, formatDate, formatDateTime } from "../utils/format";

type Tab = "summary" | "services" | "conditions" | "installments" | "payments" | "collections" | "history";

export function ContractDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [tab, setTab] = useState<Tab>(searchParams.get("tab") === "payments" ? "payments" : "summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  useDocumentTitle(contract ? contract.contract_number : "Detalle de contrato");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true); setError("");
    try { setContract(await getContract(id)); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar el contrato."); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  async function getPdf(mode: "download" | "print") {
    if (!contract) return;
    setDownloading(true);
    try {
      const blob = await downloadContractPdf(contract.id);
      const url = URL.createObjectURL(blob);
      if (mode === "download") {
        const link = document.createElement("a"); link.href = url; link.download = `Contrato_${contract.contract_number}.pdf`; link.click();
      } else {
        const popup = window.open(url, "_blank", "noopener,noreferrer"); if (!popup) throw new Error("popup");
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible abrir el PDF.", "error"); }
    finally { setDownloading(false); }
  }

  async function submitCancel() {
    if (!contract || reason.trim().length < 5) return;
    setCancelling(true);
    try { const updated = await cancelContract(contract.id, reason.trim()); setContract(updated); setCancelOpen(false); showToast("Contrato cancelado con trazabilidad."); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible cancelar.", "error"); }
    finally { setCancelling(false); }
  }

  if (loading) return <div className="detail-loading"><div className="detail-skeleton detail-skeleton--hero" /><div className="detail-skeleton" /></div>;
  if (error || !contract) return <div className="detail-error"><CircleAlert size={28} /><h2>No fue posible abrir el contrato</h2><p>{error}</p><div><button className="secondary-button" onClick={() => navigate("/contratos")}>Volver</button><button className="primary-action" onClick={() => void load()}>Reintentar</button></div></div>;

  return <div className="module-page contract-detail-page">
    <Link className="back-link" to="/contratos"><ArrowLeft size={16} /> Volver a contratos</Link>
    <section className="contract-hero"><div><div className="contract-hero__meta"><span>{contract.contract_number}</span><span className={`contract-status contract-status--${contract.status}`}>{contract.status_label}</span></div><h2>{contract.customer_name_snapshot}</h2><p>{contract.plan_name_snapshot} · {contract.branch.name}</p><div className="contract-hero__facts"><span><CalendarDays size={14} /> Venta {formatDate(contract.sale_date)}</span><span><UserRound size={14} /> {contract.seller.name}</span><span><ReceiptText size={14} /> {formatCurrency(contract.total_price)}</span></div></div><div className="contract-hero__actions"><button className="secondary-button" onClick={() => void getPdf("download")} disabled={downloading}><Download size={16} /> Descargar PDF</button><button className="secondary-button" onClick={() => void getPdf("print")} disabled={downloading}><Printer size={16} /> Imprimir</button>{contract.status === "active" && user?.permisos.contratos.cancel && <button className="danger-outline-button" onClick={() => setCancelOpen(true)}><XCircle size={16} /> Cancelar</button>}</div></section>
    {contract.status === "cancelled" && <div className="cancellation-banner"><XCircle size={19} /><div><strong>Contrato cancelado</strong><p>{contract.cancellation_reason} · {formatDateTime(contract.cancelled_at)} por {contract.cancelled_by?.name}</p></div></div>}
    <nav className="detail-tabs" aria-label="Secciones del contrato"><button className={tab === "summary" ? "detail-tab--active" : ""} onClick={() => setTab("summary")}><FileText size={15} /> Resumen</button><button className={tab === "services" ? "detail-tab--active" : ""} onClick={() => setTab("services")}><ShieldCheck size={15} /> Prestaciones <span>{contract.plan_items.length}</span></button><button className={tab === "conditions" ? "detail-tab--active" : ""} onClick={() => setTab("conditions")}><ReceiptText size={15} /> Condiciones</button><button className={tab === "installments" ? "detail-tab--active" : ""} onClick={() => setTab("installments")}><CalendarClock size={15} /> Cuotas</button>{user?.permisos.pagos.view_payment && <button className={tab === "payments" ? "detail-tab--active" : ""} onClick={() => setTab("payments")}><ReceiptText size={15} /> Pagos</button>}{user?.permisos.cobranza.view_portfolio && <button className={tab === "collections" ? "detail-tab--active" : ""} onClick={() => setTab("collections")}><HandCoins size={15} /> Cobranza</button>}<button className={tab === "history" ? "detail-tab--active" : ""} onClick={() => setTab("history")}><History size={15} /> Historial <span>{contract.activities.length}</span></button></nav>
    {tab === "summary" && <div className="summary-layout"><InfoCard title="Cliente contractual" icon={<UserRound size={16} />}><Info label="Nombre" value={contract.customer_name_snapshot} /><Info label="Identidad" value={displayValue(contract.customer_identity_snapshot)} /><Info label="Teléfono" value={displayValue(contract.customer_phone_snapshot)} /><Info label="Dirección" value={displayValue(contract.customer_address_snapshot)} /></InfoCard><InfoCard title="Beneficiario" icon={<ShieldCheck size={16} />}><Info label="Nombre" value={contract.beneficiary_name_snapshot} /><Info label="Identidad" value={displayValue(contract.beneficiary_identity_snapshot)} /><Info label="Relación" value={contract.beneficiary_relationship_snapshot} /><Info label="Registro fuente" value={contract.beneficiary?.name ?? "Titular"} /></InfoCard><InfoCard title="Venta y vigencia" icon={<CalendarDays size={16} />} wide><Info label="Número" value={contract.contract_number} /><Info label="Venta" value={formatDate(contract.sale_date)} /><Info label="Inicio" value={formatDate(contract.start_date)} /><Info label="Vendedor" value={contract.seller.name} /><Info label="Sucursal" value={contract.branch.name} /><Info label="Creado por" value={contract.created_by.name} /></InfoCard>{contract.notes && <InfoCard title="Observaciones" icon={<FileText size={16} />} wide><p className="notes-copy">{contract.notes}</p></InfoCard>}</div>}
    {tab === "services" && <section className="related-section"><header><div><p className="section-kicker">Snapshot histórico</p><h3>{contract.plan_name_snapshot}</h3><p>{contract.plan_description_snapshot}</p></div></header><div className="contract-service-list">{contract.plan_items.map((item) => <article key={item.id}><span>{item.quantity} ×</span><div><strong>{item.service_name_snapshot}</strong><small>{item.service_code_snapshot} · {item.category_snapshot} · {item.unit_snapshot}</small>{item.notes_snapshot && <p>{item.notes_snapshot}</p>}</div>{item.estimated_cost_snapshot !== undefined && <em>Costo interno {formatCurrency(item.estimated_cost_snapshot)}</em>}</article>)}</div></section>}
    {tab === "conditions" && <div className="contract-conditions"><section className="financial-card"><h3>Resumen comercial</h3><dl><div><dt>Precio del plan</dt><dd>{formatCurrency(contract.subtotal)}</dd></div><div><dt>Descuento</dt><dd>− {formatCurrency(contract.discount)}</dd></div><div className="financial-total"><dt>Total contractual</dt><dd>{formatCurrency(contract.total_price)}</dd></div><div><dt>Prima acordada</dt><dd>{formatCurrency(contract.initial_payment_agreed)}</dd></div><div><dt>Monto financiado</dt><dd>{formatCurrency(contract.financed_amount)}</dd></div></dl></section><section className="info-card"><header><span><CalendarDays size={16} /></span><h3>Condiciones futuras</h3></header>{contract.allow_financing ? <dl className="info-grid"><Info label="Frecuencia" value={contract.payment_frequency_label} /><Info label="Cuota esperada" value={formatCurrency(contract.installment_amount)} /><Info label="Primer vencimiento" value={formatDate(contract.first_due_date)} /><Info label="Aclaración" value="No constituye pago recibido" /></dl> : <p className="notes-copy">Venta al contado. Este contrato no constituye un comprobante de dinero recibido.</p>}</section></div>}
    {tab === "installments" && <ContractInstallmentsTab contract={contract} />}
    {tab === "payments" && <ContractPaymentsTab contract={contract} autoOpen={searchParams.get("payment") === "new"} />}
    {tab === "collections" && <ContractCollectionTab contractId={contract.id} />}
    {tab === "history" && <section className="history-section"><header><div><p className="section-kicker">Trazabilidad</p><h3>Historial del contrato</h3><p>Acciones relevantes registradas por Memora.</p></div></header><ol className="activity-timeline">{contract.activities.map((item) => <li key={item.id}><span className="activity-timeline__dot"><History size={15} /></span><div><strong>{item.action_label}</strong><p>{item.description}</p><small>{formatDateTime(item.created_at)} · {item.user?.name ?? "Sistema"}</small></div></li>)}</ol></section>}
    <Modal open={cancelOpen} onClose={() => !cancelling && setCancelOpen(false)} title="Cancelar contrato" description="Esta acción es irreversible y quedará auditada." size="small"><label className="related-field"><span>Motivo de cancelación *</span><textarea rows={5} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Describe el motivo documentado" /></label><div className="modal-actions"><button className="secondary-button" onClick={() => setCancelOpen(false)} disabled={cancelling}>Conservar contrato</button><button className="danger-button" onClick={() => void submitCancel()} disabled={cancelling || reason.trim().length < 5}>{cancelling ? "Cancelando…" : "Confirmar cancelación"}</button></div></Modal>
  </div>;
}

function InfoCard({ title, icon, wide, children }: { title: string; icon: ReactNode; wide?: boolean; children: ReactNode }) { return <section className={`info-card ${wide ? "info-card--wide" : ""}`}><header><span>{icon}</span><h3>{title}</h3></header><dl className="info-grid">{children}</dl></section>; }
function Info({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
