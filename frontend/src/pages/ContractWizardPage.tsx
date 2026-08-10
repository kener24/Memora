import { ArrowLeft, ArrowRight, Check, CircleAlert, Plus, Search, UserRoundPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { BeneficiaryModal } from "../components/customers/BeneficiaryModal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { confirmContract, createContractDraft, getContractOptions } from "../services/contractService";
import { getCustomer, getCustomerOptions, listCustomers } from "../services/customerService";
import { listPlans } from "../services/planService";
import type { ContractDraftPayload, ContractModuleOptions } from "../types/contract";
import type { CustomerDetail, CustomerListItem, CustomerModuleOptions } from "../types/customer";
import type { FuneralPlanListItem } from "../types/plan";
import { formatCurrency } from "../utils/format";

const steps = ["Cliente", "Beneficiario", "Plan", "Condiciones", "Venta", "Revisión"];
function localDateValue(date = new Date()) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
const today = localDateValue();
const inThirtyDays = localDateValue(new Date(Date.now() + 30 * 86400000));

export function ContractWizardPage() {
  useDocumentTitle("Nueva venta");
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(0);
  const [options, setOptions] = useState<ContractModuleOptions | null>(null);
  const [customerOptions, setCustomerOptions] = useState<CustomerModuleOptions | null>(null);
  const [branchId, setBranchId] = useState<number>(user?.sucursal?.id ?? 0);
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [beneficiaryId, setBeneficiaryId] = useState<number | null>(null);
  const [beneficiaryModal, setBeneficiaryModal] = useState(false);
  const [plans, setPlans] = useState<FuneralPlanListItem[]>([]);
  const [plan, setPlan] = useState<FuneralPlanListItem | null>(null);
  const [discount, setDiscount] = useState("0.00");
  const [financing, setFinancing] = useState(false);
  const [initialPayment, setInitialPayment] = useState("0.00");
  const [frequency, setFrequency] = useState("monthly");
  const [installment, setInstallment] = useState("0.00");
  const [firstDue, setFirstDue] = useState(inThirtyDays);
  const [saleDate, setSaleDate] = useState(today);
  const [startDate, setStartDate] = useState(today);
  const [sellerId, setSellerId] = useState<number>(user?.id ?? 0);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([getContractOptions(), getCustomerOptions()]).then(([contractData, customerData]) => {
      setOptions(contractData); setCustomerOptions(customerData);
      const initialBranch = user?.sucursal?.id ?? contractData.branches[0]?.id ?? 0;
      setBranchId(initialBranch);
      const ownSeller = contractData.sellers.find((item) => item.id === user?.id) ?? contractData.sellers[0];
      if (ownSeller) setSellerId(ownSeller.id);
    }).catch((caught) => setError(caught instanceof ApiError ? caught.message : "No fue posible preparar la venta.")).finally(() => setLoading(false));
  }, [user?.id, user?.sucursal?.id]);

  useEffect(() => {
    const customerId = Number(params.get("customer"));
    if (!customerId) return;
    void getCustomer(customerId).then((item) => { setCustomer(item); if (item.branch?.id) setBranchId(item.branch.id); }).catch(() => setError("No fue posible recuperar el cliente recién creado."));
  }, [params]);

  useEffect(() => {
    if (!branchId) return;
    setPlan(null);
    const organizationId = options?.branches.find((item) => item.id === branchId)?.organization_id;
    const ownSeller = options?.sellers.find((item) => item.id === user?.id && item.organization_id === organizationId);
    const firstSeller = ownSeller ?? options?.sellers.find((item) => item.organization_id === organizationId);
    if (firstSeller) setSellerId(firstSeller.id);
    void listPlans({ is_active: "true", branch: branchId, page_size: 100 }).then((data) => setPlans(data.results)).catch(() => setError("No fue posible cargar los planes disponibles."));
  }, [branchId, options, user?.id]);

  useEffect(() => {
    if (!search.trim()) { setCustomers([]); return; }
    const timer = window.setTimeout(() => {
      setSearching(true);
      void listCustomers({ search: search.trim(), is_active: "true", branch: String(branchId), page_size: 8 })
        .then((data) => setCustomers(data.results)).catch(() => setError("No fue posible buscar clientes."))
        .finally(() => setSearching(false));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search, branchId]);

  const total = Math.max(0, Number(plan?.base_price ?? 0) - Number(discount || 0));
  const financed = financing ? Math.max(0, total - Number(initialPayment || 0)) : 0;
  const selectedBeneficiary = customer?.beneficiaries.find((item) => item.id === beneficiaryId) ?? null;
  const selectedOrganizationId = options?.branches.find((item) => item.id === branchId)?.organization_id;
  const availableSellers = options?.sellers.filter((item) => item.organization_id === selectedOrganizationId) ?? [];

  function stepValid() {
    if (step === 0) return Boolean(branchId && customer);
    if (step === 1) return Boolean(customer);
    if (step === 2) return Boolean(plan);
    if (step === 3) return total >= 0 && (!financing || (Number(initialPayment) < total && Number(installment) > 0 && Boolean(firstDue)));
    if (step === 4) return Boolean(sellerId && saleDate && startDate);
    return true;
  }
  function next() { if (!stepValid()) { setError("Completa la información requerida para continuar."); return; } setError(""); setStep((current) => Math.min(5, current + 1)); }
  function selectCustomer(item: CustomerListItem) { void getCustomer(item.id).then((detail) => { setCustomer(detail); setBeneficiaryId(null); setSearch(""); setCustomers([]); }); }
  function reloadCustomer(message: string) { if (!customer) return; setBeneficiaryModal(false); showToast(message); void getCustomer(customer.id).then(setCustomer); }

  async function submit() {
    if (!customer || !plan || !options) return;
    setSubmitting(true); setError("");
    const payload: ContractDraftPayload = {
      organization: options.permissions.global_access ? selectedOrganizationId : undefined,
      branch: branchId, customer: customer.id, beneficiary: beneficiaryId, plan: plan.id,
      seller: sellerId, sale_date: saleDate, start_date: startDate,
      discount: options.permissions.apply_discount ? discount || "0.00" : "0.00",
      allow_financing: financing, initial_payment_agreed: financing ? initialPayment : "0.00",
      payment_frequency: financing ? frequency : "", installment_amount: financing ? installment : "0.00",
      first_due_date: financing ? firstDue : null, notes,
    };
    try {
      const draft = await createContractDraft(payload, crypto.randomUUID());
      const confirmed = await confirmContract(draft.id, crypto.randomUUID());
      showToast(`Contrato ${confirmed.contract_number} confirmado.`);
      navigate(`/contratos/${confirmed.id}`, { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible confirmar la venta.");
    } finally { setSubmitting(false); }
  }

  if (loading) return <div className="form-loading"><span className="spinner" /><p>Preparando la venta…</p></div>;
  return <div className="module-page contract-wizard">
    <header className="module-header module-header--compact"><div><Link className="back-link" to="/contratos"><ArrowLeft size={16} /> Volver a contratos</Link><p className="section-kicker">Venta asistida</p><h2>Nuevo contrato</h2><p>Confirma cada dato antes de congelar las condiciones históricas.</p></div><span className="wizard-counter">Paso {step + 1} de 6</span></header>
    <ol className="wizard-progress" aria-label="Progreso">{steps.map((label, index) => <li key={label} className={index === step ? "current" : index < step ? "done" : ""}><span>{index < step ? <Check size={13} /> : index + 1}</span><small>{label}</small></li>)}</ol>
    {error && <div className="module-error" role="alert"><CircleAlert size={18} /><span>{error}</span></div>}
    <section className="wizard-panel">
      {step === 0 && <><WizardHeading title="Selecciona al cliente" copy="La búsqueda consulta los registros reales de la sucursal." /><label className="form-field wizard-branch"><span>Sucursal de venta *</span><select value={branchId} onChange={(e) => { setBranchId(Number(e.target.value)); setCustomer(null); }}>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</select></label>{customer ? <SelectionCard title={customer.full_name} meta={`${customer.customer_code} · ${customer.identity_number || "Sin identidad"}`} onClear={() => setCustomer(null)} /> : <><label className="search-control wizard-search"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nombre, identidad, teléfono o código" /></label>{searching && <p className="wizard-helper">Buscando…</p>}<div className="wizard-results">{customers.map((item) => <button type="button" key={item.id} onClick={() => selectCustomer(item)}><strong>{item.full_name}</strong><small>{item.customer_code} · {item.identity_number || item.phone}</small><ArrowRight size={16} /></button>)}</div><Link className="secondary-button wizard-create-link" to={`/clientes/nuevo?returnTo=${encodeURIComponent("/contratos/nuevo")}`}><UserRoundPlus size={16} /> Registrar cliente nuevo</Link></>}</>}
      {step === 1 && customer && <><WizardHeading title="Define el beneficiario" copy="Puede ser el titular u otra persona asociada al cliente." /><div className="beneficiary-choices"><button type="button" className={beneficiaryId === null ? "selected" : ""} onClick={() => setBeneficiaryId(null)}><strong>{customer.full_name}</strong><small>Titular del contrato</small></button>{customer.beneficiaries.filter((item) => item.is_active && !item.is_customer).map((item) => <button type="button" key={item.id} className={beneficiaryId === item.id ? "selected" : ""} onClick={() => setBeneficiaryId(item.id)}><strong>{item.full_name}</strong><small>{item.relationship_label} · {item.identity_number || "Sin identidad"}</small></button>)}</div><button type="button" className="secondary-button" onClick={() => setBeneficiaryModal(true)}><Plus size={15} /> Agregar beneficiario</button></>}
      {step === 2 && <><WizardHeading title="Elige el plan funerario" copy="Solo se muestran planes activos disponibles en la sucursal." /><div className="wizard-plan-grid">{plans.map((item) => <button type="button" key={item.id} className={plan?.id === item.id ? "selected" : ""} onClick={() => { setPlan(item); setFinancing(item.allow_financing); setInitialPayment(item.initial_payment); }}><span>{item.code}</span><strong>{item.name}</strong><p>{item.description || "Plan funerario"}</p><em>{formatCurrency(item.base_price)}</em><small>{item.allow_financing ? "Admite financiamiento" : "Solo contado"}</small></button>)}</div>{plans.length === 0 && <div className="compact-empty"><p>No hay planes disponibles para esta sucursal.</p></div>}</>}
      {step === 3 && plan && <><WizardHeading title="Condiciones comerciales" copy="La prima acordada no registra un pago; solo define la futura estructura financiera." /><div className="conditions-grid"><label><span>Precio del plan</span><strong>{formatCurrency(plan.base_price)}</strong></label>{options?.permissions.apply_discount && <label><span>Descuento autorizado</span><input type="number" min="0" max={plan.base_price} step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} /></label>}<label className="condition-total"><span>Total contractual</span><strong>{formatCurrency(total)}</strong></label></div>{plan.allow_financing && <label className="check-card"><input type="checkbox" checked={financing} onChange={(e) => setFinancing(e.target.checked)} /><span><strong>Venta financiada</strong><small>Preparar condiciones para el futuro calendario de cuotas.</small></span></label>}{financing && <div className="form-grid wizard-finance"><label className="form-field"><span>Prima acordada *</span><input type="number" min="0" max={total} step="0.01" value={initialPayment} onChange={(e) => setInitialPayment(e.target.value)} /></label><label className="form-field"><span>Frecuencia *</span><select value={frequency} onChange={(e) => setFrequency(e.target.value)}>{options?.payment_frequencies.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label className="form-field"><span>Cuota esperada *</span><input type="number" min="0.01" step="0.01" value={installment} onChange={(e) => setInstallment(e.target.value)} /></label><label className="form-field"><span>Primer vencimiento *</span><input type="date" min={startDate} value={firstDue} onChange={(e) => setFirstDue(e.target.value)} /></label><div className="finance-summary">Monto sujeto a financiamiento: <strong>{formatCurrency(financed)}</strong></div></div>}</>}
      {step === 4 && <><WizardHeading title="Datos de la venta" copy="Asigna responsable, fechas y observaciones contractuales." /><div className="form-grid"><label className="form-field"><span>Fecha de venta *</span><input type="date" value={saleDate} onChange={(e) => setSaleDate(e.target.value)} /></label><label className="form-field"><span>Inicio de vigencia *</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label><label className="form-field form-field--wide"><span>Vendedor *</span><select value={sellerId} onChange={(e) => setSellerId(Number(e.target.value))} disabled={user?.rol?.codigo === "seller"}>{availableSellers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="form-field form-field--wide"><span>Observaciones</span><textarea rows={5} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Acuerdos o información relevante para el documento" /></label></div></>}
      {step === 5 && customer && plan && <><WizardHeading title="Revisa y confirma" copy="Al confirmar se congela el snapshot. El contrato activo ya no podrá editarse." /><div className="review-grid"><Review title="Cliente" value={customer.full_name} detail={customer.identity_number || customer.customer_code} /><Review title="Beneficiario" value={selectedBeneficiary?.full_name ?? customer.full_name} detail={selectedBeneficiary?.relationship_label ?? "Titular"} /><Review title="Plan" value={plan.name} detail={formatCurrency(plan.base_price)} /><Review title="Modalidad" value={financing ? "Financiado" : "Contado"} detail={financing ? `Prima ${formatCurrency(initialPayment)} · cuota ${formatCurrency(installment)}` : "Sin calendario futuro"} /><Review title="Vendedor" value={availableSellers.find((item) => item.id === sellerId)?.name ?? "—"} detail={options?.branches.find((item) => item.id === branchId)?.name ?? ""} /><Review title="Total contractual" value={formatCurrency(total)} detail={Number(discount) ? `Descuento ${formatCurrency(discount)}` : "Sin descuento"} /></div><div className="confirmation-notice"><CircleAlert size={19} /><p><strong>Confirmación irreversible.</strong> La venta quedará activa y los datos comerciales se conservarán aunque cambien los catálogos.</p></div></>}
    </section>
    <footer className="wizard-actions"><button type="button" className="secondary-button" onClick={() => step === 0 ? navigate("/contratos") : setStep((current) => current - 1)} disabled={submitting}><ArrowLeft size={16} /> {step === 0 ? "Cancelar" : "Anterior"}</button>{step < 5 ? <button type="button" className="primary-action" onClick={next}>Continuar <ArrowRight size={16} /></button> : <button type="button" className="primary-action" onClick={() => void submit()} disabled={submitting}>{submitting ? <><span className="button-spinner" /> Confirmando…</> : <><Check size={16} /> Confirmar contrato</>}</button>}</footer>
    {customer && <BeneficiaryModal open={beneficiaryModal} customerId={customer.id} beneficiary={null} relationships={customerOptions?.relationships ?? []} onClose={() => setBeneficiaryModal(false)} onSaved={reloadCustomer} />}
  </div>;
}

function WizardHeading({ title, copy }: { title: string; copy: string }) { return <header className="wizard-heading"><p className="section-kicker">Paso de venta</p><h3>{title}</h3><p>{copy}</p></header>; }
function SelectionCard({ title, meta, onClear }: { title: string; meta: string; onClear: () => void }) { return <div className="selection-card"><span><strong>{title}</strong><small>{meta}</small></span><button type="button" onClick={onClear}>Cambiar</button></div>; }
function Review({ title, value, detail }: { title: string; value: string; detail: string }) { return <article><small>{title}</small><strong>{value}</strong><span>{detail}</span></article>; }
