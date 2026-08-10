import { CircleAlert, Download, ReceiptText, Search, WalletCards } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { Pagination } from "../components/Pagination";
import { useToast } from "../contexts/ToastContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { downloadReceiptPdf, getPaymentOptions, listPayments } from "../services/paymentService";
import type { PaginatedPayments, PaymentOptions } from "../types/payment";
import { formatCurrency, formatDateTime } from "../utils/format";

const emptyData: PaginatedPayments = {
  count: 0, page: 1, page_size: 20, total_pages: 0, next: null, previous: null, total_confirmed: "0.00", results: [],
};

export function PaymentsPage() {
  useDocumentTitle("Pagos");
  const { showToast } = useToast();
  const [options, setOptions] = useState<PaymentOptions | null>(null);
  const [data, setData] = useState<PaginatedPayments>(emptyData);
  const [filters, setFilters] = useState({
    search: "", status: "", preset: "", branch: "", payment_method: "", payment_type: "",
    received_by: "", date_from: "", date_to: "", ordering: "-payment_date", page: 1,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await listPayments(filters)); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "No fue posible cargar los pagos."); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { getPaymentOptions().then(setOptions).catch(() => setError("No fue posible cargar las opciones.")); }, []);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer); }, [load]);
  const update = (field: string, value: string | number) => setFilters((current) => ({ ...current, [field]: value, page: field === "page" ? Number(value) : 1 }));

  async function download(paymentId: number, receiptNumber: string) {
    setDownloading(paymentId);
    try {
      const blob = await downloadReceiptPdf(paymentId); const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = `Recibo_${receiptNumber}.pdf`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (caught) { showToast(caught instanceof ApiError ? caught.message : "No fue posible descargar el recibo.", "error"); }
    finally { setDownloading(null); }
  }

  return <div className="module-page payments-page">
    <header className="module-heading"><div><p className="section-kicker">Cobros documentados</p><h2>Pagos y recibos</h2><p>Consulta centralizada del dinero recibido, su contrato y el comprobante emitido.</p></div></header>
    <section className="payment-global-metric"><span><WalletCards size={21} /></span><div><small>Total confirmado con los filtros actuales</small><strong>{formatCurrency(data.total_confirmed ?? "0.00")}</strong><p>{data.count} registro{data.count === 1 ? "" : "s"} encontrado{data.count === 1 ? "" : "s"}</p></div></section>
    <section className="filter-panel installment-filters payment-filters">
      <label className="search-field"><Search size={17} /><input value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Recibo, pago, contrato, cliente o referencia" /></label>
      <select value={filters.status} onChange={(e) => update("status", e.target.value)} aria-label="Estado"><option value="">Todos los estados</option>{options?.statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.preset} onChange={(e) => update("preset", e.target.value)} aria-label="Periodo"><option value="">Cualquier periodo</option><option value="today">Hoy</option><option value="week">Esta semana</option><option value="month">Este mes</option></select>
      <select value={filters.branch} onChange={(e) => update("branch", e.target.value)} aria-label="Sucursal"><option value="">Todas las sucursales</option>{options?.branches.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select value={filters.payment_method} onChange={(e) => update("payment_method", e.target.value)} aria-label="Método"><option value="">Todos los métodos</option>{options?.payment_methods.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.payment_type} onChange={(e) => update("payment_type", e.target.value)} aria-label="Tipo"><option value="">Todos los tipos</option>{options?.payment_types.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      <select value={filters.received_by} onChange={(e) => update("received_by", e.target.value)} aria-label="Receptor"><option value="">Todos los receptores</option>{options?.receivers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <label><span>Desde</span><input type="date" value={filters.date_from} onChange={(e) => update("date_from", e.target.value)} /></label>
      <label><span>Hasta</span><input type="date" value={filters.date_to} onChange={(e) => update("date_to", e.target.value)} /></label>
    </section>
    {error && <div className="inline-error"><CircleAlert size={17} />{error}<button onClick={() => void load()}>Reintentar</button></div>}
    <section className="data-card payment-global-card">
      {loading ? <div className="table-loading">Cargando pagos…</div> : !data.results.length ? <div className="empty-state"><ReceiptText size={30} /><h3>No hay pagos con estos filtros</h3><p>Ajusta la búsqueda o registra un pago desde un contrato activo.</p></div> : <>
        <div className="table-scroll"><table className="data-table payment-global-table"><thead><tr><th>Fecha</th><th>Recibo / pago</th><th>Cliente / contrato</th><th>Monto</th><th>Método</th><th>Recibido por</th><th>Sucursal</th><th>Estado</th><th>Recibo</th></tr></thead><tbody>{data.results.map((payment) => <tr key={payment.id}><td>{formatDateTime(payment.payment_date)}</td><td><strong>{payment.receipt.receipt_number}</strong><small>{payment.payment_number}</small></td><td><strong>{payment.customer_name}</strong><small><Link to={`/contratos/${payment.contract}`}>{payment.contract_number}</Link> · {payment.customer_code}</small></td><td className="payment-amount-cell">{formatCurrency(payment.amount)}</td><td>{payment.payment_method_label}<small>{payment.reference}</small></td><td>{payment.received_by.name}</td><td>{payment.branch_name}</td><td><span className={`payment-status payment-status--${payment.status}`}>{payment.status_label}</span></td><td><button className="table-icon-action" title="Descargar PDF" disabled={downloading === payment.id} onClick={() => void download(payment.id, payment.receipt.receipt_number)}><Download size={15} /></button></td></tr>)}</tbody></table></div>
        <Pagination page={data.page} totalPages={data.total_pages} hasNext={Boolean(data.next)} hasPrevious={Boolean(data.previous)} onChange={(page) => update("page", page)} />
      </>}
    </section>
  </div>;
}
