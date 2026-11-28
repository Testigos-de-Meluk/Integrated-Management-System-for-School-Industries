import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { ApiError } from "@/shared/api/http";
import { formatDateOnly } from "@/shared/format";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { NonBusinessDayWarning } from "@/shared/calendar/businessDays";

import {
  useAvailableQuotations,
  useGenerateWorkOrder,
  useWorkOrders,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_STATUS_STYLES,
  type AvailableQuotation,
  type WorkOrderFilters,
  type WorkOrderItem,
  type WorkOrderStatus,
  type WorkOrderSummary,
} from "./api";
import { CustomerLookup, type ChosenCustomer } from "./CustomerLookup";

const PAGE_SIZE = 20;
const EMPTY: WorkOrderFilters = {
  number: "",
  quotation_number: "",
  customer: "",
  product: "",
  agreed_from: "",
  agreed_to: "",
  status: "",
};
const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";

export function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" }).format(new Date());
}

export function itemsText(items: Pick<WorkOrderItem, "description" | "quantity">[], limit = 2): string {
  const shown = items.slice(0, limit).map((i) => `${i.description} × ${i.quantity}`);
  const rest = items.length - limit;
  return rest > 0 ? `${shown.join(", ")} y ${rest} más` : shown.join(", ");
}

/** Work orders (US 2.35, US 2.36) and "Generar O.T." from approved quotations (US 2.37). */
export function WorkOrdersPage() {
  const [draft, setDraft] = useState<WorkOrderFilters>(EMPTY);
  const [filters, setFilters] = useState<WorkOrderFilters>(EMPTY);
  const [page, setPage] = useState(1);
  const [generating, setGenerating] = useState(false);
  const { data, isPending, isError, error, isFetching } = useWorkOrders(filters, page, PAGE_SIZE);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };
  const set = (field: keyof WorkOrderFilters) => (value: string) => setDraft({ ...draft, [field]: value });
  const filtered = Object.values(filters).some(Boolean);

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Inicio / Órdenes de trabajo</p>
          <h1 className="text-2xl font-semibold">Órdenes de trabajo</h1>
          <p className="text-sm text-slate-600">
            Se generan a partir de cotizaciones aprobadas. Solo las órdenes Pendientes se pueden editar.
          </p>
        </div>
        <Button onClick={() => setGenerating(true)}>Generar O.T.</Button>
      </div>

      <form
        onSubmit={search}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <label className="text-xs text-slate-600">
          Número de O.T.
          <input placeholder="OT-…" className={inputClass} value={draft.number}
            onChange={(e) => set("number")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Cotización de origen
          <input placeholder="COT-…" className={inputClass} value={draft.quotation_number}
            onChange={(e) => set("quotation_number")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Cliente
          <input placeholder="Nombre o NIT" className={inputClass} value={draft.customer}
            onChange={(e) => set("customer")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Producto
          <input placeholder="Código o descripción" className={inputClass} value={draft.product}
            onChange={(e) => set("product")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Entrega acordada desde
          <input type="date" className={inputClass} value={draft.agreed_from}
            onChange={(e) => set("agreed_from")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Entrega acordada hasta
          <input type="date" className={inputClass} value={draft.agreed_to}
            onChange={(e) => set("agreed_to")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Estado
          <select className={inputClass} value={draft.status}
            onChange={(e) => set("status")(e.target.value as WorkOrderStatus | "")}>
            <option value="">Todos los estados</option>
            {Object.entries(WORK_ORDER_STATUS_LABELS).map(([value, label]) => (
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
              <th className="px-4 py-3">Cliente</th>
              <th className="px-4 py-3">Productos</th>
              <th className="px-4 py-3">Entrega acordada</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3 text-right">Acción</th>
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Message>Cargando órdenes de trabajo…</Message>
            ) : isError ? (
              <Message tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar las órdenes de trabajo."}
              </Message>
            ) : data.results.length === 0 ? (
              <Message>
                {filtered
                  ? "No se encontraron órdenes de trabajo con los filtros aplicados."
                  : "Aún no hay órdenes de trabajo. Genere la primera desde una cotización aprobada."}
              </Message>
            ) : (
              data.results.map((order) => <Row key={order.id} order={order} />)
            )}
          </tbody>
        </table>
      </div>

      {data && data.count > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <span>
            Mostrando {(data.page - 1) * data.page_size + 1}–
            {Math.min(data.page * data.page_size, data.count)} de {data.count} órdenes
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

      <GenerateDialog open={generating} onClose={() => setGenerating(false)} />
    </div>
  );
}

function Row({ order }: { order: WorkOrderSummary }) {
  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="px-4 py-3">
        <p className="font-mono text-xs">{order.number}</p>
        <p className="font-mono text-xs text-slate-500">{order.quotation_number}</p>
      </td>
      <td className="px-4 py-3">
        <p className="font-medium">{order.customer_name}</p>
        <p className="text-xs text-slate-500">{order.customer_tax_id}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">{itemsText(order.items)}</td>
      <td className="px-4 py-3 whitespace-nowrap">{formatDateOnly(order.agreed_delivery_date)}</td>
      <td className="px-4 py-3">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${WORK_ORDER_STATUS_STYLES[order.status]}`}>
          {WORK_ORDER_STATUS_LABELS[order.status]}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <Link to={`/ordenes-trabajo/${order.id}`} className="text-sm font-medium text-red-700 hover:underline">
          {order.status === "PENDING" ? "Ver o editar" : "Ver"}
        </Link>
      </td>
    </tr>
  );
}

function Message({ tone = "info", children }: { tone?: "info" | "error"; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={6} className={`px-4 py-10 text-center ${tone === "error" ? "text-red-700" : "text-slate-500"}`}>
        {children}
      </td>
    </tr>
  );
}

/** Step 1: choose an approved quotation without an active O.T. Step 2: confirm the details. */
function GenerateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AvailableQuotation | null>(null);
  const { data, isPending, isError } = useAvailableQuotations(search.trim(), page, open);

  const close = () => {
    setSelected(null);
    setSearch("");
    setPage(1);
    onClose();
  };

  return (
    <Modal open={open} title="Generar orden de trabajo" onClose={close}>
      {selected ? (
        <ConfirmGeneration quotation={selected} onBack={() => setSelected(null)} onDone={close} />
      ) : (
        <div className="space-y-3 text-sm">
          <p className="text-slate-600">Cotizaciones aprobadas que aún no tienen una orden de trabajo activa.</p>
          <input aria-label="Buscar cotización" placeholder="Número, solicitante, institución o NIT"
            className={inputClass} value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          {isPending ? (
            <p className="text-slate-500">Cargando cotizaciones…</p>
          ) : isError ? (
            <p className="text-red-700">No fue posible cargar las cotizaciones aprobadas.</p>
          ) : data.results.length === 0 ? (
            <p className="rounded-md bg-slate-50 p-3 text-slate-600">
              {search.trim()
                ? "Ninguna cotización aprobada coincide con la búsqueda."
                : "No hay cotizaciones aprobadas pendientes de orden de trabajo."}
            </p>
          ) : (
            <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
              {data.results.map((quotation) => (
                <li key={quotation.id}>
                  <button type="button" onClick={() => setSelected(quotation)}
                    className="w-full px-3 py-2 text-left hover:bg-slate-50">
                    <span className="font-mono text-xs">{quotation.number}</span>
                    <span className="block font-medium">
                      {quotation.customer_name || quotation.requester_institution || quotation.requester_name}
                    </span>
                    <span className="block text-xs text-slate-500">{itemsText(quotation.items)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-end gap-2 text-xs text-slate-600">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
              <span>Página {data.page} de {data.total_pages}</span>
              <Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
                Siguiente
              </Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function ConfirmGeneration({
  quotation,
  onBack,
  onDone,
}: {
  quotation: AvailableQuotation;
  onBack: () => void;
  onDone: () => void;
}) {
  const navigate = useNavigate();
  const generate = useGenerateWorkOrder();
  const today = todayIso();
  const usableDispatch = quotation.dispatch_date && quotation.dispatch_date >= today ? quotation.dispatch_date : "";
  const [agreed, setAgreed] = useState(usableDispatch);
  const [customer, setCustomer] = useState<ChosenCustomer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const needsCustomer = quotation.customer_id === null;
  const inactiveCustomer = quotation.customer_id !== null && quotation.customer_active === false;

  const submit = async () => {
    setError(null);
    try {
      const order = await generate.mutateAsync({
        quotation_id: quotation.id,
        customer_id: needsCustomer ? (customer?.id ?? null) : null,
        agreed_delivery_date: agreed || null,
      });
      onDone();
      navigate(`/ordenes-trabajo/${order.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const messages = Object.values(err.fieldErrors).flat();
        setError(messages.length ? messages.join(" ") : err.message);
      } else {
        setError("No fue posible conectar con el servidor. Intente de nuevo.");
      }
    }
  };

  return (
    <div className="space-y-4 text-sm">
      <div className="rounded-md bg-slate-50 p-3">
        <p className="font-mono text-xs">{quotation.number}</p>
        <p className="font-medium">{quotation.requester_name}</p>
        {quotation.requester_institution && <p className="text-xs text-slate-500">{quotation.requester_institution}</p>}
        <ul className="mt-2 list-disc pl-5 text-slate-700">
          {quotation.items.map((item) => (
            <li key={item.product_id}>
              {item.description} × {item.quantity} {item.unit_of_measure.toLowerCase()}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="mb-1 font-medium text-slate-700">Cliente</p>
        {needsCustomer ? (
          <>
            <p className="mb-2 text-xs text-slate-500">
              La cotización no tiene cliente. El que elija quedará vinculado también a la cotización.
            </p>
            <CustomerLookup chosen={customer} onChoose={setCustomer} />
          </>
        ) : (
          <p className={inactiveCustomer ? "text-red-700" : ""}>
            {quotation.customer_name}
            {inactiveCustomer && " · Inactivo: reactívelo en Clientes para generar la orden."}
          </p>
        )}
      </div>

      <label className="block">
        <span className="mb-1 block font-medium text-slate-700">Fecha acordada de entrega</span>
        <input type="date" min={today} className={inputClass} value={agreed}
          onChange={(e) => setAgreed(e.target.value)} />
        <NonBusinessDayWarning date={agreed} />
        <span className="mt-1 block text-xs text-slate-500">
          {quotation.dispatch_date
            ? usableDispatch
              ? "Tomada de la fecha de despacho de la cotización."
              : `La fecha de despacho de la cotización (${formatDateOnly(quotation.dispatch_date)}) ya pasó: indique una nueva.`
            : "La cotización no tiene fecha de despacho: indique una."}
        </span>
      </label>

      {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">{error}</p>}
      <div className="flex justify-between gap-2">
        <Button variant="secondary" onClick={onBack}>Volver</Button>
        <Button
          disabled={generate.isPending || !agreed || (needsCustomer && !customer) || inactiveCustomer}
          onClick={submit}
        >
          {generate.isPending ? "Generando…" : "Generar O.T."}
        </Button>
      </div>
    </div>
  );
}
