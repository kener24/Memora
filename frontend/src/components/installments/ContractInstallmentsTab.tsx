import { CalendarClock, CircleAlert, Download, History, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../api/client";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import {
  downloadPaymentPlanPdf, generateContractSchedule, getContractSchedule, previewContractSchedule,
  reprogramContractSchedule,
} from "../../services/installmentService";
import type { ContractDetail } from "../../types/contract";
import type { ContractSchedulePayload, ManualInstallment, ScheduleConditions, SchedulePreview } from "../../types/installment";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/format";
import { Modal } from "../Modal";
import { Pagination } from "../Pagination";

const frequencies = [{ value: "monthly", label: "Mensual" }, { value: "biweekly", label: "Cada 15 días" }, { value: "weekly", label: "Semanal" }, { value: "custom", label: "Personalizada" }];
type EditorMode = "generate" | "reprogram";

export function ContractInstallmentsTab({ contract }: { contract: ContractDetail }) {
  const { user } = useAuth(); const { showToast } = useToast();
  const [data, setData] = useState<ContractSchedulePayload | null>(null);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [page, setPage] = useState(1);
  const [working, setWorking] = useState(false); const [editorMode, setEditorMode] = useState<EditorMode | null>(null);
  const [frequency, setFrequency] = useState(contract.payment_frequency || "monthly");
  const [amount, setAmount] = useState(contract.installment_amount || "");
  const [firstDue, setFirstDue] = useState(contract.first_due_date || ""); const [reason, setReason] = useState("");
  const [manual, setManual] = useState<ManualInstallment[]>([{ due_date: contract.first_due_date || "", amount: "" }]);
  const [preview, setPreview] = useState<SchedulePreview | null>(null); const [formError, setFormError] = useState("");
  const permissions = user?.permisos.cuotas;

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await getContractSchedule(contract.id, page)); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar el calendario."); }
    finally { setLoading(false); }
  }, [contract.id, page]);
  useEffect(() => { void load(); }, [load]);
  const isCustom = frequency === "custom";
  const manualTotal = useMemo(() => manual.reduce((sum, item) => sum + (Number(item.amount) || 0), 0), [manual]);

  function openEditor(mode: EditorMode) {
    const schedule = data?.schedule;
    setEditorMode(mode); setFrequency(mode === "reprogram" && schedule ? schedule.frequency : contract.payment_frequency || "monthly");
    setAmount(mode === "reprogram" && schedule ? schedule.regular_installment_amount : contract.installment_amount || "");
    setFirstDue(mode === "reprogram" && schedule ? schedule.first_due_date : contract.first_due_date || "");
    setReason(""); setPreview(null); setFormError("");
    if (schedule?.frequency === "custom" && data?.installments?.results.length) setManual(data.installments.results.map((item) => ({ due_date: item.due_date, amount: item.current_amount })));
    else setManual([{ due_date: contract.first_due_date || "", amount: "" }]);
  }
  function payload(): ScheduleConditions {
    return isCustom ? { frequency, manual_installments: manual, reason } : { frequency, installment_amount: amount, first_due_date: firstDue, reason };
  }
  async function calculatePreview() {
    setWorking(true); setFormError("");
    try { setPreview(await previewContractSchedule(contract.id, payload())); }
    catch (caught) { setFormError(caught instanceof ApiError ? caught.message : "No fue posible calcular la vista previa."); }
    finally { setWorking(false); }
  }
  async function saveEditor() {
    setWorking(true); setFormError("");
    try {
      if (editorMode === "generate") await generateContractSchedule(contract.id, manual);
      else await reprogramContractSchedule(contract.id, payload());
      setEditorMode(null); setPage(1); await load(); showToast(editorMode === "generate" ? "Calendario generado correctamente." : "Calendario reprogramado con historial.");
    } catch (caught) { setFormError(caught instanceof ApiError ? caught.message : "No fue posible guardar el calendario."); }
    finally { setWorking(false); }
  }
  async function generateAutomatic() {
    setWorking(true);
    try { await generateContractSchedule(contract.id); await load(); showToast("Calendario generado correctamente."); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible generar el calendario.", "error"); }
    finally { setWorking(false); }
  }
  async function downloadPdf() {
    setWorking(true);
    try { const blob = await downloadPaymentPlanPdf(contract.id); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `Plan_Pagos_${contract.contract_number}.pdf`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 60000); }
    catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible descargar el plan.", "error"); }
    finally { setWorking(false); }
  }
  if (loading && !data) return <div className="table-loading">Cargando calendario de cuotas…</div>;
  if (error && !data) return <div className="inline-error"><CircleAlert size={18} />{error}<button onClick={() => void load()}>Reintentar</button></div>;
  if (!data?.schedule) return <section className="installment-empty"><CalendarClock size={34} /><h3>{data?.reason === "cash" ? "Contrato al contado" : "Calendario pendiente de generación"}</h3><p>{data?.reason === "cash" ? "Este contrato no tiene monto financiado y no genera obligaciones." : contract.payment_frequency === "custom" ? "Define las fechas e importes del calendario personalizado." : "Este contrato activo es compatible con la generación segura del calendario."}</p>{contract.status === "active" && data?.reason !== "cash" && permissions?.generate_schedule && (contract.payment_frequency === "custom" ? <button className="primary-action" onClick={() => openEditor("generate")}><Plus size={16} /> Crear calendario personalizado</button> : <button className="primary-action" disabled={working} onClick={() => void generateAutomatic()}><Plus size={16} /> Generar calendario</button>)}{editorMode && renderEditor()}</section>;

  const schedule = data.schedule; const installments = data.installments;
  return <div className="contract-installments">
    <section className="schedule-summary"><div><p className="section-kicker">Calendario activo</p><h3>Plan de pagos · versión {schedule.version}</h3><p>{schedule.frequency_label} · {schedule.total_installments} cuotas · {formatDate(schedule.first_due_date)} a {formatDate(schedule.last_due_date)}</p></div><div className="schedule-summary__actions"><button className="secondary-button" disabled={working} onClick={() => void downloadPdf()}><Download size={16} /> Plan de pagos</button>{contract.status === "active" && permissions?.reprogram_schedule && <button className="secondary-button" onClick={() => openEditor("reprogram")}><RefreshCw size={16} /> Reprogramar</button>}</div><dl><div><dt>Financiado</dt><dd>{formatCurrency(schedule.total_financed)}</dd></div><div><dt>Cuota regular</dt><dd>{formatCurrency(schedule.regular_installment_amount)}</dd></div><div><dt>Vigencia</dt><dd><span className={`installment-status installment-status--${schedule.status}`}>{schedule.status_label}</span></dd></div><div><dt>Generado</dt><dd>{formatDateTime(schedule.generated_at)}</dd></div></dl></section>
    {installments && <section className="data-card"><div className="table-scroll"><table className="data-table installment-table"><thead><tr><th>#</th><th>Vencimiento</th><th>Monto original</th><th>Monto vigente</th><th>Pagado</th><th>Pendiente</th><th>Estado</th></tr></thead><tbody>{installments.results.map((item) => <tr key={item.id}><td>{item.installment_number}</td><td><strong>{formatDate(item.due_date)}</strong></td><td>{formatCurrency(item.original_amount)}</td><td>{formatCurrency(item.current_amount)}</td><td>{formatCurrency(item.paid_amount)}</td><td>{formatCurrency(item.pending_amount)}</td><td><span className={`installment-status installment-status--${item.effective_status}`}>{item.effective_status_label}</span></td></tr>)}</tbody></table></div><Pagination page={installments.page} totalPages={installments.total_pages} hasNext={Boolean(installments.next)} hasPrevious={Boolean(installments.previous)} onChange={setPage} /></section>}
    {data.history.length > 1 && <section className="schedule-history"><header><History size={17} /><h3>Versiones anteriores</h3></header>{data.history.filter((item) => item.id !== schedule.id).map((item) => <article key={item.id}><div><strong>Versión {item.version} · {item.status_label}</strong><p>{item.frequency_label} · {item.total_installments} cuotas · {formatCurrency(item.total_financed)}</p>{item.reprogramming_reason && <small>Motivo: {item.reprogramming_reason}</small>}</div><time>{formatDateTime(item.updated_at)}</time></article>)}</section>}
    {editorMode && renderEditor()}
  </div>;

  function renderEditor() { return <Modal open={Boolean(editorMode)} onClose={() => !working && setEditorMode(null)} title={editorMode === "generate" ? "Crear calendario personalizado" : "Reprogramar calendario"} description="La vista previa no guarda cambios. Al confirmar, la versión anterior permanece en el historial.">
    <div className="schedule-editor"><div className="schedule-editor__fields">{editorMode === "reprogram" && <label><span>Frecuencia</span><select value={frequency} onChange={(e) => { setFrequency(e.target.value); setPreview(null); }}>{frequencies.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>}{!isCustom && <><label><span>Monto de cuota</span><input inputMode="decimal" value={amount} onChange={(e) => { setAmount(e.target.value); setPreview(null); }} /></label><label><span>Primer vencimiento</span><input type="date" value={firstDue} onChange={(e) => { setFirstDue(e.target.value); setPreview(null); }} /></label></>}{editorMode === "reprogram" && <label className="field-wide"><span>Motivo obligatorio</span><textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Documenta la razón del cambio" /></label>}</div>
    {isCustom && <div className="manual-schedule"><div className="manual-schedule__header"><div><strong>Cuotas manuales</strong><small>Total ingresado: {formatCurrency(manualTotal)} de {formatCurrency(contract.financed_amount)}</small></div><button className="secondary-button" onClick={() => setManual((items) => [...items, { due_date: "", amount: "" }])}><Plus size={15} /> Agregar</button></div>{manual.map((item, index) => <div className="manual-row" key={index}><span>{index + 1}</span><input aria-label={`Fecha cuota ${index + 1}`} type="date" value={item.due_date} onChange={(e) => setManual((items) => items.map((current, position) => position === index ? { ...current, due_date: e.target.value } : current))} /><input aria-label={`Monto cuota ${index + 1}`} inputMode="decimal" value={item.amount} placeholder="0.00" onChange={(e) => setManual((items) => items.map((current, position) => position === index ? { ...current, amount: e.target.value } : current))} /><button className="icon-button" aria-label={`Eliminar cuota ${index + 1}`} disabled={manual.length === 1} onClick={() => setManual((items) => items.filter((_, position) => position !== index))}><Trash2 size={16} /></button></div>)}</div>}
    {formError && <div className="inline-error"><CircleAlert size={17} />{formError}</div>}{preview && <div className="schedule-preview"><header><strong>Vista previa: {preview.total_installments} cuotas</strong><span>{formatCurrency(preview.total)}</span></header><div className="preview-list">{preview.items.map((item) => <div key={item.installment_number}><span>#{item.installment_number}</span><span>{formatDate(item.due_date)}</span><strong>{formatCurrency(item.amount)}</strong></div>)}</div></div>}
    <div className="modal-actions"><button className="secondary-button" onClick={() => setEditorMode(null)} disabled={working}>Cancelar</button>{editorMode === "reprogram" && <button className="secondary-button" onClick={() => void calculatePreview()} disabled={working || reason.trim().length < 5}>{working ? "Calculando…" : "Calcular vista previa"}</button>}<button className="primary-action" onClick={() => void saveEditor()} disabled={working || (editorMode === "reprogram" && (!preview || reason.trim().length < 5))}>{working ? "Guardando…" : editorMode === "generate" ? "Generar calendario" : "Confirmar reprogramación"}</button></div></div>
  </Modal>; }
}
