export function formatDate(value?: string | null): string {
  if (!value) return "No registrado";
  return new Intl.DateTimeFormat("es-HN", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}
export function formatDateTime(value?: string | null): string {
  if (!value) return "No registrado";
  return new Intl.DateTimeFormat("es-HN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function displayValue(value?: string | null): string {
  return value?.trim() || "No registrado";
}

export function formatCurrency(value?: string | number | null): string {
  if (value === null || value === undefined || value === "") return "L 0.00";
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return "L 0.00";
  return new Intl.NumberFormat("es-HN", {
    style: "currency",
    currency: "HNL",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
  }).format(parsed);
}
