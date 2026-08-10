import { Save } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { createBeneficiary, updateBeneficiary } from "../../services/customerService";
import type { Beneficiary, BeneficiaryPayload, SelectOption } from "../../types/customer";
import { Modal } from "../Modal";

const emptyBeneficiary: BeneficiaryPayload = {
  is_customer: false,
  first_name: "",
  middle_name: "",
  last_name: "",
  second_last_name: "",
  identity_number: null,
  birth_date: null,
  relationship: "relative",
  phone: "",
  address: "",
  notes: "",
  is_active: true,
};

interface BeneficiaryModalProps {
  open: boolean;
  customerId: number;
  beneficiary: Beneficiary | null;
  relationships: SelectOption[];
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function BeneficiaryModal({ open, customerId, beneficiary, relationships, onClose, onSaved }: BeneficiaryModalProps) {
  const [form, setForm] = useState<BeneficiaryPayload>(emptyBeneficiary);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!open) return;
    setForm(beneficiary ? {
      is_customer: beneficiary.is_customer,
      first_name: beneficiary.first_name,
      middle_name: beneficiary.middle_name,
      last_name: beneficiary.last_name,
      second_last_name: beneficiary.second_last_name,
      identity_number: beneficiary.identity_number,
      birth_date: beneficiary.birth_date,
      relationship: beneficiary.relationship,
      phone: beneficiary.phone,
      address: beneficiary.address,
      notes: beneficiary.notes,
      is_active: beneficiary.is_active,
    } : emptyBeneficiary);
    setErrors({});
    setMessage("");
  }, [open, beneficiary]);

  function errorFor(field: string) {
    const value = errors[field];
    return Array.isArray(value) ? value.map(String).join(" ") : typeof value === "string" ? value : "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.is_customer && (!form.first_name.trim() || !form.last_name.trim())) {
      setErrors({ first_name: ["Nombre y apellido son obligatorios."] });
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const payload = {
        ...form,
        birth_date: form.birth_date && /^\d{4}-\d{2}-\d{2}$/.test(form.birth_date) ? form.birth_date : null,
      };
      if (beneficiary) await updateBeneficiary(customerId, beneficiary.id, payload);
      else await createBeneficiary(customerId, payload);
      onSaved(beneficiary ? "Beneficiario actualizado." : "Beneficiario agregado.");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setErrors(caught.errors);
        setMessage(caught.message);
      } else setMessage("No fue posible guardar el beneficiario.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={beneficiary ? "Editar beneficiario" : "Agregar beneficiario"} description="Persona que podrá asociarse posteriormente con un plan funerario.">
      <form className="related-form" onSubmit={submit} noValidate>
        <label className="check-card"><input type="checkbox" checked={form.is_customer} onChange={(e) => setForm((current) => ({ ...current, is_customer: e.target.checked, relationship: e.target.checked ? "self" : "relative" }))} /><span><strong>El cliente es el beneficiario titular</strong><small>Se utilizarán sus datos actuales sin duplicarlos.</small></span></label>
        {!form.is_customer && <div className="related-form__grid">
          <RelatedField label="Primer nombre" required error={errorFor("first_name")}><input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></RelatedField>
          <RelatedField label="Segundo nombre"><input value={form.middle_name} onChange={(e) => setForm({ ...form, middle_name: e.target.value })} /></RelatedField>
          <RelatedField label="Primer apellido" required error={errorFor("last_name")}><input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></RelatedField>
          <RelatedField label="Segundo apellido"><input value={form.second_last_name} onChange={(e) => setForm({ ...form, second_last_name: e.target.value })} /></RelatedField>
          <RelatedField label="Parentesco" required><select value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })}>{relationships.filter((item) => item.value !== "self").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></RelatedField>
          <RelatedField label="Identidad" error={errorFor("identity_number")}><input value={form.identity_number ?? ""} onChange={(e) => setForm({ ...form, identity_number: e.target.value })} /></RelatedField>
          <RelatedField label="Nacimiento" error={errorFor("birth_date")}><input type="date" max={new Date().toISOString().slice(0, 10)} value={form.birth_date ?? ""} onChange={(e) => setForm({ ...form, birth_date: e.target.value || null })} /></RelatedField>
          <RelatedField label="Teléfono" error={errorFor("phone")}><input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></RelatedField>
          <RelatedField label="Dirección" wide><textarea rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></RelatedField>
          <RelatedField label="Observaciones" wide><textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></RelatedField>
        </div>}
        {message && <div className="inline-error" role="alert">{message}</div>}
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancelar</button><button type="submit" className="primary-action" disabled={saving}><Save size={16} /> {saving ? "Guardando…" : "Guardar beneficiario"}</button></div>
      </form>
    </Modal>
  );
}

function RelatedField({ label, required, error, wide, children }: { label: string; required?: boolean; error?: string; wide?: boolean; children: ReactNode }) {
  return <label className={`related-field ${wide ? "related-field--wide" : ""} ${error ? "related-field--error" : ""}`}><span>{label}{required && " *"}</span>{children}{error && <small role="alert">{error}</small>}</label>;
}
