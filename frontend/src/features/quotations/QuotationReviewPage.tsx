import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import type { Customer } from "@/features/customers/api";
import { ProductPicker } from "@/features/products/ProductPicker";
import { api, ApiError } from "@/shared/api/http";
import { formatCOP, formatDateOnly, formatRange } from "@/shared/format";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";
import { ReasonDialog } from "@/shared/ui/ReasonDialog";

import {
  downloadQuotationPdf,
  QUOTATION_STATUS_LABELS,
  QUOTATION_STATUS_STYLES,
  useApproveQuotation,
  useLinkCustomer,
  useModifyQuotation,
  useQuotation,
  useRejectQuotation,
  type QuotationDetail,
} from "./api";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200 disabled:bg-slate-100";
const dateTime = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

/** One editable row. ``itemId`` is null for a product added during this review. */
type Line = {
  key: string;
  itemId: string | null;
  productId: string;
  code: string;
  description: string;
  unit: string;
  quantity: string;
  min: string | null;
  max: string | null;
  source: "HISTORY" | "AI" | null;
  finalPrice: string;
};

function linesOf(detail: QuotationDetail): Line[] {
  return detail.items.map((item) => ({
    key: item.id,
    itemId: item.id,
    productId: item.product_id,
    code: item.product_code,
    description: item.description,
    unit: item.unit_of_measure,
    quantity: String(item.quantity),
    min: item.unit_price_min,
    max: item.unit_price_max,
    source: item.price_source,
    finalPrice: item.final_unit_price ?? "",
  }));
}

function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

/** Review of one quotation (US 2.12, US 2.13, US 2.27 … US 2.29). */
export function QuotationReviewPage() {
  const { quotationId = "" } = useParams();
  const { data, isPending, error } = useQuotation(quotationId);
  // Bumped after every saved change: the editor starts again from the server's version.
  const [revision, setRevision] = useState(0);

  if (isPending) return <p className="text-sm text-slate-500">Cargando cotización…</p>;
  if (!data) {
    return (
      <div className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-6">
        <p className="text-red-700">
          {error instanceof ApiError ? error.message : "No fue posible cargar la cotización."}
        </p>
        <Link to="/cotizaciones" className="mt-3 inline-block text-sm text-red-700 hover:underline">
          Volver a cotizaciones
        </Link>
      </div>
    );
  }
  return (
    <Review key={`${data.id}-${revision}`} detail={data} onSaved={() => setRevision((r) => r + 1)} />
  );
}

function Review({ detail, onSaved }: { detail: QuotationDetail; onSaved: () => void }) {
  const editable = detail.is_editable;
  const [lines, setLines] = useState<Line[]>(() => linesOf(detail));
  const [dispatchDate, setDispatchDate] = useState(detail.estimated_dispatch_date ?? "");
  const [terms, setTerms] = useState(detail.commercial_terms);
  const [dialog, setDialog] = useState<"modify" | "approve" | "reject" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const modify = useModifyQuotation(detail.id);
  const approve = useApproveQuotation(detail.id);
  const reject = useRejectQuotation(detail.id);

  const original = linesOf(detail);
  const structureChanged =
    lines.length !== original.length ||
    lines.some((line, index) => line.productId !== original[index].productId || line.quantity !== original[index].quantity);
  const anythingChanged =
    structureChanged ||
    lines.some((line, index) => line.finalPrice !== original[index]?.finalPrice) ||
    dispatchDate !== (detail.estimated_dispatch_date ?? "") ||
    terms !== detail.commercial_terms;

  const quantityError = lines.some((l) => !/^\d+$/.test(l.quantity) || Number(l.quantity) < 1);
  const missingPrices = lines.filter((l) => l.finalPrice === "").length;
  const finalTotal = missingPrices === 0
    ? lines.reduce((sum, l) => sum + Number(l.finalPrice) * Number(l.quantity || 0), 0)
    : null;

  const update = (key: string, changes: Partial<Line>) =>
    setLines(lines.map((line) => (line.key === key ? { ...line, ...changes } : line)));

  const addProduct = (product: { id: string; code: string; name: string; unit_of_measure: string }) => {
    if (lines.some((line) => line.productId === product.id)) return;
    setLines([
      ...lines,
      {
        key: `new-${product.id}`,
        itemId: null,
        productId: product.id,
        code: product.code,
        description: product.name,
        unit: product.unit_of_measure,
        quantity: "1",
        min: null,
        max: null,
        source: null,
        finalPrice: "",
      },
    ]);
  };

  const saveChanges = (reason: string) =>
    modify
      .mutateAsync({
        items: lines.map((l) => ({
          product_id: l.productId,
          quantity: Number(l.quantity),
          final_unit_price: l.finalPrice || null,
        })),
        reason,
        commercial_terms: terms,
        dispatch_date: dispatchDate || null,
      })
      .then(onSaved);

  const approveQuotation = () =>
    approve
      .mutateAsync({
        prices: lines
          .filter((l) => l.itemId !== null)
          .map((l) => ({ item_id: l.itemId as string, final_unit_price: l.finalPrice || null })),
        dispatch_date: dispatchDate || null,
        commercial_terms: terms,
      })
      .then(onSaved);

  const download = async () => {
    setDownloadError(null);
    try {
      await downloadQuotationPdf(detail);
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "No fue posible descargar el PDF.");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">
            <Link to="/cotizaciones" className="hover:underline">Cotizaciones</Link> / {detail.number}
          </p>
          <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold">
            Cotización {detail.number}
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${QUOTATION_STATUS_STYLES[detail.status]}`}>
              {QUOTATION_STATUS_LABELS[detail.status]}
            </span>
          </h1>
          <p className="text-sm text-slate-600">
            Emitida el {dateTime.format(new Date(detail.issued_at))} · Válida hasta el{" "}
            {formatDateOnly(detail.valid_until)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button variant="secondary" onClick={download}>
            {detail.status === "APPROVED" ? "Descargar cotización formal" : "Descargar PDF preliminar"}
          </Button>
          {downloadError && <p className="text-xs text-red-700">{downloadError}</p>}
        </div>
      </div>

      {detail.status === "APPROVED" && (
        <Notice tone="success">
          Aprobada por {detail.approved_by_name || "—"} el{" "}
          {detail.approved_at ? dateTime.format(new Date(detail.approved_at)) : "—"} · La
          cotización formal se envió a {detail.requester_email} y ya no se puede modificar.
        </Notice>
      )}
      {detail.status === "REJECTED" && (
        <Notice tone="muted">
          <strong>Rechazada.</strong> Motivo: {detail.rejection_reason}
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5 text-sm">
          <h2 className="mb-3 text-lg font-medium">Solicitante</h2>
          <dl className="grid grid-cols-[8rem_1fr] gap-y-1.5">
            <dt className="text-slate-500">Nombre</dt><dd>{detail.requester_name}</dd>
            <dt className="text-slate-500">Correo</dt><dd>{detail.requester_email}</dd>
            <dt className="text-slate-500">Teléfono</dt><dd>{detail.requester_phone}</dd>
            <dt className="text-slate-500">Institución</dt><dd>{detail.requester_institution || "—"}</dd>
            <dt className="text-slate-500">NIT indicado</dt><dd>{detail.requester_tax_id || "—"}</dd>
          </dl>
        </section>
        <CustomerSection detail={detail} />
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-1 text-lg font-medium">Productos</h2>
        <p className="mb-4 text-sm text-slate-600">
          {editable
            ? "Defina el precio unitario final de cada producto. El rango estimado es solo una referencia."
            : "Precios de la cotización."}
        </p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="text-xs text-slate-500 uppercase">
              <tr>
                <th className="py-2">Producto</th>
                <th className="py-2 w-24">Cantidad</th>
                <th className="py-2">Precio estimado (unidad)</th>
                <th className="py-2 w-44">Precio final (unidad)</th>
                <th className="py-2 text-right">Subtotal final</th>
                {editable && <th className="py-2" />}
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const subtotal = line.finalPrice !== "" && line.quantity !== ""
                  ? Number(line.finalPrice) * Number(line.quantity)
                  : null;
                return (
                  <tr key={line.key} className="border-t border-slate-100">
                    <td className="py-2 pr-3">
                      <p className="font-medium">{line.description}</p>
                      <p className="text-xs text-slate-500">{line.code} · {line.unit}</p>
                    </td>
                    <td className="py-2 pr-3">
                      {editable ? (
                        <input aria-label={`Cantidad de ${line.description}`} inputMode="numeric"
                          className={inputClass} value={line.quantity}
                          onChange={(e) => update(line.key, { quantity: e.target.value.replace(/\D/g, "") })} />
                      ) : line.quantity}
                    </td>
                    <td className="py-2 pr-3 text-slate-600">
                      {line.itemId === null
                        ? <span className="text-xs">Se estima al guardar</span>
                        : formatRange(line.min, line.max)}
                      {line.source === "AI" && (
                        <span className="ml-2 rounded bg-sky-50 px-1.5 py-0.5 text-xs text-sky-800"
                          title="Estimado por IA a partir de precios aprobados de productos similares">
                          IA
                        </span>
                      )}
                      {line.source === "HISTORY" && (
                        <span className="block text-xs text-slate-400">Según su historial</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {editable ? (
                        <input aria-label={`Precio final de ${line.description}`} inputMode="numeric"
                          placeholder="Precio en COP" className={inputClass} value={line.finalPrice}
                          onChange={(e) => update(line.key, { finalPrice: e.target.value.replace(/\D/g, "") })} />
                      ) : line.finalPrice ? formatCOP(line.finalPrice) : "—"}
                    </td>
                    <td className="py-2 text-right whitespace-nowrap">
                      {subtotal !== null ? formatCOP(subtotal) : "—"}
                    </td>
                    {editable && (
                      <td className="py-2 pl-2 text-right">
                        <Button variant="link" disabled={lines.length === 1}
                          title={lines.length === 1 ? "La cotización debe tener al menos un producto" : undefined}
                          onClick={() => setLines(lines.filter((l) => l.key !== line.key))}>
                          Quitar
                        </Button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200 font-medium">
                <td colSpan={2} className="py-3">Total</td>
                <td className="py-3 text-slate-600">
                  {formatRange(detail.total_min, detail.total_max, "Por confirmar")}
                </td>
                <td />
                <td className="py-3 text-right">
                  {finalTotal !== null ? formatCOP(finalTotal) : (
                    <span className="text-xs font-normal text-amber-700">
                      {missingPrices} producto(s) sin precio final
                    </span>
                  )}
                </td>
                {editable && <td />}
              </tr>
            </tfoot>
          </table>
        </div>
        {editable && <ProductPicker onPick={addProduct} />}
        {editable && quantityError && (
          <p className="mt-2 text-sm text-red-700">Cada cantidad debe ser un número entero mayor que cero.</p>
        )}
      </section>

      <section className="grid gap-6 rounded-lg border border-slate-200 bg-white p-5 lg:grid-cols-[16rem_1fr]">
        <div>
          <label htmlFor="dispatch-date" className="mb-1 block text-sm font-medium text-slate-700">
            Fecha de despacho
          </label>
          {editable ? (
            <input id="dispatch-date" type="date" min={todayIso()} className={inputClass}
              value={dispatchDate} onChange={(e) => setDispatchDate(e.target.value)} />
          ) : (
            <p className="text-sm">{detail.estimated_dispatch_date ? formatDateOnly(detail.estimated_dispatch_date) : "—"}</p>
          )}
          <p className="mt-1 text-xs text-slate-500">
            {detail.dispatch_date_source === "SUGGESTED"
              ? "Sugerida según tiempos históricos."
              : detail.estimated_dispatch_date
                ? "Ingresada manualmente."
                : "Sin datos históricos suficientes: ingrésela manualmente."}
          </p>
        </div>
        <div>
          <label htmlFor="terms" className="mb-1 block text-sm font-medium text-slate-700">
            Condiciones comerciales
          </label>
          {editable ? (
            <textarea id="terms" rows={3} maxLength={2000} className={inputClass}
              placeholder="Forma de pago, lugar de entrega, garantía…" value={terms}
              onChange={(e) => setTerms(e.target.value)} />
          ) : (
            <p className="text-sm whitespace-pre-line">{detail.commercial_terms || "—"}</p>
          )}
        </div>
      </section>

      {editable && (
        <div className="flex flex-wrap items-center justify-end gap-3 rounded-lg border border-slate-200 bg-white p-4">
          {structureChanged && (
            <p className="mr-auto text-sm text-amber-700">
              Cambió productos o cantidades: guarde los cambios antes de aprobar.
            </p>
          )}
          <Button variant="danger" onClick={() => setDialog("reject")}>Rechazar</Button>
          <Button variant="secondary" disabled={!anythingChanged || quantityError}
            onClick={() => setDialog("modify")}>
            Guardar cambios
          </Button>
          <Button disabled={structureChanged || quantityError} onClick={() => setDialog("approve")}>
            Aprobar
          </Button>
        </div>
      )}

      <ReasonDialog
        open={dialog === "modify"}
        title="Guardar cambios"
        label="Motivo de la modificación"
        hint="Queda registrado en la auditoría junto con el detalle de los cambios."
        confirmLabel="Guardar cambios"
        onConfirm={saveChanges}
        onClose={() => setDialog(null)}
      />
      <ReasonDialog
        open={dialog === "reject"}
        title={`Rechazar ${detail.number}`}
        label="Motivo del rechazo"
        hint={`Se enviará a ${detail.requester_email}. La cotización quedará rechazada y no podrá modificarse.`}
        confirmLabel="Rechazar cotización"
        danger
        onConfirm={(reason) => reject.mutateAsync(reason).then(onSaved)}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog === "approve"}
        title={`Aprobar ${detail.number}`}
        confirmLabel="Aprobar y enviar"
        onConfirm={approveQuotation}
        onClose={() => setDialog(null)}
      >
        <p>
          Total final: <strong>{finalTotal !== null ? formatCOP(finalTotal) : "incompleto"}</strong>
          {dispatchDate && <> · Despacho: <strong>{formatDateOnly(dispatchDate)}</strong></>}
        </p>
        <p className="mt-2 text-slate-600">
          Se enviará la cotización formal en PDF a {detail.requester_email}. Después de aprobarla no
          podrá modificarse ni rechazarse.
        </p>
      </ConfirmDialog>
    </div>
  );
}

function CustomerSection({ detail }: { detail: QuotationDetail }) {
  const link = useLinkCustomer(detail.id);
  const [taxId, setTaxId] = useState("");
  const [found, setFound] = useState<Customer | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const canLink = detail.is_editable || (detail.status === "APPROVED" && !detail.customer);

  const run = async (customerId: string | null) => {
    setMessage(null);
    try {
      await link.mutateAsync(customerId);
      setFound(null);
      setTaxId("");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "No fue posible vincular el cliente.");
    }
  };

  const search = async () => {
    setMessage(null);
    setFound(null);
    try {
      setFound(await api.get<Customer>(`/customers/by-tax-id/${encodeURIComponent(taxId.trim())}/`));
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "No fue posible buscar el cliente.");
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 text-sm">
      <h2 className="mb-1 text-lg font-medium">Cliente registrado</h2>
      <p className="mb-3 text-slate-600">
        Opcional al revisar. Es obligatorio para generar la orden de trabajo.
      </p>
      {detail.customer ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-3">
          <div>
            <Link to={`/clientes/${encodeURIComponent(detail.customer.tax_id)}`} className="font-medium text-red-700 hover:underline">
              {detail.customer.name}
            </Link>
            <p className="text-xs text-slate-500">{detail.customer.tax_id}</p>
          </div>
          {detail.is_editable && (
            <Button variant="link" disabled={link.isPending} onClick={() => run(null)}>Desvincular</Button>
          )}
        </div>
      ) : (
        <>
          {detail.suggested_customer && canLink && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-md bg-amber-50 p-3">
              <p>
                El NIT coincide con <strong>{detail.suggested_customer.name}</strong> (
                {detail.suggested_customer.tax_id}).
              </p>
              <Button disabled={link.isPending} onClick={() => run(detail.suggested_customer!.id)}>
                Vincular
              </Button>
            </div>
          )}
          {canLink ? (
            <div className="space-y-2">
              <div className="flex gap-2">
                <input aria-label="NIT o documento del cliente" placeholder="NIT o documento"
                  className={inputClass} value={taxId} onChange={(e) => setTaxId(e.target.value)} />
                <Button variant="secondary" disabled={!taxId.trim()} onClick={search}>Buscar</Button>
              </div>
              {found && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-3">
                  <div>
                    <p className="font-medium">{found.name}</p>
                    <p className="text-xs text-slate-500">
                      {found.tax_id}{!found.is_active && " · Inactivo: no se puede vincular"}
                    </p>
                  </div>
                  <Button disabled={!found.is_active || link.isPending} onClick={() => run(found.id)}>
                    Vincular
                  </Button>
                </div>
              )}
              <p className="text-xs text-slate-500">
                ¿No está registrado? <Link to="/clientes" className="text-red-700 hover:underline">Regístrelo en Clientes</Link>.
              </p>
            </div>
          ) : (
            <p className="text-slate-500">Sin cliente vinculado.</p>
          )}
        </>
      )}
      {message && <p role="alert" className="mt-2 text-red-700">{message}</p>}
    </section>
  );
}

function Notice({ tone, children }: { tone: "success" | "muted"; children: ReactNode }) {
  return (
    <p className={`rounded-lg p-4 text-sm ${tone === "success" ? "bg-green-50 text-green-900" : "bg-slate-100 text-slate-700"}`}>
      {children}
    </p>
  );
}
