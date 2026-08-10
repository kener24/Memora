import { ArrowLeft, Check, CircleAlert, Save, UserPlus } from "lucide-react";
import { cloneElement, type FormEvent, type ReactElement, type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { checkDuplicates, createCustomer, getCustomer, getCustomerOptions, updateCustomer } from "../services/customerService";
import type { CustomerModuleOptions, CustomerPayload, DuplicateMatch } from "../types/customer";

const initialForm: CustomerPayload = {
  branch: "", first_name: "", middle_name: "", last_name: "", second_last_name: "", identity_number: "",
  birth_date: null, gender: "", marital_status: "", phone: "", secondary_phone: "", email: "", address: "",
  city: "", department: "", country: "Honduras", occupation: "", notes: "",
};

function fieldError(errors: Record<string, unknown>, field: string): string {
  const value = errors[field];
  if (Array.isArray(value)) return value.map(String).join(" ");
  return typeof value === "string" ? value : "";
}

export function CustomerFormPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  useDocumentTitle(editing ? "Editar cliente" : "Registrar cliente");
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [form, setForm] = useState<CustomerPayload>(initialForm);
  const [options, setOptions] = useState<CustomerModuleOptions | null>(null);
  const [loading, setLoading] = useState(editing);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, unknown>>({});
  const [pageError, setPageError] = useState("");
  const [duplicates, setDuplicates] = useState<DuplicateMatch[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [moduleOptions, customer] = await Promise.all([
          getCustomerOptions(),
          editing ? getCustomer(Number(id)) : Promise.resolve(null),
        ]);
        setOptions(moduleOptions);
        if (customer) {
          setForm({
            organization: customer.organization.id,
            branch: customer.branch?.id ?? "",
            first_name: customer.first_name,
            middle_name: customer.middle_name,
            last_name: customer.last_name,
            second_last_name: customer.second_last_name,
            identity_number: customer.identity_number ?? "",
            birth_date: customer.birth_date,
            gender: customer.gender,
            marital_status: customer.marital_status,
            phone: customer.phone,
            secondary_phone: customer.secondary_phone,
            email: customer.email,
            address: customer.address,
            city: customer.city,
            department: customer.department,
            country: customer.country || "Honduras",
            occupation: customer.occupation,
            notes: customer.notes,
          });
        }
      } catch (caught) {
        setPageError(caught instanceof ApiError ? caught.message : "No fue posible preparar el formulario.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [editing, id]);

  function updateField<K extends keyof CustomerPayload>(field: K, value: CustomerPayload[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    if (field === "phone" || field === "identity_number") setDuplicates([]);
  }

  function validateLocal(): boolean {
    const next: Record<string, string[]> = {};
    if (!form.first_name.trim()) next.first_name = ["El nombre es obligatorio."];
    if (!form.last_name.trim()) next.last_name = ["El apellido es obligatorio."];
    if (!form.phone.trim()) next.phone = ["El teléfono es obligatorio."];
    if (form.birth_date && form.birth_date > new Date().toISOString().slice(0, 10)) next.birth_date = ["La fecha no puede estar en el futuro."];
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function saveCustomer() {
    setSaving(true);
    setPageError("");
    try {
      const payload = {
        ...form,
        branch: form.branch || null,
        birth_date: form.birth_date && /^\d{4}-\d{2}-\d{2}$/.test(form.birth_date) ? form.birth_date : null,
      };
      const customer = editing ? await updateCustomer(Number(id), payload) : await createCustomer(payload);
      showToast(editing ? "Información actualizada." : "Cliente registrado correctamente.");
      navigate(`/clientes/${customer.id}`, { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        setErrors(caught.errors);
        setPageError(caught.message === "La solicitud contiene datos inválidos." ? "No fue posible guardar el cliente. Revisa los campos indicados." : caught.message);
      } else setPageError("No fue posible guardar el cliente. Inténtalo nuevamente.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!validateLocal()) return;
    if (!editing) {
      setSaving(true);
      try {
        const matches = await checkDuplicates(form.identity_number, form.phone);
        const identityMatch = matches.find((match) => match.same_identity);
        if (identityMatch) {
          setErrors({ identity_number: [`La identidad pertenece a ${identityMatch.customer_code} · ${identityMatch.full_name}.`] });
          return;
        }
        const phoneMatches = matches.filter((match) => match.same_phone);
        if (phoneMatches.length) {
          setDuplicates(phoneMatches);
          return;
        }
      } catch (caught) {
        if (caught instanceof ApiError) setErrors(caught.errors);
        else setPageError("No fue posible comprobar posibles duplicados.");
        return;
      } finally {
        setSaving(false);
      }
    }
    await saveCustomer();
  }

  if (loading) return <div className="form-loading"><span className="spinner" /><p>Cargando información del cliente…</p></div>;

  return (
    <div className="module-page customer-form-page">
      <header className="module-header module-header--compact">
        <div><Link className="back-link" to={editing ? `/clientes/${id}` : "/clientes"}><ArrowLeft size={16} /> Volver</Link><p className="section-kicker">{editing ? "Actualización" : "Nuevo registro"}</p><h2>{editing ? "Editar cliente" : "Registrar cliente"}</h2><p>Los campos marcados con * son obligatorios.</p></div>
        <span className="header-symbol"><UserPlus size={24} /></span>
      </header>

      {pageError && <div className="module-error" role="alert"><CircleAlert size={18} /><span>{pageError}</span></div>}
      <form className="customer-form" onSubmit={handleSubmit} noValidate>
        {options?.permissions.global_access && (
          <FormSection title="Organización" description="Empresa responsable del registro.">
            <FormField label="Organización" required error={fieldError(errors, "organization")}><select value={form.organization ?? ""} onChange={(e) => updateField("organization", Number(e.target.value) || "")}><option value="">Seleccionar organización</option>{options.organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></FormField>
          </FormSection>
        )}
        <FormSection title="Información personal" description="Datos de identificación del cliente.">
          <FormField label="Primer nombre" required error={fieldError(errors, "first_name")}><input value={form.first_name} onChange={(e) => updateField("first_name", e.target.value)} maxLength={80} /></FormField>
          <FormField label="Segundo nombre" error={fieldError(errors, "middle_name")}><input value={form.middle_name} onChange={(e) => updateField("middle_name", e.target.value)} maxLength={80} /></FormField>
          <FormField label="Primer apellido" required error={fieldError(errors, "last_name")}><input value={form.last_name} onChange={(e) => updateField("last_name", e.target.value)} maxLength={80} /></FormField>
          <FormField label="Segundo apellido" error={fieldError(errors, "second_last_name")}><input value={form.second_last_name} onChange={(e) => updateField("second_last_name", e.target.value)} maxLength={80} /></FormField>
          <FormField label="Identidad" hint="Puede escribirse con o sin guiones." error={fieldError(errors, "identity_number")}><input value={form.identity_number} onChange={(e) => updateField("identity_number", e.target.value)} placeholder="0801-1990-12345" /></FormField>
          <FormField label="Fecha de nacimiento" error={fieldError(errors, "birth_date")}><input type="date" max={new Date().toISOString().slice(0, 10)} value={form.birth_date ?? ""} onChange={(e) => updateField("birth_date", e.target.value || null)} /></FormField>
          <FormField label="Sexo" error={fieldError(errors, "gender")}><select value={form.gender} onChange={(e) => updateField("gender", e.target.value)}><option value="">No indicado</option>{options?.genders.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></FormField>
          <FormField label="Estado civil" error={fieldError(errors, "marital_status")}><select value={form.marital_status} onChange={(e) => updateField("marital_status", e.target.value)}><option value="">No indicado</option>{options?.marital_statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></FormField>
          <FormField label="Ocupación" error={fieldError(errors, "occupation")} wide><input value={form.occupation} onChange={(e) => updateField("occupation", e.target.value)} maxLength={120} /></FormField>
        </FormSection>

        <FormSection title="Contacto" description="Canales para comunicarse con el cliente.">
          <FormField label="Teléfono" required error={fieldError(errors, "phone")}><input type="tel" value={form.phone} onChange={(e) => updateField("phone", e.target.value)} placeholder="9876-5432" /></FormField>
          <FormField label="Teléfono alternativo" error={fieldError(errors, "secondary_phone")}><input type="tel" value={form.secondary_phone} onChange={(e) => updateField("secondary_phone", e.target.value)} /></FormField>
          <FormField label="Correo electrónico" error={fieldError(errors, "email")} wide><input type="email" value={form.email} onChange={(e) => updateField("email", e.target.value)} placeholder="cliente@correo.com" /></FormField>
        </FormSection>

        <FormSection title="Ubicación" description="Dirección habitual del cliente.">
          <FormField label="Departamento" error={fieldError(errors, "department")}><select value={form.department} onChange={(e) => updateField("department", e.target.value)}><option value="">Seleccionar</option>{options?.departments.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></FormField>
          <FormField label="Ciudad o municipio" error={fieldError(errors, "city")}><input value={form.city} onChange={(e) => updateField("city", e.target.value)} maxLength={120} /></FormField>
          <FormField label="País" error={fieldError(errors, "country")}><input value={form.country} onChange={(e) => updateField("country", e.target.value)} maxLength={80} /></FormField>
          <FormField label="Dirección" error={fieldError(errors, "address")} wide><textarea rows={3} value={form.address} onChange={(e) => updateField("address", e.target.value)} /></FormField>
        </FormSection>

        <FormSection title="Organización" description="Asignación operativa dentro de la empresa.">
          <FormField label="Sucursal" error={fieldError(errors, "branch")}><select value={form.branch ?? ""} onChange={(e) => updateField("branch", Number(e.target.value) || "")}><option value="">Sin sucursal</option>{options?.branches.filter((branch) => !form.organization || branch.organization_id === Number(form.organization)).map((branch) => <option key={branch.id} value={branch.id}>{branch.name} · {branch.code}</option>)}</select></FormField>
        </FormSection>

        <FormSection title="Otros" description="Información administrativa útil, sin datos financieros.">
          <FormField label="Observaciones" error={fieldError(errors, "notes")} wide><textarea rows={4} value={form.notes} onChange={(e) => updateField("notes", e.target.value)} /></FormField>
        </FormSection>

        {duplicates.length > 0 && <div className="duplicate-warning" role="alert"><CircleAlert size={20} /><div><strong>Existe otro cliente registrado con este teléfono.</strong><p>{duplicates.map((item) => `${item.customer_code} · ${item.full_name}`).join(", ")}. Las personas pueden compartir teléfono; confirma si deseas continuar.</p></div><button type="button" className="primary-action" onClick={() => void saveCustomer()} disabled={saving}><Check size={16} /> Registrar de todos modos</button></div>}

        <footer className="form-actions"><Link className="secondary-button" to={editing ? `/clientes/${id}` : "/clientes"}>Cancelar</Link><button className="primary-action" type="submit" disabled={saving}>{saving ? <><span className="button-spinner" /> Guardando…</> : <><Save size={17} /> {editing ? "Guardar cambios" : "Registrar cliente"}</>}</button></footer>
      </form>
    </div>
  );
}

function FormSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="form-section"><header><h3>{title}</h3><p>{description}</p></header><div className="form-grid">{children}</div></section>;
}

function FormField({ label, required, hint, error, wide, children }: { label: string; required?: boolean; hint?: string; error?: string; wide?: boolean; children: ReactElement<Record<string, unknown>> }) {
  const id = `field-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return <div className={`form-field ${wide ? "form-field--wide" : ""} ${error ? "form-field--error" : ""}`}><label htmlFor={id}>{label}{required && <span> *</span>}</label>{hint && <small>{hint}</small>}{cloneElement(children, { id, "aria-invalid": Boolean(error), "aria-describedby": error ? `${id}-error` : undefined })}{error && <p id={`${id}-error`} role="alert">{error}</p>}</div>;
}
