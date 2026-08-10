import { Banknote, CircleAlert, Download, Eye, FileCheck2, Plus, Printer, ReceiptText, ShieldAlert, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import {
  createPayment, downloadReceiptPdf, getContractPayments, previewPayment,
  settleContract, voidPayment,
} from "../../services/paymentService";
import type { ContractDetail } from "../../types/contract";
import type { ContractPaymentsPayload, Payment, PaymentPreview } from "../../types/payment";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/format";
import { Modal } from "../Modal";
import { Pagination } from "../Pagination";

const types = [
  { value: "initial_payment", label: "Prima" }, { value: "installment", label: "Cuota / abono" },
  { value: "advance", label: "Adelanto" }, { value: "other", label: "Otro" },
];
const methods = [
  { value: "cash", label: "Efectivo" }, { value: "transfer", label: "Transferencia" },
  { value: "card", label: "Tarjeta" }, { value: "check", label: "Cheque" }, { value: "other", label: "Otro" },
];

export function ContractPaymentsTab({ contract }: { contract: ContractDetail }) {
  const { user } = useAuth(); const { showToast } = useToast();
  const permissions = user?.permisos.pagos;
  const [data, setData] = useState<ContractPaymentsPayload | null>(null);
  const [page, setPage] = useState(1); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [formOpen, setFormOpen] = useState(false); const [settlementMode, setSettlementMode] = useState(false);
  const [amount, setAmount] = useState(""); const [paymentType, setPaymentType] = useState("installment");
  const [method, setMethod] = useState("cash"); const [reference, setReference] = useState(""); const [notes, setNotes] = useState(""); const [paymentDate, setPaymentDate] = useState("");
  const [preview, setPreview] = useState<PaymentPreview | null>(null); const [working, setWorking] = useState(false); const [formError, setFormError] = useState(""); const [key, setKey] = useState("");
  const [result, setResult] = useState<Payment | null>(null); const [receiptOpen, setReceiptOpen] = useState(false);
  const [voidTarget, setVoidTarget] = useState<Payment | null>(null); const [voidReason, setVoidReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await getContractPayments(contract.id, page)); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar los pagos."); }
    finally { setLoading(false); }
  }, [contract.id, page]);
  useEffect(() => { void load(); }, [load]);

  function openPayment(settle = false) {
    setSettlementMode(settle); setPaymentType(settle ? "settlement" : "installment");
    setAmount(settle ? data?.financial_summary.contract_balance ?? contract.financial_summary.contract_balance : "");
    setMethod("cash"); setReference(""); setNotes(""); setPaymentDate(""); setPreview(null); setFormError("");
    setKey(crypto.randomUUID()); setResult(null); setFormOpen(true);
  }
  async function calculate() {
    setWorking(true); setFormError("");
    try { setPreview(await previewPayment(contract.id, { amount, payment_type: paymentType })); }
    catch (caught) { setFormError(caught instanceof ApiError ? caught.message : "No fue posible calcular la aplicación."); }
    finally { setWorking(false); }
  }
  async function submit() {
    if (!preview) return;
    setWorking(true); setFormError("");
    try {
      const payment = settlementMode ? await settleContract(contract.id, {
        expected_balance: preview.balance_before, payment_method: method, reference, notes,
        ...(paymentDate ? { payment_date: paymentDate } : {}),
      }, key) : await createPayment({
        contract: contract.id, amount, payment_type: paymentType, payment_method: method, reference, notes,
        ...(paymentDate ? { payment_date: paymentDate } : {}),
      }, key);
      setResult(payment); setPreview(null); await load(); showToast("Pago registrado correctamente.");
    } catch (caught) { setFormError(caught instanceof ApiError ? caught.message : "No fue posible registrar el pago."); }
    finally { setWorking(false); }
  }
  async function receiptAction(payment: Payment, mode: "download" | "print") {
    setWorking(true);
    try {
      const blob = await downloadReceiptPdf(payment.id); const url = URL.createObjectURL(blob);
      if (mode === "download") { const link = document.createElement("a"); link.href = url; link.download = `Recibo_${payment.receipt.receipt_number}.pdf`; link.click(); }
      else { const popup = window.open(url, "_blank", "noopener,noreferrer"); if (!popup) throw new Error("popup"); }
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible abrir el recibo.", "error"); }
    finally { setWorking(false); }
  }
  async function confirmVoid() {
    if (!voidTarget || voidReason.trim().length < 5) return;
    setWorking(true);
    try { await voidPayment(voidTarget.id, voidReason.trim()); setVoidTarget(null); setVoidReason(""); await load(); showToast("Pago anulado y cuotas reconstruidas."); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible anular el pago.", "error"); }
    finally { setWorking(false); }
  }

  if (loading && !data) return <div className="table-loading">Cargando historial financiero…</div>;
  if (error && !data) return <div className="inline-error"><CircleAlert size={17} />{error}<button onClick={() => void load()}>Reintentar</button></div>;
  const summary = data?.financial_summary ?? contract.financial_summary;
  const payments = data?.payments;
  return <div className="contract-payments">
    <section className="payment-financial-summary">
      <header><div><p className="section-kicker">Estado financiero</p><h3>{summary.financial_status_label}</h3></div><span className={`financial-status financial-status--${summary.financial_status}`}>{summary.financial_status_label}</span></header>
      <div className="financial-metrics"><article><small>Valor contractual</small><strong>{formatCurrency(summary.total_price)}</strong></article><article><small>Total pagado</small><strong>{formatCurrency(summary.total_paid)}</strong></article><article className="balance-metric"><small>Saldo pendiente</small><strong>{formatCurrency(summary.contract_balance)}</strong></article></div>
      <div className="financial-breakdown"><div><strong>Prima</strong><span>Acordada {formatCurrency(summary.initial_payment_agreed)}</span><span>Pagada {formatCurrency(summary.initial_payment_paid)}</span><span>Pendiente {formatCurrency(summary.initial_payment_pending)}</span></div><div><strong>Cuotas financiadas</strong><span>Total {formatCurrency(summary.financed_amount)}</span><span>Pagado {formatCurrency(summary.financed_paid)}</span><span>Pendiente {formatCurrency(summary.financed_pending)}</span></div></div>
      {contract.status === "active" && Number(summary.contract_balance) > 0 && permissions?.create_payment && <div className="financial-actions"><button className="primary-action" onClick={() => openPayment(false)}><Plus size={16} /> Registrar pago</button>{permissions.settle_contract && <button className="secondary-button" onClick={() => openPayment(true)}><Banknote size={16} /> Liquidar contrato</button>}</div>}
    </section>
    <section className="data-card payment-history-card">
      <header className="payment-history-header"><div><p className="section-kicker">Dinero recibido</p><h3>Historial de pagos</h3></div></header>
      {loading ? <div className="table-loading">Actualizando pagos…</div> : !payments?.results.length ? <div className="empty-state"><ReceiptText size={30} /><h3>Este contrato todavía no tiene pagos.</h3><p>Cuando se registre dinero recibido, el recibo y sus aplicaciones aparecerán aquí.</p></div> : <><div className="table-scroll"><table className="data-table payment-table"><thead><tr><th>Fecha</th><th>Recibo</th><th>Concepto</th><th>Monto</th><th>Método</th><th>Recibido por</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{payments.results.map((payment) => <tr key={payment.id}><td>{formatDateTime(payment.payment_date)}</td><td><strong>{payment.receipt.receipt_number}</strong><small>{payment.payment_number}</small></td><td>{payment.payment_type_label}</td><td><strong>{formatCurrency(payment.amount)}</strong></td><td>{payment.payment_method_label}<small>{payment.reference}</small></td><td>{payment.received_by.name}</td><td><span className={`payment-status payment-status--${payment.status}`}>{payment.status_label}</span>{payment.status === "voided" && <small>{payment.void_reason}</small>}</td><td><div className="payment-row-actions"><button title="Ver recibo" onClick={() => { setResult(payment); setReceiptOpen(true); }}><Eye size={15} /></button><button title="Descargar recibo" onClick={() => void receiptAction(payment, "download")}><Download size={15} /></button>{payment.status === "confirmed" && permissions?.void_payment && <button className="danger-text" title="Anular pago" onClick={() => setVoidTarget(payment)}><XCircle size={15} /></button>}</div></td></tr>)}</tbody></table></div><Pagination page={payments.page} totalPages={payments.total_pages} hasNext={Boolean(payments.next)} hasPrevious={Boolean(payments.previous)} onChange={setPage} /></>}
    </section>
    <Modal open={formOpen} onClose={() => !working && setFormOpen(false)} title={settlementMode ? "Liquidar contrato" : "Registrar pago"} description="Memora volverá a validar el saldo y distribuirá el dinero al confirmar.">
      {result ? <div className="payment-result"><span><FileCheck2 size={30} /></span><h3>Pago registrado correctamente</h3><p>Se emitió el recibo <strong>{result.receipt.receipt_number}</strong> por {formatCurrency(result.amount)}.</p><div className="receipt-actions"><button className="secondary-button" onClick={() => setReceiptOpen(true)}><Eye size={16} /> Ver recibo</button><button className="secondary-button" disabled={working} onClick={() => void receiptAction(result, "download")}><Download size={16} /> Descargar PDF</button><button className="secondary-button" disabled={working} onClick={() => void receiptAction(result, "print")}><Printer size={16} /> Imprimir</button></div><button className="primary-action" onClick={() => setFormOpen(false)}>Volver al contrato</button></div> : <div className="payment-form">
        <section className="payment-context"><div><small>Cliente</small><strong>{contract.customer_name_snapshot}</strong></div><div><small>Contrato</small><strong>{contract.contract_number}</strong></div><div><small>Saldo actual</small><strong>{formatCurrency(summary.contract_balance)}</strong></div><div><small>Prima pendiente</small><strong>{formatCurrency(summary.initial_payment_pending)}</strong></div></section>
        <div className="payment-fields"><label><span>Monto recibido</span><input inputMode="decimal" value={amount} readOnly={settlementMode} onChange={(e) => { setAmount(e.target.value); setPreview(null); }} placeholder="0.00" /></label><label><span>Tipo de pago</span><select value={paymentType} disabled={settlementMode} onChange={(e) => { setPaymentType(e.target.value); setPreview(null); }}>{types.filter((item) => item.value !== "initial_payment" || permissions?.register_initial_payment).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Método</span><select value={method} onChange={(e) => setMethod(e.target.value)}>{methods.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Referencia {method === "cash" || method === "other" ? "(opcional)" : "*"}</span><input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Voucher, transferencia o cheque" /></label>{permissions?.backdate_payment && <label><span>Fecha administrativa (opcional)</span><input type="datetime-local" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} /></label>}<label className="field-wide"><span>Notas</span><textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observación del cobro" /></label></div>
        {formError && <div className="inline-error"><CircleAlert size={17} />{formError}</div>}{preview && <section className="allocation-preview"><header><div><small>Monto recibido</small><strong>{formatCurrency(preview.amount)}</strong></div><div><small>Saldo después</small><strong>{formatCurrency(preview.balance_after)}</strong></div></header><h4>Aplicación prevista</h4>{Number(preview.initial_amount) > 0 && <div><span>Prima contractual</span><strong>{formatCurrency(preview.initial_amount)}</strong></div>}{preview.applications.map((item) => <div key={item.installment_id}><span>Cuota #{item.installment_number} · {formatDate(item.due_date)}</span><strong>{formatCurrency(item.amount)}</strong></div>)}{Number(preview.direct_amount) > 0 && <div><span>Saldo contractual</span><strong>{formatCurrency(preview.direct_amount)}</strong></div>}</section>}
        <div className="modal-actions"><button className="secondary-button" onClick={() => setFormOpen(false)} disabled={working}>Cancelar</button><button className="secondary-button" onClick={() => void calculate()} disabled={working || !amount}>{working ? "Calculando…" : "Calcular aplicación"}</button><button className="primary-action" onClick={() => void submit()} disabled={working || !preview}>{working ? "Procesando…" : "Confirmar pago"}</button></div>
      </div>}
    </Modal>
    <Modal open={receiptOpen && Boolean(result)} onClose={() => setReceiptOpen(false)} title={`Recibo ${result?.receipt.receipt_number ?? ""}`} description="Comprobante histórico del dinero recibido." size="small">{result && <ReceiptView payment={result} />}<div className="modal-actions"><button className="secondary-button" onClick={() => setReceiptOpen(false)}>Cerrar</button>{result && <button className="primary-action" onClick={() => void receiptAction(result, "print")}><Printer size={16} /> Imprimir</button>}</div></Modal>
    <Modal open={Boolean(voidTarget)} onClose={() => !working && setVoidTarget(null)} title="Anular pago" description="El pago y su recibo permanecerán en el historial. Las cuotas se reconstruirán." size="small"><div className="void-warning"><ShieldAlert size={20} /><p>Se anulará {voidTarget?.payment_number} por {formatCurrency(voidTarget?.amount)}.</p></div><label className="related-field"><span>Motivo obligatorio</span><textarea rows={4} value={voidReason} onChange={(e) => setVoidReason(e.target.value)} placeholder="Describe la razón documentada" /></label><div className="modal-actions"><button className="secondary-button" onClick={() => setVoidTarget(null)} disabled={working}>Conservar pago</button><button className="danger-button" onClick={() => void confirmVoid()} disabled={working || voidReason.trim().length < 5}>{working ? "Anulando…" : "Confirmar anulación"}</button></div></Modal>
  </div>;
}

function ReceiptView({ payment }: { payment: Payment }) {
  const receipt = payment.receipt;
  return <div className={`receipt-view ${receipt.status === "voided" ? "receipt-view--voided" : ""}`}>{receipt.status === "voided" && <strong className="receipt-void-label">ANULADO</strong>}<div className="receipt-view__brand"><ReceiptText size={22} /><div><strong>{receipt.organization_name_snapshot}</strong><small>{receipt.receipt_number} · {formatDateTime(receipt.issued_at)}</small></div></div><dl><div><dt>Cliente</dt><dd>{receipt.customer_name_snapshot}</dd></div><div><dt>Contrato</dt><dd>{receipt.contract_number_snapshot}</dd></div><div><dt>Concepto</dt><dd>{receipt.concept_snapshot}</dd></div><div><dt>Método</dt><dd>{receipt.method_snapshot}</dd></div>{receipt.reference_snapshot && <div><dt>Referencia</dt><dd>{receipt.reference_snapshot}</dd></div>}<div><dt>Saldo anterior</dt><dd>{formatCurrency(receipt.balance_before)}</dd></div><div><dt>Monto recibido</dt><dd>{formatCurrency(receipt.amount_snapshot)}</dd></div><div><dt>Saldo posterior</dt><dd>{formatCurrency(receipt.balance_after)}</dd></div></dl><h4>Aplicaciones</h4>{receipt.applications_snapshot.map((item, index) => <div className="receipt-application" key={index}><span>{item.kind === "installment" ? `Cuota #${item.installment_number}` : item.label}</span><strong>{formatCurrency(item.amount)}</strong></div>)}<small>Recibido por {receipt.received_by_snapshot}</small></div>;
}
