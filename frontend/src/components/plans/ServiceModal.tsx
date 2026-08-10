import { Save } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { createService, updateService } from "../../services/planService";
import type { PlanModuleOptions, ServiceCatalogItem, ServicePayload } from "../../types/plan";
import { Modal } from "../Modal";

interface Props {
  open: boolean;
  service: ServiceCatalogItem | null;
  options: PlanModuleOptions;
  onClose: () => void;
  onSaved: (message: string) => void;
}

const emptyService: ServicePayload = {
  code: "", name: "", description: "", category: "other", unit: "service",
  estimated_cost: "0.00", default_sale_price: "0.00",
};

function extractErrors(error: ApiError): Record<string, string> {
  return Object.fromEntries(Object.entries(error.errors).map(([key, value]) => [
    key,
    Array.isArray(value) ? String(value[0]) : typeof value === "string" ? value : error.message,
  ]));
}

export function ServiceModal({ open, service, options, onClose, onSaved }: Props) {
  const [form, setForm] = useState<ServicePayload>(emptyService);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(service ? {
      code: service.code, name: service.name, description: service.description,
      category: service.category, unit: service.unit, estimated_cost: service.estimated_cost ?? "0.00",
      default_sale_price: service.default_sale_price,
    } : { ...emptyService });
    setErrors({});
  }, [open, service]);

  function update<K extends keyof ServicePayload>(key: K, value: ServicePayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: "" }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const localErrors: Record<string, string> = {};
    if (!form.code.trim()) localErrors.code = "Ingresa un código.";
    if (!form.name.trim()) localErrors.name = "Ingresa un nombre.";
    if (Number(form.estimated_cost) < 0) localErrors.estimated_cost = "El costo no puede ser negativo.";
    if (Number(form.default_sale_price) < 0) localErrors.default_sale_price = "El precio no puede ser negativo.";
    if (Object.keys(localErrors).length) { setErrors(localErrors); return; }
    setSaving(true);
    try {
      if (service) await updateService(service.id, form); else await createService(form);
      onSaved(service ? "Servicio actualizado." : "Servicio agregado al catálogo.");
    } catch (caught) {
      if (caught instanceof ApiError) setErrors({ ...extractErrors(caught), form: caught.message });
      else setErrors({ form: "No fue posible guardar el servicio." });
    } finally { setSaving(false); }
  }

  return (
    <Modal open={open} onClose={() => !saving && onClose()} title={service ? "Editar servicio" : "Agregar servicio"} description="Define una prestación comercial reutilizable en los planes.">
      <form className="service-form" onSubmit={submit}>
        <div className="modal-section-title"><span>Información</span><p>Identificación dentro del catálogo.</p></div>
        <div className="related-form__grid">
          <label className="related-field"><span>Código *</span><input value={form.code} onChange={(e) => update("code", e.target.value.toUpperCase())} placeholder="EJ. TRA-001" />{errors.code && <small className="field-error">{errors.code}</small>}</label>
          <label className="related-field"><span>Nombre *</span><input value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="Traslado local" />{errors.name && <small className="field-error">{errors.name}</small>}</label>
          <label className="related-field"><span>Categoría *</span><select value={form.category} onChange={(e) => update("category", e.target.value)}>{options.categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className="related-field"><span>Unidad *</span><select value={form.unit} onChange={(e) => update("unit", e.target.value)}>{options.units.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className="related-field related-field--wide"><span>Descripción</span><textarea rows={3} value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Describe el alcance comercial de esta prestación." /></label>
        </div>
        <div className="modal-section-title"><span>Configuración</span><p>Referencias monetarias en lempiras.</p></div>
        <div className="related-form__grid">
          <label className="related-field"><span>Costo estimado *</span><div className="money-input"><span>L</span><input type="number" min="0" step="0.01" value={form.estimated_cost} onChange={(e) => update("estimated_cost", e.target.value)} /></div>{errors.estimated_cost && <small className="field-error">{errors.estimated_cost}</small>}</label>
          <label className="related-field"><span>Precio individual sugerido *</span><div className="money-input"><span>L</span><input type="number" min="0" step="0.01" value={form.default_sale_price} onChange={(e) => update("default_sale_price", e.target.value)} /></div>{errors.default_sale_price && <small className="field-error">{errors.default_sale_price}</small>}</label>
        </div>
        {errors.form && <div className="inline-error" role="alert">{errors.form}</div>}
        <div className="modal-actions"><button type="button" className="secondary-button" disabled={saving} onClick={onClose}>Cancelar</button><button className="primary-action" type="submit" disabled={saving}>{saving ? <><span className="button-spinner" /> Guardando…</> : <><Save size={16} /> Guardar servicio</>}</button></div>
      </form>
    </Modal>
  );
}
