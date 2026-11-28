import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { itemsText } from "@/features/work-orders/WorkOrdersPage";
import { ApiError } from "@/shared/api/http";
import { formatDateOnly } from "@/shared/format";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

import { BatchesTab } from "./BatchesTab";
import {
  downloadBatch,
  useExportQueue,
  useExportWorkOrders,
  type QueueEntry,
  type QueueFilters,
} from "./api";

const PAGE_SIZE = 20;
const EMPTY: QueueFilters = { created_from: "", created_to: "", customer: "", number: "" };
const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";
const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

type Tab = "queue" | "batches";

/**
 * "Exportación a Odoo" (US 2.31 … US 2.34): the queue of work orders waiting to be exported and the
 * exported batches. Generating the file moves the selected O.T.s to "Registrada en Odoo"; the file
 * is imported by hand in Odoo (Ventas → Pedidos → Importar registros).
 */
export function ExportQueuePage() {
  const [tab, setTab] = useState<Tab>("queue");
  const tabClass = (value: Tab) =>
    `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
      tab === value ? "border-red-700 text-red-700" : "border-transparent text-slate-600 hover:text-slate-900"
    }`;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-4">
        <p className="text-sm text-slate-500">Inicio / Exportación a Odoo</p>
        <h1 className="text-2xl font-semibold">Exportación a Odoo</h1>
        <p className="text-sm text-slate-600">
          Seleccione las órdenes de trabajo que quiere incluir en el archivo para Odoo; al generarlo quedarán como
          «Registrada en Odoo» y ya no se podrán editar.
        </p>
      </div>
      <div role="tablist" className="mb-4 flex border-b border-slate-200">
        <button role="tab" aria-selected={tab === "queue"} className={tabClass("queue")} onClick={() => setTab("queue")}>
          Pendientes de exportar
        </button>
        <button role="tab" aria-selected={tab === "batches"} className={tabClass("batches")} onClick={() => setTab("batches")}>
          Lotes exportados
        </button>
      </div>
      {tab === "queue" ? <QueueTab onExported={() => setTab("batches")} /> : <BatchesTab />}
    </div>
  );
}

function QueueTab({ onExported }: { onExported: () => void }) {
  const [draft, setDraft] = useState<QueueFilters>(EMPTY);
  const [filters, setFilters] = useState<QueueFilters>(EMPTY);
  const [page, setPage] = useState(1);
  // Kept across pages and filters: the batch is built from several searches (US 2.33).
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const { data, isPending, isError, error, isFetching } = useExportQueue(filters, page, PAGE_SIZE);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };
  const set = (field: keyof QueueFilters) => (value: string) => setDraft({ ...draft, [field]: value });
  const filtered = Object.values(filters).some(Boolean);

  const toggle = (entry: QueueEntry) => {
    const next = new Map(selected);
    if (next.has(entry.work_order_id)) next.delete(entry.work_order_id);
    else next.set(entry.work_order_id, entry.number);
    setSelected(next);
  };
  const pageEntries = data?.results ?? [];
  const allOnPage = pageEntries.length > 0 && pageEntries.every((e) => selected.has(e.work_order_id));
  const togglePage = () => {
    const next = new Map(selected);
    pageEntries.forEach((e) => (allOnPage ? next.delete(e.work_order_id) : next.set(e.work_order_id, e.number)));
    setSelected(next);
  };

  const queryClient = useQueryClient();
  const exportOrders = useExportWorkOrders();
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  const generate = async () => {
    let batch;
    try {
      batch = await exportOrders.mutateAsync([...selected.keys()]);
    } catch (err) {
      // Exported or annulled by someone else meanwhile: show the current queue.
      if (err instanceof ApiError && err.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["export-queue"] });
      }
      throw err;
    }
    setSelected(new Map());
    try {
      await downloadBatch(batch);
      setNotice({
        tone: "ok",
        text: `Se generó ${batch.file_name} con ${batch.work_orders.length} orden(es); ya están «Registrada en Odoo». Impórtelo en Odoo.`,
      });
    } catch {
      setNotice({
        tone: "warn",
        text: `Se generó ${batch.file_name}, pero no se pudo descargar. Descárguelo desde «Lotes exportados».`,
      });
    }
  };

  return (
    <div>
      {notice && (
        <div
          role="status"
          className={`mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md p-3 text-sm ${
            notice.tone === "ok" ? "bg-green-50 text-green-800" : "bg-amber-50 text-amber-900"
          }`}
        >
          <span>{notice.text}</span>
          <Button variant="secondary" onClick={onExported}>Ver lotes exportados</Button>
        </div>
      )}

      <form
        onSubmit={search}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        <label className="text-xs text-slate-600">
          Generada desde
          <input type="date" className={inputClass} value={draft.created_from}
            onChange={(e) => set("created_from")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Generada hasta
          <input type="date" className={inputClass} value={draft.created_to}
            onChange={(e) => set("created_to")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Cliente
          <input placeholder="Nombre o NIT" className={inputClass} value={draft.customer}
            onChange={(e) => set("customer")(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">
          Número de O.T.
          <input placeholder="OT-…" className={inputClass} value={draft.number}
            onChange={(e) => set("number")(e.target.value)} />
        </label>
        <div className="flex items-end gap-2">
          <Button type="submit" className="flex-1">Buscar</Button>
          <Button variant="secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>
            Limpiar
          </Button>
        </div>
      </form>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm">
        <span>
          {selected.size === 0
            ? "Ninguna orden seleccionada."
            : `${selected.size} orden${selected.size === 1 ? "" : "es"} seleccionada${selected.size === 1 ? "" : "s"}: ${[...selected.values()].join(", ")}`}
        </span>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <Button variant="secondary" onClick={() => setSelected(new Map())}>Quitar selección</Button>
          )}
          <Button disabled={selected.size === 0} onClick={() => setConfirming(true)}>
            Generar archivo para Odoo
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirming}
        title="Generar archivo para Odoo"
        confirmLabel="Generar y descargar"
        onConfirm={generate}
        onClose={() => setConfirming(false)}
      >
        <p>
          Se generará un archivo con {selected.size} orden{selected.size === 1 ? "" : "es"} de trabajo:{" "}
          <span className="font-mono text-xs">{[...selected.values()].join(", ")}</span>.
        </p>
        <p className="mt-2">
          Quedarán como «Registrada en Odoo», saldrán de la cola y ya no se podrán editar. Luego importe el archivo en
          Odoo (Ventas → Pedidos → Importar registros).
        </p>
      </ConfirmDialog>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="w-10 px-4 py-3">
                <input type="checkbox" aria-label="Seleccionar todas las de esta página"
                  checked={allOnPage} onChange={togglePage} disabled={pageEntries.length === 0} />
              </th>
              <th className="px-4 py-3">Orden de trabajo</th>
              <th className="px-4 py-3">Generada</th>
              <th className="px-4 py-3">Cliente</th>
              <th className="px-4 py-3">Productos</th>
              <th className="px-4 py-3">Entrega acordada</th>
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Message>Cargando la cola de exportación…</Message>
            ) : isError ? (
              <Message tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar la cola de exportación."}
              </Message>
            ) : pageEntries.length === 0 ? (
              <Message>
                {filtered
                  ? "No se encontraron órdenes con los filtros aplicados."
                  : "No hay órdenes de trabajo pendientes de exportar."}
              </Message>
            ) : (
              pageEntries.map((entry) => (
                <tr key={entry.work_order_id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3">
                    <input type="checkbox" aria-label={`Seleccionar ${entry.number}`}
                      checked={selected.has(entry.work_order_id)} onChange={() => toggle(entry)} />
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/ordenes-trabajo/${entry.work_order_id}`} className="font-mono text-xs text-red-700 hover:underline">
                      {entry.number}
                    </Link>
                    <p className="font-mono text-xs text-slate-500">{entry.quotation_number}</p>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{dateTime.format(new Date(entry.created_at))}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium">{entry.customer_name}</p>
                    <p className="text-xs text-slate-500">{entry.customer_tax_id}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{itemsText(entry.items)}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{formatDateOnly(entry.agreed_delivery_date)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data && data.count > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <span>
            Mostrando {(data.page - 1) * data.page_size + 1}–
            {Math.min(data.page * data.page_size, data.count)} de {data.count} órdenes pendientes
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

function Message({ tone = "info", children }: { tone?: "info" | "error"; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={6} className={`px-4 py-10 text-center ${tone === "error" ? "text-red-700" : "text-slate-500"}`}>
        {children}
      </td>
    </tr>
  );
}
