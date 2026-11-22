/** Display helpers (Spanish / Colombian formats). */

const pesos = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });

/** "9800000" → "$9.800.000" */
export function formatCOP(value: string | number): string {
  return `$${pesos.format(Number(value))}`;
}

/** A price range, or the given placeholder when there is no estimate. */
export function formatRange(
  min: string | null,
  max: string | null,
  empty = "Precio por confirmar",
): string {
  if (min === null || max === null) return empty;
  return min === max ? formatCOP(min) : `${formatCOP(min)} – ${formatCOP(max)}`;
}

export const dateFormat = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "long",
  timeZone: "America/Bogota",
});

/** "2026-12-07" (a date without time) shown as a local date, not shifted by the time zone. */
export function formatDateOnly(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat("es-CO", { dateStyle: "long" }).format(new Date(year, month - 1, day));
}
