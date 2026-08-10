import {
  Activity, ArrowLeft, Building2, CheckCircle2, Clock3, Edit3, HeartHandshake,
  History, MapPin, Phone, Plus, Star, UserRound, UsersRound, WalletCards,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { BeneficiaryModal } from "../components/customers/BeneficiaryModal";
import { ContactModal } from "../components/customers/ContactModal";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { changeCustomerStatus, getCustomer, getCustomerOptions, updateBeneficiary, updateContact } from "../services/customerService";
import type { Beneficiary, CustomerContact, CustomerDetail, CustomerModuleOptions } from "../types/customer";
import { displayValue, formatCurrency, formatDate, formatDateTime } from "../utils/format";

type DetailTab = "summary" | "beneficiaries" | "contacts" | "history";
type StatusTarget = { kind: "customer" | "beneficiary" | "contact"; id: number; name: string; active: boolean };

export function CustomerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [options, setOptions] = useState<CustomerModuleOptions | null>(null);
  const [tab, setTab] = useState<DetailTab>("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [beneficiaryModal, setBeneficiaryModal] = useState(false);
  const [editingBeneficiary, setEditingBeneficiary] = useState<Beneficiary | null>(null);
  const [contactModal, setContactModal] = useState(false);
  const [editingContact, setEditingContact] = useState<CustomerContact | null>(null);
  const [statusTarget, setStatusTarget] = useState<StatusTarget | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useDocumentTitle(customer?.full_name ?? "Ficha del cliente");
  const permissions = user?.permisos.clientes;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [detail, moduleOptions] = await Promise.all([getCustomer(Number(id)), getCustomerOptions()]);
      setCustomer(detail);
      setOptions(moduleOptions);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible cargar la ficha del cliente.");
    } finally { setLoading(false); }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  function beneficiarySaved(message: string) {
    setBeneficiaryModal(false);
    setEditingBeneficiary(null);
    showToast(message);
    void load();
  }

  function contactSaved(message: string) {
    setContactModal(false);
    setEditingContact(null);
    showToast(message);
    void load();
  }

  async function confirmStatus() {
    if (!statusTarget || !customer) return;
    setActionLoading(true);
    try {
      if (statusTarget.kind === "customer") await changeCustomerStatus(customer.id, !statusTarget.active);
      if (statusTarget.kind === "beneficiary") await updateBeneficiary(customer.id, statusTarget.id, { is_active: !statusTarget.active });
      if (statusTarget.kind === "contact") await updateContact(customer.id, statusTarget.id, { is_active: !statusTarget.active });
      const subject = statusTarget.kind === "customer" ? "Cliente" : statusTarget.kind === "beneficiary" ? "Beneficiario" : "Contacto";
      showToast(`${subject} ${statusTarget.active ? "inactivado" : "reactivado"}.`);
      setStatusTarget(null);
      await load();
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "No fue posible cambiar el estado.", "error");
    } finally { setActionLoading(false); }
  }

  async function markPrimary(contact: CustomerContact) {
    if (!customer || contact.is_primary) return;
    setActionLoading(true);
    try {
      await updateContact(customer.id, contact.id, { is_primary: true, is_active: true });
      showToast("Contacto principal actualizado.");
      await load();
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "No fue posible seleccionar el contacto principal.", "error");
    } finally { setActionLoading(false); }
  }

  if (loading) return <div className="detail-loading"><div className="detail-skeleton detail-skeleton--hero" /><div className="detail-skeleton" /><div className="detail-skeleton" /><span className="sr-only">Cargando ficha del cliente</span></div>;
  if (error || !customer) return <div className="detail-error"><UserRound size={34} /><h2>No pudimos abrir esta ficha</h2><p>{error || "El cliente no está disponible."}</p><div><button className="secondary-button" onClick={() => navigate("/clientes")}>Volver a clientes</button><button className="primary-action" onClick={() => void load()}>Reintentar</button></div></div>;

  const tabs: { id: DetailTab; label: string; count?: number }[] = [
    { id: "summary", label: "Resumen" },
    { id: "beneficiaries", label: "Beneficiarios", count: customer.beneficiaries.length },
    { id: "contacts", label: "Contactos", count: customer.contacts.length },
    { id: "history", label: "Historial", count: customer.activities.length },
  ];

  return (
    <div className="module-page customer-detail-page">
      <Link className="back-link" to="/clientes"><ArrowLeft size={16} /> Volver a clientes</Link>
      <section className="customer-hero">
        <div className="customer-hero__identity"><span className="customer-hero__avatar">{customer.first_name.charAt(0)}{customer.last_name.charAt(0)}</span><div><div className="customer-hero__code"><span>{customer.customer_code}</span><span className={`status-pill status-pill--${customer.is_active ? "active" : "inactive"}`}>{customer.is_active ? "Activo" : "Inactivo"}</span></div><h2>{customer.full_name}</h2><div className="customer-hero__facts"><span><Phone size={15} /> {customer.phone}</span><span><UserRound size={15} /> {customer.identity_number ?? "Identidad no registrada"}</span><span><Building2 size={15} /> {customer.branch?.name ?? "Sin sucursal"}</span></div></div></div>
        <div className="customer-hero__actions">
          {permissions?.edit && <Link className="secondary-button" to={`/clientes/${customer.id}/editar`}><Edit3 size={16} /> Editar cliente</Link>}
          {permissions?.change_status && <button className={customer.is_active ? "danger-outline-button" : "primary-action"} type="button" onClick={() => setStatusTarget({ kind: "customer", id: customer.id, name: customer.full_name, active: customer.is_active })}>{customer.is_active ? "Inactivar" : "Reactivar"}</button>}
        </div>
      </section>

      <nav className="detail-tabs" aria-label="Secciones del cliente">{tabs.map((item) => <button key={item.id} type="button" className={tab === item.id ? "detail-tab--active" : ""} onClick={() => setTab(item.id)} aria-current={tab === item.id ? "page" : undefined}>{item.label}{item.count !== undefined && <span>{item.count}</span>}</button>)}</nav>

      {tab === "summary" && <div className="summary-layout">
        {user?.permisos.pagos.view_payment && <InfoCard title="Resumen financiero" icon={<WalletCards size={19} />} wide><InfoGrid items={[
          ["Contratos activos", String(customer.financial_summary.active_contracts)],
          ["Saldo total pendiente", formatCurrency(customer.financial_summary.total_balance)],
          ["Último pago", customer.financial_summary.last_payment ? `${formatCurrency(customer.financial_summary.last_payment.amount)} · ${formatDateTime(customer.financial_summary.last_payment.payment_date)}` : "Sin pagos confirmados"],
        ]} /></InfoCard>}
        <InfoCard title="Información personal" icon={<UserRound size={19} />}><InfoGrid items={[
          ["Nombre completo", customer.full_name], ["Identidad", customer.identity_number], ["Nacimiento", customer.birth_date ? formatDate(customer.birth_date) : null],
          ["Sexo", customer.gender_label], ["Estado civil", customer.marital_status_label], ["Ocupación", customer.occupation],
        ]} /></InfoCard>
        <InfoCard title="Contacto" icon={<Phone size={19} />}><InfoGrid items={[["Teléfono", customer.phone], ["Teléfono alternativo", customer.secondary_phone], ["Correo electrónico", customer.email]]} /></InfoCard>
        <InfoCard title="Dirección" icon={<MapPin size={19} />}><InfoGrid items={[["Departamento", customer.department_label], ["Ciudad o municipio", customer.city], ["País", customer.country], ["Dirección", customer.address]]} /></InfoCard>
        <InfoCard title="Información administrativa" icon={<Building2 size={19} />}><InfoGrid items={[["Organización", customer.organization.name], ["Sucursal", customer.branch?.name], ["Registrado por", customer.created_by.name], ["Fecha de registro", formatDateTime(customer.created_at)], ["Última actualización", formatDateTime(customer.updated_at)]]} /></InfoCard>
        {customer.notes && <InfoCard title="Observaciones" icon={<Activity size={19} />} wide><p className="notes-copy">{customer.notes}</p></InfoCard>}
      </div>}

      {tab === "beneficiaries" && <section className="related-section">
        <header><div><p className="section-kicker">Personas asociadas</p><h3>Beneficiarios</h3><p>No representan contratos; son personas que podrán asociarse a planes futuros.</p></div>{permissions?.manage_beneficiaries && <button className="primary-action" type="button" onClick={() => { setEditingBeneficiary(null); setBeneficiaryModal(true); }}><Plus size={17} /> Agregar beneficiario</button>}</header>
        {customer.beneficiaries.length === 0 ? <EmptyRelated icon={<HeartHandshake size={28} />} title="Este cliente todavía no tiene beneficiarios registrados." action={permissions?.manage_beneficiaries ? "Agregar beneficiario" : undefined} onAction={() => setBeneficiaryModal(true)} /> : <div className="related-list">{customer.beneficiaries.map((item) => <article className="related-card" key={item.id}><span className="related-card__avatar">{item.full_name.charAt(0)}</span><div className="related-card__main"><div><h4>{item.full_name}</h4>{item.is_customer && <span className="primary-label"><Star size={12} /> Titular</span>}</div><p>{item.relationship_label}{item.age !== null ? ` · ${item.age} años` : ""}</p><div><span>{item.identity_number ?? "Sin identidad"}</span><span>{item.phone || "Sin teléfono"}</span></div></div><span className={`status-dot status-dot--${item.is_active ? "active" : "inactive"}`}>{item.is_active ? "Activo" : "Inactivo"}</span>{permissions?.manage_beneficiaries && <div className="related-card__actions"><button type="button" onClick={() => { setEditingBeneficiary(item); setBeneficiaryModal(true); }}>Editar</button><button type="button" className={item.is_active ? "danger-text" : ""} onClick={() => setStatusTarget({ kind: "beneficiary", id: item.id, name: item.full_name, active: item.is_active })}>{item.is_active ? "Inactivar" : "Reactivar"}</button></div>}</article>)}</div>}
      </section>}

      {tab === "contacts" && <section className="related-section">
        <header><div><p className="section-kicker">Red de referencia</p><h3>Contactos</h3><p>Personas mediante las cuales puede localizarse al cliente.</p></div>{permissions?.manage_contacts && <button className="primary-action" type="button" onClick={() => { setEditingContact(null); setContactModal(true); }}><Plus size={17} /> Agregar contacto</button>}</header>
        {customer.contacts.length === 0 ? <EmptyRelated icon={<UsersRound size={28} />} title="No hay contactos adicionales." action={permissions?.manage_contacts ? "Agregar contacto" : undefined} onAction={() => setContactModal(true)} /> : <div className="related-list">{customer.contacts.map((item) => <article className="related-card" key={item.id}><span className="related-card__avatar related-card__avatar--contact">{item.name.charAt(0)}</span><div className="related-card__main"><div><h4>{item.name}</h4>{item.is_primary && item.is_active && <span className="primary-label"><Star size={12} /> Principal</span>}</div><p>{item.relationship || "Relación no indicada"}</p><div><span>{item.phone}</span>{item.secondary_phone && <span>{item.secondary_phone}</span>}</div></div><span className={`status-dot status-dot--${item.is_active ? "active" : "inactive"}`}>{item.is_active ? "Activo" : "Inactivo"}</span>{permissions?.manage_contacts && <div className="related-card__actions">{!item.is_primary && item.is_active && <button type="button" onClick={() => void markPrimary(item)} disabled={actionLoading}>Marcar principal</button>}<button type="button" onClick={() => { setEditingContact(item); setContactModal(true); }}>Editar</button><button type="button" className={item.is_active ? "danger-text" : ""} onClick={() => setStatusTarget({ kind: "contact", id: item.id, name: item.name, active: item.is_active })}>{item.is_active ? "Inactivar" : "Reactivar"}</button></div>}</article>)}</div>}
      </section>}

      {tab === "history" && <section className="history-section"><header><div><p className="section-kicker">Trazabilidad administrativa</p><h3>Historial del cliente</h3><p>Cambios realizados únicamente dentro de este módulo.</p></div><History size={22} /></header><ol className="activity-timeline">{customer.activities.map((item) => <li key={item.id}><span className="activity-timeline__dot"><CheckCircle2 size={15} /></span><div><strong>{item.action_label}</strong><p>{item.description}</p><small><Clock3 size={13} /> {formatDateTime(item.created_at)}{item.user ? ` · ${item.user.name}` : ""}</small></div></li>)}</ol></section>}

      <BeneficiaryModal open={beneficiaryModal} customerId={customer.id} beneficiary={editingBeneficiary} relationships={options?.relationships ?? []} onClose={() => { setBeneficiaryModal(false); setEditingBeneficiary(null); }} onSaved={beneficiarySaved} />
      <ContactModal open={contactModal} customerId={customer.id} contact={editingContact} onClose={() => { setContactModal(false); setEditingContact(null); }} onSaved={contactSaved} />
      <ConfirmModal open={Boolean(statusTarget)} title={`${statusTarget?.active ? "Inactivar" : "Reactivar"} ${statusTarget?.kind === "customer" ? "cliente" : statusTarget?.kind === "beneficiary" ? "beneficiario" : "contacto"}`} description={statusTarget?.active ? `¿Deseas inactivar a ${statusTarget.name}? El registro permanecerá en el historial y podrá reactivarse posteriormente.` : `¿Deseas reactivar a ${statusTarget?.name}?`} confirmLabel={statusTarget?.active ? "Sí, inactivar" : "Sí, reactivar"} tone={statusTarget?.active ? "danger" : "primary"} loading={actionLoading} onConfirm={() => void confirmStatus()} onCancel={() => !actionLoading && setStatusTarget(null)} />
    </div>
  );
}

function InfoCard({ title, icon, children, wide }: { title: string; icon: ReactNode; children: ReactNode; wide?: boolean }) {
  return <section className={`info-card ${wide ? "info-card--wide" : ""}`}><header><span>{icon}</span><h3>{title}</h3></header>{children}</section>;
}

function InfoGrid({ items }: { items: Array<[string, string | null | undefined]> }) {
  return <dl className="info-grid">{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{displayValue(value)}</dd></div>)}</dl>;
}

function EmptyRelated({ icon, title, action, onAction }: { icon: ReactNode; title: string; action?: string; onAction: () => void }) {
  return <div className="empty-related"><span>{icon}</span><h4>{title}</h4>{action && <button type="button" className="secondary-button" onClick={onAction}><Plus size={16} /> {action}</button>}</div>;
}
