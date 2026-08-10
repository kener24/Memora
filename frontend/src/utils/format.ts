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
