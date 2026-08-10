import { ArrowLeft, Calculator, Check, Plus, Save, Search, Trash2, X } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { Modal } from "../components/Modal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { createPlan, getPlan, getPlanOptions, listServices, updatePlan } from "../services/planService";
import type { FuneralPlanPayload, PlanItemService, PlanModuleOptions, ServiceCatalogItem } from "../types/plan";
import { formatCurrency } from "../utils/format";

interface SelectedItem {
  service: PlanItemService;
  quantity: string;
  notes: string;
}

const initialForm: FuneralPlanPayload = {
  name: "", description: "", base_price: "0.00", initial_payment: "0.00",
  allow_financing: false, available_all_branches: true, available_branch_ids: [], items: [],
};

function apiErrors(error: ApiError): Record<string, string> {
  return Object.fromEntries(Object.entries(error.errors).map(([key, value]) => [
    key,
    Array.isArray(value) ? String(value[0]) : typeof value === "string" ? value : error.message,
  ]));
}

export function PlanFormPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [form, setForm] = useState<FuneralPlanPayload>(initialForm);
  const [selected, setSelected] = useState<SelectedItem[]>([]);
  const [options, setOptions] = useState<PlanModuleOptions | null>(null);
  const [loading, setLoading] = useState(editing);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorSearch, setSelectorSearch] = useState("");
  const [selectorServices, setSelectorServices] = useState<ServiceCatalogItem[]>([]);
  const [selectorLoading, setSelectorLoading] = useState(false);
  const permissions = user?.permisos.planes;
  useDocumentTitle(editing ? "Editar plan" : "Crear plan");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const moduleOptions = await getPlanOptions();
        if (!active) return;
        setOptions(moduleOptions);
        if (editing) {
          const plan = await getPlan(Number(id));
          if (!active) return;
          setForm({
            name: plan.name, description: plan.description, base_price: plan.base_price,
            initial_payment: plan.initial_payment, allow_financing: plan.allow_financing,
            available_all_branches: plan.available_all_branches,
            available_branch_ids: plan.availability.branches.map((branch) => branch.id), items: [],
          });
          setSelected(plan.items.map((item) => ({ service: item.service, quantity: item.quantity, notes: item.notes })));
        }
      } catch (caught) {
        setErrors({ form: caught instanceof ApiError ? caught.message : "No fue posible preparar el formulario." });
      } finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [editing, id]);

  useEffect(() => {
    if (!selectorOpen) return;
    const timer = window.setTimeout(async () => {
      setSelectorLoading(true);
      try { const result = await listServices({ search: selectorSearch, is_active: "true", page_size: 50, organization: form.organization || undefined }); setSelectorServices(result.results); }
      catch { setSelectorServices([]); }
      finally { setSelectorLoading(false); }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [selectorOpen, selectorSearch, form.organization]);

  const estimatedCostCents = useMemo(() => selected.reduce((total, item) => {
    const costCents = Math.round(Number.parseFloat(item.service.estimated_cost ?? "0") * 100);
    const quantity = Number.parseFloat(item.quantity || "0");
    return total + Math.round(costCents * (Number.isFinite(quantity) ? quantity : 0));
  }, 0), [selected]);
  const priceCents = Math.round(Number.parseFloat(form.base_price || "0") * 100) || 0;
  const marginCents = priceCents - estimatedCostCents;
  const allowedBranches = options?.branches.filter((branch) => !form.organization || branch.organization_id === Number(form.organization)) ?? [];

  function update<K extends keyof FuneralPlanPayload>(key: K, value: FuneralPlanPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: "" }));
  }
  function addService(service: ServiceCatalogItem) {
    if (selected.some((item) => item.service.id === service.id)) return;
    setSelected((current) => [...current, { service, quantity: "1.00", notes: "" }]);
    setSelectorOpen(false); setSelectorSearch(""); setErrors((current) => ({ ...current, items: "" }));
  }
  function updateItem(index: number, field: "quantity" | "notes", value: string) {
    setSelected((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item));
  }
  function toggleBranch(branchId: number) {
    update("available_branch_ids", form.available_branch_ids.includes(branchId) ? form.available_branch_ids.filter((id) => id !== branchId) : [...form.available_branch_ids, branchId]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const local: Record<string, string> = {};
    if (!form.name.trim()) local.name = "Ingresa el nombre del plan.";
    if (!Number.isFinite(Number(form.base_price)) || Number(form.base_price) < 0) local.base_price = "Ingresa un precio válido.";
    if (Number(form.initial_payment) < 0 || Number(form.initial_payment) > Number(form.base_price)) local.initial_payment = "La prima debe estar entre cero y el precio.";
    if (!selected.length) local.items = "Agrega al menos una prestación.";
    if (selected.some((item) => !item.quantity || Number(item.quantity) <= 0)) local.items = "Todas las cantidades deben ser mayores que cero.";
    if (!form.available_all_branches && !form.available_branch_ids.length) local.available_branch_ids = "Selecciona al menos una sucursal.";
    if (Object.keys(local).length) { setErrors(local); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    setSaving(true); setErrors({});
    const payload: FuneralPlanPayload = {
      ...form,
      items: selected.map((item, index) => ({ service_id: item.service.id, quantity: item.quantity, included: true, notes: item.notes, sort_order: index })),
    };
    try {
      const saved = editing ? await updatePlan(Number(id), payload) : await createPlan(payload);
      showToast(editing ? "Plan actualizado." : "Plan funerario creado.");
      navigate(`/planes/${saved.id}`);
    } catch (caught) {
      if (caught instanceof ApiError) setErrors({ ...apiErrors(caught), form: caught.message });
      else setErrors({ form: "No fue posible guardar el plan." });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally { setSaving(false); }
  }

  if (loading) return <div className="module-page"><div className="detail-skeleton detail-skeleton--hero" /><div className="detail-skeleton" /></div>;
  if ((editing && !permissions?.edit) || (!editing && !permissions?.create)) {
    return <div className="module-page detail-error"><Link to="/planes"><ArrowLeft size={16} /> Volver a planes</Link><h2>Acceso restringido</h2><p>Tu rol puede consultar planes, pero no crear ni modificar su configuración.</p></div>;
  }
  return <div className="module-page form-page plan-form-page">
    <header className="form-page__header"><Link to={editing ? `/planes/${id}` : "/planes"}><ArrowLeft size={17} /> Volver a planes</Link><p className="section-kicker">Oferta comercial</p><h2>{editing ? "Editar plan funerario" : "Crear plan funerario"}</h2><p>Configura el producto que la funeraria ofrecerá a sus clientes.</p></header>
    {errors.form && <div className="module-error" role="alert"><span>{errors.form}</span></div>}
    <form className="customer-form" onSubmit={submit}>
      <PlanSection title="Información general" description="Nombre y explicación comercial del plan."><Field label="Nombre" error={errors.name} required><input value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="Ej. Plan Familiar" /></Field>{permissions?.global_access && options && <Field label="Organización" error={errors.organization} required><select value={form.organization ?? ""} onChange={(e) => update("organization", e.target.value ? Number(e.target.value) : "")}><option value="">Seleccionar…</option>{options.organizations.map((org) => <option value={org.id} key={org.id}>{org.name}</option>)}</select></Field>}<Field label="Descripción" wide><textarea rows={4} value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Describe a quién está dirigido y su alcance." /></Field></PlanSection>
      <PlanSection title="Precio" description="Valores sugeridos del catálogo; el contrato futuro guardará su propio snapshot."><Field label="Precio del plan" error={errors.base_price} required><div className="money-input"><span>L</span><input type="number" min="0" step="0.01" value={form.base_price} onChange={(e) => update("base_price", e.target.value)} /></div></Field><Field label="Prima sugerida" error={errors.initial_payment} required><div className="money-input"><span>L</span><input type="number" min="0" step="0.01" value={form.initial_payment} onChange={(e) => update("initial_payment", e.target.value)} /></div></Field><label className="check-card form-field--wide"><input type="checkbox" checked={form.allow_financing} onChange={(e) => update("allow_financing", e.target.checked)} /><span><strong>Permite financiamiento</strong><small>La modalidad definitiva se establecerá en el contrato futuro.</small></span></label></PlanSection>
      <section className="form-section plan-items-section"><header><h3>Prestaciones incluidas</h3><p>Agrega servicios del catálogo y define cantidades.</p></header><div className="plan-items-editor"><div className="plan-items-editor__top"><span>{selected.length} {selected.length === 1 ? "prestación" : "prestaciones"}</span><button className="secondary-button" type="button" onClick={() => setSelectorOpen(true)}><Plus size={16} /> Agregar prestación</button></div>{errors.items && <div className="inline-error">{errors.items}</div>}{selected.length === 0 ? <div className="compact-empty"><p>Aún no has agregado prestaciones.</p><button type="button" onClick={() => setSelectorOpen(true)}>Buscar en el catálogo</button></div> : <div className="plan-item-list">{selected.map((item, index) => <article className="plan-item-editor" key={item.service.id}><span className="plan-item-editor__order">{index + 1}</span><div className="plan-item-editor__service"><strong>{item.service.name}</strong><small>{item.service.code} · {item.service.unit_label}</small>{!item.service.is_active && <em>Servicio actualmente inactivo</em>}</div><label><span>Cantidad</span><input type="number" min="0.01" step="0.01" value={item.quantity} onChange={(e) => updateItem(index, "quantity", e.target.value)} /></label><label className="plan-item-editor__notes"><span>Notas</span><input value={item.notes} onChange={(e) => updateItem(index, "notes", e.target.value)} placeholder="Opcional" /></label><button className="icon-button danger-text" type="button" onClick={() => setSelected((current) => current.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Quitar ${item.service.name}`}><Trash2 size={17} /></button></article>)}</div>}</div></section>
      {permissions?.view_costs && <section className="estimate-panel"><header><Calculator size={19} /><div><strong>Análisis estimado</strong><small>Referencia comercial, no utilidad contable real.</small></div></header><div><span><small>Precio de venta</small><strong>{formatCurrency(priceCents / 100)}</strong></span><span><small>Costo estimado</small><strong>{formatCurrency(estimatedCostCents / 100)}</strong></span><span className={marginCents < 0 ? "negative-margin" : ""}><small>Margen estimado</small><strong>{formatCurrency(marginCents / 100)}</strong></span><span><small>Margen estimado %</small><strong>{priceCents > 0 ? `${((marginCents / priceCents) * 100).toFixed(2)}%` : "—"}</strong></span></div></section>}
      <PlanSection title="Disponibilidad" description="Define en qué sucursales podrá ofrecerse el plan."><label className="availability-choice form-field--wide"><input type="radio" name="availability" checked={form.available_all_branches} onChange={() => update("available_all_branches", true)} /><span><strong>Todas las sucursales</strong><small>Disponible en cualquier sucursal actual o futura de la organización.</small></span></label><label className="availability-choice form-field--wide"><input type="radio" name="availability" checked={!form.available_all_branches} onChange={() => update("available_all_branches", false)} /><span><strong>Sucursales seleccionadas</strong><small>Limita la oferta a ubicaciones específicas.</small></span></label>{!form.available_all_branches && <div className="branch-picker form-field--wide">{allowedBranches.map((branch) => <label key={branch.id}><input type="checkbox" checked={form.available_branch_ids.includes(branch.id)} onChange={() => toggleBranch(branch.id)} /><span><strong>{branch.name}</strong><small>{branch.code}</small></span>{form.available_branch_ids.includes(branch.id) && <Check size={16} />}</label>)}{!allowedBranches.length && <p>No hay sucursales disponibles.</p>}{errors.available_branch_ids && <small className="field-error">{errors.available_branch_ids}</small>}</div>}</PlanSection>
      <footer className="form-actions"><Link className="secondary-button" to={editing ? `/planes/${id}` : "/planes"}>Cancelar</Link><button className="primary-action" type="submit" disabled={saving}>{saving ? <><span className="button-spinner" /> Guardando…</> : <><Save size={17} /> {editing ? "Guardar cambios" : "Crear plan"}</>}</button></footer>
    </form>
    <Modal open={selectorOpen} onClose={() => setSelectorOpen(false)} title="Agregar prestación" description="Busca servicios activos del catálogo y agrégalos al plan."><div className="service-selector"><label className="search-control"><Search size={18} /><input autoFocus value={selectorSearch} onChange={(e) => setSelectorSearch(e.target.value)} placeholder="Buscar servicio…" />{selectorSearch && <button type="button" onClick={() => setSelectorSearch("")}><X size={16} /></button>}</label>{selectorLoading ? <div className="selector-loading"><span className="button-spinner" /> Cargando catálogo…</div> : selectorServices.length === 0 ? <div className="compact-empty"><p>No encontramos servicios activos.</p></div> : <div className="selector-results">{selectorServices.map((service) => { const already = selected.some((item) => item.service.id === service.id); return <button type="button" key={service.id} disabled={already} onClick={() => addService(service)}><span><strong>{service.name}</strong><small>{service.code} · {service.category_label} · {service.unit_label}</small></span>{already ? <em>Agregado</em> : <Plus size={17} />}</button>; })}</div>}</div></Modal>
  </div>;
}

function PlanSection({ title, description, children }: { title: string; description: string; children: ReactNode }) { return <section className="form-section"><header><h3>{title}</h3><p>{description}</p></header><div className="form-grid">{children}</div></section>; }
function Field({ label, error, required, wide, children }: { label: string; error?: string; required?: boolean; wide?: boolean; children: ReactNode }) { return <label className={`form-field ${wide ? "form-field--wide" : ""} ${error ? "form-field--error" : ""}`}><span>{label}{required && " *"}</span>{children}{error && <small className="field-error">{error}</small>}</label>; }
