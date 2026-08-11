import { AlertTriangle, CalendarCheck, HandCoins, History, Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getContractCollection } from "../../services/collectionService";
import type { CollectionDetail } from "../../types/collection";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/format";

export function ContractCollectionTab({ contractId }: { contractId: number }) {
  const [data, setData] = useState<CollectionDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getContractCollection(contractId).then(setData).catch((caught) => setError(caught instanceof ApiError ? caught.message : "No fue posible cargar cobranza."));
  }, [contractId]);
  if (error) return <div className="inline-error"><AlertTriangle size={17} />{error}</div>;
  if (!data) return <div className="table-loading">Calculando cobranza…</div>;
  const row = data.portfolio;
  return <div className="contract-collection-tab">
    <section className="detail-balance"><div><small>Saldo pendiente</small><strong>{formatCurrency(row.balance)}</strong></div><div><small>Monto vencido</small><strong>{formatCurrency(row.overdue_amount)}</strong></div><div><small>Cuotas vencidas</small><strong>{row.overdue_installments}</strong></div><div><small>Días de mora</small><strong>{row.days_overdue}</strong></div></section>
    <section className="collection-contract-facts"><div><CalendarCheck size={16} /><span><small>Próximo vencimiento</small><strong>{formatDate(row.next_due_date)}</strong></span></div><div><HandCoins size={16} /><span><small>Último pago</small><strong>{row.last_payment ? `${formatCurrency(row.last_payment.amount)} · ${formatDateTime(row.last_payment.date)}` : "Sin pagos"}</strong></span></div><div><Phone size={16} /><span><small>Contacto</small><strong><a href={`tel:${row.phone}`}>{row.phone || "No registrado"}</a></strong></span></div></section>
    <section className="collection-timeline"><header className="contract-collection-heading"><div><p className="section-kicker">Trazabilidad</p><h3>Historial de cobranza</h3></div><Link className="secondary-button" to="/cartera">Abrir cartera</Link></header>{data.actions.length ? data.actions.map((item) => <article key={item.id}><span><History size={15} /></span><div><strong>{item.action_type_label} · {item.outcome_label}</strong><p>{item.notes}</p><small>{formatDateTime(item.contact_date)} · {item.created_by_name}</small>{item.next_follow_up_date && <em>Seguimiento: {formatDate(item.next_follow_up_date)}</em>}</div></article>) : <p className="empty-copy">Aún no se han registrado gestiones para este contrato.</p>}</section>
  </div>;
}

