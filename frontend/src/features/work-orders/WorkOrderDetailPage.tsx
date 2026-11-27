import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { ProductPicker } from "@/features/products/ProductPicker";
import { ApiError } from "@/shared/api/http";
import { formatDateOnly } from "@/shared/format";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { ReasonDialog } from "@/shared/ui/ReasonDialog";

import {
  useCancelWorkOrder,
  useReconcileWorkOrder,
  useUpdateWorkOrder,
  useWorkOrder,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_STATUS_STYLES,
  type WorkOrderDetail,
  type WorkOrderItem,
} from "./api";
import { CustomerLookup, type ChosenCustomer } from "./CustomerLookup";
import { todayIso } from "./WorkOrdersPage";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200 disabled:bg-slate-100";
const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "America/Bogota",
});
const SIIGO_WARNING =
  "Esta orden ya fue exportada a Siigo: al anularla aquí, anúlela también manualmente en Siigo.";

function messageOf(err: unknown, fallback: string): string {
  if (!(err instanceof ApiError)) return "No fue posible conectar con el servidor. Intente de nuevo.";
  const messages = Object.values(err.fieldErrors).flat();
  return messages.length ? messages.join(" ") : err.message || fallback;
}

/** One work order: details, edit while Pendiente, annul, and reconcile (US 2.38 … US 2.40). */
export function WorkOrderDetailPage() {
  const { workOrderId = "" } = useParams();
  const { data, isPending, error } = useWorkOrder(workOrderId);
  const [revision, setRevision] = useState(0);
  // Kept here: the detail below is rebuilt from the server's version after every change.
  const [notice, setNotice] = useState<string | null>(null);

  if (isPending) return <p className="text-sm text-slate-500">Cargando orden de trabajo…</p>;
  if (!data) {
    return (
      <div className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-6">
        <p className="text-red-700">
          {error instanceof ApiError ? error.message : "No fue posible cargar la orden de trabajo."}
        </p>
        <Link to="/ordenes-trabajo" className="mt-3 inline-block text-sm text-red-700 hover:underline">
          Volver a órdenes de trabajo
        </Link>
      </div>
    );
  }
  return (
    <Detail
      key={`${data.id}-${revision}`}
      order={data}
      notice={notice}
      onSaved={(message) => {
        setNotice(message);
        setRevision((r) => r + 1);
      }}
    />
  );
}

function Detail({
  order,
  notice,
  onSaved,
}: {
  order: WorkOrderDetail;
  notice: string | null;
  onSaved: (message: string) => void;
}) {
  const [cancelling, setCancelling] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const cancel = useCancelWorkOrder(order.id);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">
            <Link to="/ordenes-trabajo" className="hover:underline">Órdenes de trabajo</Link> / {order.number}
          </p>
          <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold">
            <span className="font-mono">{order.number}</span>
            <span className={`rounded-full px-2.5 py-0.5 text-sm font-medium ${WORK_ORDER_STATUS_STYLES[order.status]}`}>
              {WORK_ORDER_STATUS_LABELS[order.status]}
            </span>
          </h1>
          <p className="text-sm text-slate-600">
            Generada el {dateTime.format(new Date(order.created_at))}
            {order.created_by_name && ` por ${order.created_by_name}`} desde la cotización{" "}
            <span className="font-mono">{order.quotation_number}</span>.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {order.can_reconcile && <Button onClick={() => setReconciling(true)}>Marcar como Conciliada</Button>}
          {order.can_cancel && (
            <Button variant="danger" onClick={() => setCancelling(true)}>Anular</Button>
          )}
        </div>
      </div>

      {notice && <Notice tone="success">{notice}</Notice>}
      {order.status === "REGISTERED_IN_SIIGO" && (
        <Notice tone="muted">
          Exportada a Siigo: ya no se puede editar. Cuando se despache, márquela como Conciliada con la fecha real.
        </Notice>
      )}
      {order.status === "PENDING" && (
        <Notice tone="muted">
          Pendiente de exportar a Siigo. Puede editarla hasta que se genere su archivo de exportación.
        </Notice>
      )}
      {order.status === "CANCELLED" && (
        <Notice tone="muted">
          Anulada. Motivo: {order.cancellation_reason}. La cotización puede generar una nueva orden de trabajo.
        </Notice>
      )}

      {order.can_edit ? (
        <Editor order={order} onSaved={onSaved} />
      ) : (
        <ReadOnly order={order} />
      )}

      <ReasonDialog
        open={cancelling}
        title={`Anular ${order.number}`}
        label="Motivo de la anulación"
        hint="Queda registrado en la auditoría. La anulación no se puede deshacer."
        confirmLabel="Anular orden de trabajo"
        danger
        warning={order.was_exported ? SIIGO_WARNING : undefined}
        onConfirm={async (reason) => {
          await cancel.mutateAsync(reason);
          onSaved(
            order.was_exported
              ? "Orden de trabajo anulada. Recuerde anularla también en Siigo."
              : "Orden de trabajo anulada.",
          );
        }}
        onClose={() => setCancelling(false)}
      />
      <ReconcileDialog
        order={order}
        open={reconciling}
        onClose={() => setReconciling(false)}
        onDone={() => onSaved("Orden de trabajo conciliada.")}
      />
    </div>
  );
}

function ReadOnly({ order }: { order: WorkOrderDetail }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
        <h2 className="mb-3 text-lg font-medium">Productos</h2>
        <ItemsTable items={order.items} />
      </section>
      <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 text-sm">
        <Field label="Cliente">
          <Link to={`/clientes/${encodeURIComponent(order.customer_tax_id)}`} className="font-medium text-red-700 hover:underline">
            {order.customer_name}
          </Link>
          <p className="text-xs text-slate-500">{order.customer_tax_id}</p>
        </Field>
        <Field label="Entrega acordada">{formatDateOnly(order.agreed_delivery_date)}</Field>
        {order.actual_dispatch_date && (
          <Field label="Despacho real">{formatDateOnly(order.actual_dispatch_date)}</Field>
        )}
      </section>
    </div>
  );
}

function ItemsTable({ items }: { items: WorkOrderItem[] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-xs tracking-wide text-slate-500 uppercase">
        <tr>
          <th className="py-2">Código</th>
          <th className="py-2">Producto</th>
          <th className="py-2 text-right">Cantidad</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.product_id} className="border-t border-slate-100">
            <td className="py-2 font-mono text-xs">{item.product_code}</td>
            <td className="py-2">{item.description}</td>
            <td className="py-2 text-right whitespace-nowrap">
              {item.quantity} {item.unit_of_measure.toLowerCase()}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type Line = { product_id: string; product_code: string; description: string; unit_of_measure: string; quantity: string };

/** FR-02-21: customer, items with quantities and agreed date, only while Pendiente. */
function Editor({ order, onSaved }: { order: WorkOrderDetail; onSaved: (message: string) => void }) {
  const update = useUpdateWorkOrder(order.id);
  const [customer, setCustomer] = useState<ChosenCustomer | null>({
    id: order.customer_id,
    tax_id: order.customer_tax_id,
    name: order.customer_name,
  });
  const [lines, setLines] = useState<Line[]>(
    order.items.map((item) => ({ ...item, quantity: String(item.quantity) })),
  );
  const [agreed, setAgreed] = useState(order.agreed_delivery_date);
  const [error, setError] = useState<string | null>(null);

  const setQuantity = (productId: string, quantity: string) =>
    setLines(lines.map((l) => (l.product_id === productId ? { ...l, quantity: quantity.replace(/\D/g, "") } : l)));
  const remove = (productId: string) => setLines(lines.filter((l) => l.product_id !== productId));
  const add = (product: { id: string; code: string; name: string; unit_of_measure: string }) => {
    if (lines.some((l) => l.product_id === product.id)) return;
    setLines([
      ...lines,
      { product_id: product.id, product_code: product.code, description: product.name, unit_of_measure: product.unit_of_measure, quantity: "1" },
    ]);
  };

  const invalidQuantity = lines.some((l) => !Number(l.quantity));
  const canSave = customer !== null && lines.length > 0 && !invalidQuantity && Boolean(agreed);

  const save = async () => {
    if (!customer) return;
    setError(null);
    try {
      await update.mutateAsync({
        customer_id: customer.id,
        items: lines.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity) })),
        agreed_delivery_date: agreed,
      });
      onSaved("Cambios guardados.");
    } catch (err) {
      setError(messageOf(err, "No fue posible guardar los cambios."));
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
        <h2 className="mb-3 text-lg font-medium">Productos</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs tracking-wide text-slate-500 uppercase">
            <tr>
              <th className="py-2">Código</th>
              <th className="py-2">Producto</th>
              <th className="py-2 text-right">Cantidad</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.product_id} className="border-t border-slate-100">
                <td className="py-2 font-mono text-xs">{line.product_code}</td>
                <td className="py-2">{line.description}</td>
                <td className="py-2 text-right">
                  <input aria-label={`Cantidad de ${line.description}`} inputMode="numeric"
                    className={`${inputClass} w-24 text-right`} value={line.quantity}
                    onChange={(e) => setQuantity(line.product_id, e.target.value)} />
                </td>
                <td className="py-2 pl-2 text-right">
                  <Button variant="link" disabled={lines.length === 1} onClick={() => remove(line.product_id)}>
                    Quitar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {invalidQuantity && <p className="mt-2 text-xs text-red-700">Cada cantidad debe ser mayor que cero.</p>}
        <ProductPicker onPick={add} />
      </section>

      <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5 text-sm">
        <div>
          <p className="mb-1 font-medium text-slate-700">Cliente</p>
          <CustomerLookup chosen={customer} onChoose={setCustomer} />
        </div>
        <label className="block">
          <span className="mb-1 block font-medium text-slate-700">Fecha acordada de entrega</span>
          <input type="date" className={inputClass} value={agreed} min={todayIso()}
            onChange={(e) => setAgreed(e.target.value)} />
        </label>
        {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">{error}</p>}
        <Button className="w-full" disabled={!canSave || update.isPending} onClick={save}>
          {update.isPending ? "Guardando…" : "Guardar cambios"}
        </Button>
      </section>
    </div>
  );
}

function ReconcileDialog({
  order, open, onClose, onDone,
}: {
  order: WorkOrderDetail;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const reconcile = useReconcileWorkOrder(order.id);
  const today = todayIso();
  const [date, setDate] = useState(today);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    setError(null);
    try {
      await reconcile.mutateAsync(date);
      onClose();
      onDone();
    } catch (err) {
      setError(messageOf(err, "No fue posible conciliar la orden de trabajo."));
    }
  };

  return (
    <Modal open={open} title={`Conciliar ${order.number}`} onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">
          Indique la fecha real en que se despachó el pedido. Alimenta la fecha de despacho sugerida en
          futuras cotizaciones.
        </p>
        <label className="block">
          <span className="mb-1 block font-medium text-slate-700">Fecha real de despacho</span>
          <input type="date" max={today} className={inputClass} value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={!date || reconcile.isPending} onClick={confirm}>Marcar como Conciliada</Button>
        </div>
      </div>
    </Modal>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs tracking-wide text-slate-500 uppercase">{label}</p>
      <div>{children}</div>
    </div>
  );
}

function Notice({ tone, children }: { tone: "success" | "muted"; children: ReactNode }) {
  return (
    <p className={`rounded-lg p-4 text-sm ${tone === "success" ? "bg-green-50 text-green-900" : "bg-slate-100 text-slate-700"}`}>
      {children}
    </p>
  );
}
