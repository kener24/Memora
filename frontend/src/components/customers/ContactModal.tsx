import { Save } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { createContact, updateContact } from "../../services/customerService";
import type { CustomerContact, CustomerContactPayload } from "../../types/customer";
import { Modal } from "../Modal";

const emptyContact: CustomerContactPayload = {
  name: "", relationship: "", phone: "", secondary_phone: "", notes: "", is_primary: false, is_active: true,
};

interface ContactModalProps {
  open: boolean;
  customerId: number;
  contact: CustomerContact | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function ContactModal({ open, customerId, contact, onClose, onSaved }: ContactModalProps) {
  const [form, setForm] = useState<CustomerContactPayload>(emptyContact);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!open) return;
    setForm(contact ? {
      name: contact.name, relationship: contact.relationship, phone: contact.phone,
      secondary_phone: contact.secondary_phone, notes: contact.notes, is_primary: contact.is_primary,
      is_active: contact.is_active,
    } : emptyContact);
    setErrors({});
    setMessage("");
  }, [open, contact]);

  function errorFor(field: string) {
    const value = errors[field];
    return Array.isArray(value) ? value.map(String).join(" ") : typeof value === "string" ? value : "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      setErrors({ name: !form.name.trim() ? ["El nombre es obligatorio."] : undefined, phone: !form.phone.trim() ? ["El teléfono es obligatorio."] : undefined });
      return;
    }
    setSaving(true);
    try {
      if (contact) await updateContact(customerId, contact.id, form);
      else await createContact(customerId, form);
      onSaved(contact ? "Contacto actualizado." : "Contacto agregado.");
    } catch (caught) {
      if (caught instanceof ApiError) { setErrors(caught.errors); setMessage(caught.message); }
      else setMessage("No fue posible guardar el contacto.");
    } finally { setSaving(false); }
  }

  return (
    <Modal open={open} onClose={onClose} title={contact ? "Editar contacto" : "Agregar contacto"} description="Persona de referencia para localizar al cliente.">
      <form className="related-form" onSubmit={submit} noValidate>
        <div className="related-form__grid">
          <RelatedField label="Nombre completo" required error={errorFor("name")} wide><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></RelatedField>
          <RelatedField label="Relación o parentesco"><input value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} /></RelatedField>
          <RelatedField label="Teléfono" required error={errorFor("phone")}><input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></RelatedField>
          <RelatedField label="Teléfono alternativo" error={errorFor("secondary_phone")}><input type="tel" value={form.secondary_phone} onChange={(e) => setForm({ ...form, secondary_phone: e.target.value })} /></RelatedField>
          <RelatedField label="Observaciones" wide><textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></RelatedField>
        </div>
        <label className="check-card"><input type="checkbox" checked={form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} /><span><strong>Contacto principal</strong><small>Al marcarlo, sustituirá al contacto principal actual.</small></span></label>
        {message && <div className="inline-error" role="alert">{message}</div>}
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Cancelar</button><button type="submit" className="primary-action" disabled={saving}><Save size={16} /> {saving ? "Guardando…" : "Guardar contacto"}</button></div>
      </form>
    </Modal>
  );
}

function RelatedField({ label, required, error, wide, children }: { label: string; required?: boolean; error?: string; wide?: boolean; children: ReactNode }) {
  return <label className={`related-field ${wide ? "related-field--wide" : ""} ${error ? "related-field--error" : ""}`}><span>{label}{required && " *"}</span>{children}{error && <small role="alert">{error}</small>}</label>;
}
