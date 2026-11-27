import { useState } from "react";
import { Link } from "react-router";

import { QUOTATION_STATUS_LABELS, type QuotationStatus } from "@/features/quotations/api";
import { WORK_ORDER_STATUS_LABELS, type WorkOrderStatus } from "@/features/work-orders/api";
import { hasPermission, useSession } from "@/shared/auth/session";
import { Button } from "@/shared/ui/Button";

import { useCustomerHistory, type HistoryType } from "./api";

const dateFormat = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "America/Bogota" });

const TABS: { type: HistoryType; label: string; empty: string }[] = [
  { type: "QUOTATION", label: "Cotizaciones", empty: "Este cliente aún no tiene cotizaciones." },
  { type: "WORK_ORDER", label: "Órdenes de trabajo", empty: "Este cliente aún no tiene órdenes de trabajo." },
];

/** 360° history (US 2.20): quotations and work orders in two tabs, each with its own pages. */
export function HistorySection({ customerId }: { customerId: string }) {
  const [type, setType] = useState<HistoryType>("QUOTATION");
  const [pages, setPages] = useState<Record<HistoryType, number>>({ QUOTATION: 1, WORK_ORDER: 1 });
  const page = pages[type];
  const history = useCustomerHistory(customerId, type, page);
  const { user } = useSession();
  // Links only where the user can open the document (the backend enforces it anyway).
  const canOpen =
    type === "QUOTATION" ? hasPermission(user, "QUOTATION_MANAGE") : hasPermission(user, "WORK_ORDER_MANAGE");
  const tab = TABS.find((t) => t.type === type)!;
  const setPage = (next: number) => setPages({ ...pages, [type]: next });

  const statusLabel = (status: string) =>
    type === "QUOTATION"
      ? (QUOTATION_STATUS_LABELS[status as QuotationStatus] ?? status)
      : (WORK_ORDER_STATUS_LABELS[status as WorkOrderStatus] ?? status);
  const linkTo = (id: string) => (type === "QUOTATION" ? `/cotizaciones/${id}` : `/ordenes-trabajo/${id}`);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-3 text-lg font-medium">Historial de cotizaciones y órdenes de trabajo</h2>
      <div role="tablist" className="mb-4 flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button key={t.type} type="button" role="tab" aria-selected={t.type === type}
            onClick={() => setType(t.type)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              t.type === type ? "border-red-700 font-medium text-red-700" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {history.isError ? (
        <p role="alert" className="text-sm text-red-700">No fue posible cargar el historial. Intente de nuevo.</p>
      ) : history.isPending ? (
        <p className="text-sm text-slate-500">Cargando historial…</p>
      ) : history.data.results.length === 0 ? (
        <p className="text-sm text-slate-500">{tab.empty}</p>
      ) : (
        <>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500 uppercase">
              <tr>
                <th className="py-2">Referencia</th>
                <th className="py-2">Fecha</th>
                <th className="py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {history.data.results.map((entry) => (
                <tr key={entry.id} className="border-t border-slate-100">
                  <td className="py-2 font-mono text-xs">
                    {canOpen ? (
                      <Link to={linkTo(entry.id)} className="text-red-700 hover:underline">{entry.reference}</Link>
                    ) : (
                      entry.reference
                    )}
                  </td>
                  <td className="py-2">{dateFormat.format(new Date(entry.date))}</td>
                  <td className="py-2">{statusLabel(entry.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {history.data.total_pages > 1 && (
            <div className="mt-3 flex items-center justify-end gap-2 text-sm text-slate-600">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
              <span>Página {history.data.page} de {history.data.total_pages}</span>
              <Button variant="secondary" disabled={page >= history.data.total_pages} onClick={() => setPage(page + 1)}>
                Siguiente
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
