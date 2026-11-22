import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { ApiError } from "@/shared/api/http";
import { formatCOP, formatRange } from "@/shared/format";
import { Button } from "@/shared/ui/Button";

import {
  QUOTATION_STATUS_LABELS,
  QUOTATION_STATUS_STYLES,
  useQuotations,
  type QuotationFilters,
  type QuotationStatus,
  type QuotationSummary,
} from "./api";

const PAGE_SIZE = 20;
const EMPTY: QuotationFilters = {
  issued_from: "",
  issued_to: "",
  contact: "",
  product: "",
  total_min: "",
  total_max: "",
  status: "",
};
const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";

const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

/** Review tray of the quotations requested in the virtual assistant (US 2.25, US 2.26). */
export function QuotationsPage() {
  const [draft, setDraft] = useState<QuotationFilters>(EMPTY);
  const [filters, setFilters] = useState<QuotationFilters>(EMPTY);
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error, isFetching } = useQuotations(filters, page, PAGE_SIZE);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };
  const set = (field: keyof QuotationFilters) => (value: string) =>
    setDraft({ ...draft, [field]: value });

  const filtered = Object.values(filters).some(Boolean);

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        <p className="text-sm text-slate-500">Inicio / Cotizaciones</p>
        <h1 className="text-2xl font-semibold">Cotizaciones</h1>
        <p className="text-sm text-slate-600">
          Solicitudes recibidas en el asistente virtual. Ábralas para modificarlas, aprobarlas con
          los precios finales o rechazarlas.
        </p>
      </div>

      <form
        onSubmit={search}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <label className="text-xs text-slate-600">
          Emitida desde
          <input type="date" className={inputClass} value={draft.issued_from}
            onChange={(e) => set("issued_from")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Emitida hasta
          <input type="date" className={inputClass} value={draft.issued_to}
            onChange={(e) => set("issued_to")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Solicitante
          <input placeholder="Nombre, correo, teléfono, institución o NIT" className={inputClass}
            value={draft.contact} onChange={(e) => set("contact")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Producto
          <input placeholder="Código o descripción" className={inputClass} value={draft.product}
            onChange={(e) => set("product")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Monto desde (COP)
          <input inputMode="numeric" placeholder="0" className={inputClass} value={draft.total_min}
            onChange={(e) => set("total_min")(e.target.value.replace(/\D/g, ""))} />
        </label>
        <label className="text-xs text-slate-600">
          Monto hasta (COP)
          <input inputMode="numeric" placeholder="Sin límite" className={inputClass}
            value={draft.total_max} onChange={(e) => set("total_max")(e.target.value.replace(/\D/g, ""))} />
        </label>
        <label className="text-xs text-slate-600">
          Estado
          <select className={inputClass} value={draft.status}
            onChange={(e) => set("status")(e.target.value as QuotationStatus | "")}>
            <option value="">Todos los estados</option>
            {Object.entries(QUOTATION_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <div className="flex items-end gap-2">
          <Button type="submit" className="flex-1">Buscar</Button>
          <Button variant="secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>
            Limpiar
          </Button>
        </div>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">Número</th>
              <th className="px-4 py-3">Emitida</th>
              <th className="px-4 py-3">Solicitante</th>
              <th className="px-4 py-3">Productos</th>
              <th className="px-4 py-3 text-right">Monto</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3 text-right">Acción</th>
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Message>Cargando cotizaciones…</Message>
            ) : isError ? (
              <Message tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar las cotizaciones."}
              </Message>
            ) : data.results.length === 0 ? (
              <Message>
                {filtered
                  ? "No se encontraron cotizaciones con los filtros aplicados."
                  : "Aún no hay solicitudes de cotización."}
              </Message>
            ) : (
              data.results.map((quotation) => <Row key={quotation.id} quotation={quotation} />)
            )}
          </tbody>
        </table>
      </div>

      {data && data.count > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <span>
            Mostrando {(data.page - 1) * data.page_size + 1}–
            {Math.min(data.page * data.page_size, data.count)} de {data.count} cotizaciones
          </span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
            <span>Página {data.page} de {data.total_pages}</span>
            <Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ quotation }: { quotation: QuotationSummary }) {
  const products = quotation.products;
  const editable = quotation.status === "PENDING_REVIEW" || quotation.status === "MODIFIED";
  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="px-4 py-3 font-mono text-xs">{quotation.number}</td>
      <td className="px-4 py-3 whitespace-nowrap">{dateTime.format(new Date(quotation.issued_at))}</td>
      <td className="px-4 py-3">
        <p className="font-medium">{quotation.requester_name}</p>
        <p className="text-xs text-slate-500">{quotation.requester_email} · {quotation.requester_phone}</p>
        {quotation.requester_institution && (
          <p className="text-xs text-slate-500">{quotation.requester_institution}</p>
        )}
      </td>
      <td className="px-4 py-3 text-slate-700">
        {products.slice(0, 2).join(", ")}
        {products.length > 2 && <span className="text-slate-500"> y {products.length - 2} más</span>}
      </td>
      <td className="px-4 py-3 text-right whitespace-nowrap">
        {quotation.final_total !== null ? (
          <span className="font-medium">{formatCOP(quotation.final_total)}</span>
        ) : (
          <>
            <span>{formatRange(quotation.total_min, quotation.total_max, "Por confirmar")}</span>
            {quotation.unpriced_items > 0 && (
              <p className="text-xs text-amber-700">{quotation.unpriced_items} sin precio</p>
            )}
          </>
        )}
      </td>
      <td className="px-4 py-3">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${QUOTATION_STATUS_STYLES[quotation.status]}`}>
          {QUOTATION_STATUS_LABELS[quotation.status]}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <Link to={`/cotizaciones/${quotation.id}`} className="text-sm font-medium text-red-700 hover:underline">
          {editable ? "Revisar" : "Ver"}
        </Link>
      </td>
    </tr>
  );
}

function Message({ tone = "info", children }: { tone?: "info" | "error"; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={7} className={`px-4 py-10 text-center ${tone === "error" ? "text-red-700" : "text-slate-500"}`}>
        {children}
      </td>
    </tr>
  );
}
