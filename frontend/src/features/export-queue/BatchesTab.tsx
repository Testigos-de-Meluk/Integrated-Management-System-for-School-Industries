import { useState, type ReactNode } from "react";
import { Link } from "react-router";

import { WORK_ORDER_STATUS_LABELS, WORK_ORDER_STATUS_STYLES } from "@/features/work-orders/api";
import { ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

import { downloadBatch, useExportBatches, type ExportBatch } from "./api";

const PAGE_SIZE = 20;
const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

/**
 * "Lotes exportados": every generated file with its date, user and O.T.s (current status). The
 * file can be downloaded again, with a warning: importing it twice in Odoo duplicates the orders.
 */
export function BatchesTab() {
  const [page, setPage] = useState(1);
  const [again, setAgain] = useState<ExportBatch | null>(null);
  const { data, isPending, isError, error, isFetching } = useExportBatches(page, PAGE_SIZE);
  const batches = data?.results ?? [];

  return (
    <div>
      <details className="mb-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
        <summary className="cursor-pointer font-medium">Cómo importar el archivo en Odoo</summary>
        <ol className="mt-3 list-decimal space-y-1 pl-5">
          <li>
            En Odoo, los clientes deben existir con el <strong>mismo nombre</strong> que en IMSI y los productos con la{" "}
            <strong>referencia interna igual al código</strong> de IMSI.
          </li>
          <li>Abra Ventas → Pedidos, pulse el engranaje (⚙) y elija «Importar registros».</li>
          <li>Cargue el archivo .xlsx, pulse «Probar» y, si no hay errores, «Importar».</li>
          <li>
            Cada orden de trabajo queda como un pedido de venta; su número aparece en «Referencia del cliente».
          </li>
        </ol>
      </details>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[800px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">Generado</th>
              <th className="px-4 py-3">Archivo</th>
              <th className="px-4 py-3">Órdenes de trabajo</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Row>Cargando los lotes exportados…</Row>
            ) : isError ? (
              <Row error>{error instanceof ApiError ? error.message : "No fue posible cargar los lotes."}</Row>
            ) : batches.length === 0 ? (
              <Row>Todavía no se ha exportado ningún lote.</Row>
            ) : (
              batches.map((batch) => (
                <tr key={batch.id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3 whitespace-nowrap">
                    {dateTime.format(new Date(batch.created_at))}
                    <p className="text-xs text-slate-500">{batch.created_by_name}</p>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{batch.file_name}</td>
                  <td className="px-4 py-3">
                    <ul className="space-y-1">
                      {batch.work_orders.map((order) => (
                        <li key={order.work_order_id} className="flex flex-wrap items-center gap-2">
                          <Link
                            to={`/ordenes-trabajo/${order.work_order_id}`}
                            className="font-mono text-xs text-red-700 hover:underline"
                          >
                            {order.number}
                          </Link>
                          <span className="text-slate-600">{order.customer_name}</span>
                          {order.cancelled_after_export ? (
                            <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-800">
                              Anulada después de exportar: anúlela también en Odoo
                            </span>
                          ) : (
                            <span className={`rounded-full px-2 py-0.5 text-xs ${WORK_ORDER_STATUS_STYLES[order.status]}`}>
                              {WORK_ORDER_STATUS_LABELS[order.status]}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="secondary" onClick={() => setAgain(batch)}>
                      Descargar de nuevo
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data && data.total_pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm text-slate-600">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span>Página {data.page} de {data.total_pages}</span>
          <Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
            Siguiente
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={again !== null}
        title="Descargar de nuevo"
        confirmLabel="Descargar"
        onConfirm={() => (again ? downloadBatch(again) : Promise.resolve())}
        onClose={() => setAgain(null)}
      >
        <p>
          Si <span className="font-mono text-xs">{again?.file_name}</span> ya se importó en Odoo, importarlo de nuevo
          duplicará los pedidos de venta. Descárguelo solo si la importación anterior falló o se perdió el archivo.
        </p>
      </ConfirmDialog>
    </div>
  );
}

function Row({ error = false, children }: { error?: boolean; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={4} className={`px-4 py-10 text-center ${error ? "text-red-700" : "text-slate-500"}`}>
        {children}
      </td>
    </tr>
  );
}
