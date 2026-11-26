import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { ApiError } from "@/shared/api/http";
import { formatDateOnly, formatRange } from "@/shared/format";
import { Button } from "@/shared/ui/Button";
import { TextField } from "@/shared/ui/TextField";

import {
  quoteApi,
  useAssistantOptions,
  useEstimate,
  usePublicCatalog,
  type CatalogItem,
  type ContactData,
  type PreliminaryQuotation,
  type Proposal,
} from "./api";

type Selection = Map<string, { product: CatalogItem; quantity: number }>;

const STEPS = ["Datos", "Productos", "Resumen"];

/** Public portal: preliminary quotation in three guided steps (FR-02-05, US 2.7 … US 2.10). */
export function QuoteRequestPage() {
  const [step, setStep] = useState(0);
  const [contact, setContact] = useState<ContactData | null>(null);
  const [selection, setSelection] = useState<Selection>(new Map());
  const [quotation, setQuotation] = useState<PreliminaryQuotation | null>(null);

  const restart = () => {
    setSelection(new Map());
    setQuotation(null);
    setStep(1);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4">
          <div>
            <p className="text-lg font-bold text-red-700">Industrias Escolares</p>
            <p className="text-xs text-slate-500">Fabricación de mobiliario escolar</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium">Cotiza tu mobiliario escolar</p>
            <p className="text-xs text-slate-500">Sin crear una cuenta · Acompañamiento paso a paso</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <ol className="mb-6 grid grid-cols-3 gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          {STEPS.map((label, index) => (
            <li key={label} className="flex items-center gap-2">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  index < step
                    ? "bg-green-100 text-green-800"
                    : index === step
                      ? "bg-red-700 text-white"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {index < step ? "✓" : index + 1}
              </span>
              <span className={index === step ? "font-medium" : "text-slate-500"}>{label}</span>
            </li>
          ))}
        </ol>

        {step === 0 && (
          <ContactStep
            initial={contact}
            onNext={(data) => {
              setContact(data);
              setStep(1);
            }}
          />
        )}
        {step === 1 && contact && (
          <ProductsStep
            contact={contact}
            selection={selection}
            onChange={setSelection}
            onBack={() => setStep(0)}
            onDone={(result) => {
              setQuotation(result);
              setStep(2);
            }}
          />
        )}
        {step === 2 && quotation && <SummaryStep quotation={quotation} onRestart={restart} />}

        <p className="mt-8 text-center text-xs text-slate-500">
          Industrias Escolares · Bogotá, Colombia · Valores en COP.{" "}
          <Link to="/login" className="underline">Acceso interno</Link>
        </p>
      </main>
    </div>
  );
}

// --- Step 1: contact data ------------------------------------------------------------------------

const REQUIRED = "Este campo es obligatorio.";
const contactSchema = z.object({
  full_name: z.string().trim().min(1, REQUIRED).max(150, "Máximo 150 caracteres."),
  email: z.string().trim().min(1, REQUIRED).email("Ingrese un correo electrónico válido."),
  phone: z
    .string()
    .trim()
    .min(1, REQUIRED)
    .regex(/^\+?[\d\s()-]{7,30}$/, "Ingrese un teléfono válido (solo números, espacios o +)."),
  institution: z.string().trim().max(200, "Máximo 200 caracteres."),
  tax_id: z
    .string()
    .trim()
    .refine((v) => v === "" || /^[\d.\s-]{5,20}$/.test(v), "Use solo números, puntos y guion."),
  data_consent: z.boolean().refine((v) => v, "Debe autorizar el tratamiento de sus datos para continuar."),
});

function ContactStep({ initial, onNext }: { initial: ContactData | null; onNext: (data: ContactData) => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ContactData>({
    resolver: zodResolver(contactSchema),
    defaultValues: initial ?? {
      full_name: "",
      email: "",
      phone: "",
      institution: "",
      tax_id: "",
      data_consent: false,
    },
  });

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form onSubmit={handleSubmit(onNext)} noValidate className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 lg:col-span-2">
        <div>
          <h1 className="text-2xl font-semibold">Empecemos por conocerte</h1>
          <p className="text-sm text-slate-600">
            Cuéntanos quién solicita la cotización. Después podrás elegir los productos y las cantidades.
          </p>
        </div>
        <TextField label="Nombre completo *" autoComplete="name" error={errors.full_name?.message} {...register("full_name")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Correo electrónico *" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
          <TextField label="Teléfono celular *" inputMode="tel" autoComplete="tel" error={errors.phone?.message} {...register("phone")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Institución o razón social (opcional)" error={errors.institution?.message} {...register("institution")} />
          <TextField label="NIT (opcional)" hint="Si su institución ya es cliente, agiliza el trámite." error={errors.tax_id?.message} {...register("tax_id")} />
        </div>
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" className="mt-1" {...register("data_consent")} />
          <span>
            Autorizo a Industrias Escolares a tratar mis datos personales para atender esta solicitud,
            conforme a la Ley 1581 de 2012.
          </span>
        </label>
        {errors.data_consent && <p className="text-xs text-red-700">{errors.data_consent.message}</p>}
        <Button type="submit">Continuar a productos</Button>
      </form>

      <aside className="h-fit rounded-lg border border-slate-200 bg-white p-6 text-sm">
        <p className="text-lg font-medium">Hola, soy tu asistente</p>
        <p className="mt-2 text-slate-600">
          Te ayudo a preparar tu solicitud sin crear una cuenta. Primero tus datos; luego eliges el
          mobiliario y revisas el resumen antes de enviarlo.
        </p>
        <p className="mt-4 rounded-md bg-amber-50 p-3 text-amber-900">
          La cotización preliminar es un rango estimado: la administradora revisará tu solicitud y
          confirmará precios, condiciones y fecha de despacho.
        </p>
      </aside>
    </div>
  );
}

// --- Step 2: products and quantities -------------------------------------------------------------

function ProductsStep({
  contact,
  selection,
  onChange,
  onBack,
  onDone,
}: {
  contact: ContactData;
  selection: Selection;
  onChange: (selection: Selection) => void;
  onBack: () => void;
  onDone: (quotation: PreliminaryQuotation) => void;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const catalog = usePublicCatalog(search, page);
  const items = useMemo(
    () => [...selection.values()].map(({ product, quantity }) => ({ product_id: product.id, quantity })),
    [selection],
  );
  const estimate = useEstimate(items);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const options = useAssistantOptions();

  const setQuantity = (product: CatalogItem, quantity: number) => {
    const next = new Map(selection);
    if (quantity > 0) next.set(product.id, { product, quantity });
    else next.delete(product.id);
    onChange(next);
  };

  const addProposed = (lines: { product: CatalogItem; quantity: number }[]) => {
    const next = new Map(selection);
    lines.forEach((line) => next.set(line.product.id, line));
    onChange(next);
  };

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      onDone(await quoteApi.request(contact, items));
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Has enviado muchas solicitudes. Intenta de nuevo más tarde.");
      } else {
        setError(err instanceof ApiError ? err.message : "No fue posible conectar con el servidor.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="space-y-4 lg:col-span-2">
        <div>
          <h1 className="text-2xl font-semibold">Elige el mobiliario para tu institución</h1>
          <p className="text-sm text-slate-600">Productos disponibles. Indica la cantidad de cada uno.</p>
        </div>
        {options.data?.free_text_enabled && <FreeTextAssistant onAdd={addProposed} />}
        <input
          aria-label="Buscar producto"
          placeholder="Buscar por nombre o código…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        {catalog.isPending ? (
          <p className="text-sm text-slate-500">Cargando productos…</p>
        ) : !catalog.data || catalog.data.results.length === 0 ? (
          <p className="text-sm text-slate-500">No encontramos productos con esa búsqueda.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {catalog.data.results.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                quantity={selection.get(product.id)?.quantity ?? 0}
                onQuantity={(q) => setQuantity(product, q)}
              />
            ))}
          </ul>
        )}
        {catalog.data && catalog.data.total_pages > 1 && (
          <div className="flex items-center justify-end gap-2 text-sm">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
            <span>Página {catalog.data.page} de {catalog.data.total_pages}</span>
            <Button variant="secondary" disabled={page >= catalog.data.total_pages} onClick={() => setPage(page + 1)}>
              Siguiente
            </Button>
          </div>
        )}
        <Button variant="secondary" onClick={onBack}>← Regresar a mis datos</Button>
      </section>

      <aside className="h-fit space-y-4 rounded-lg border border-slate-200 bg-white p-5 text-sm lg:sticky lg:top-4">
        <h2 className="text-lg font-medium">Tu selección</h2>
        {selection.size === 0 ? (
          <p className="text-slate-500">Aún no has agregado productos.</p>
        ) : (
          <ul className="space-y-2">
            {[...selection.values()].map(({ product, quantity }) => {
              const line = estimate.data?.items.find((i) => i.product_id === product.id);
              return (
                <li key={product.id} className="flex items-start justify-between gap-2">
                  <span>
                    {quantity} × {product.name}
                    <br />
                    <span className="text-xs text-slate-500">
                      {line ? formatRange(line.subtotal_min, line.subtotal_max) : "…"}
                      {line?.price_source === "AI" && " · estimado con IA"}
                    </span>
                  </span>
                  <button type="button" className="text-xs text-red-700 hover:underline" onClick={() => setQuantity(product, 0)}>
                    Quitar
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {estimate.data && selection.size > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-500">Rango estimado</p>
            <p className="text-xl font-semibold">
              {formatRange(estimate.data.total_min, estimate.data.total_max, "Por confirmar")}
            </p>
            {estimate.data.unpriced_items > 0 && (
              <p className="mt-1 text-xs text-amber-800">
                {estimate.data.unpriced_items} producto(s) con precio por confirmar.
              </p>
            )}
            {estimate.data.items.some((i) => i.price_source === "AI") && (
              <p className="mt-1 text-xs text-slate-500">
                «Estimado con IA»: referencia calculada a partir de precios de productos similares.
              </p>
            )}
          </div>
        )}
        {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">{error}</p>}
        <Button className="w-full" disabled={selection.size === 0 || submitting} onClick={submit}>
          {submitting ? "Preparando…" : "Revisar resumen"}
        </Button>
        <p className="text-xs text-slate-500">Preliminar sujeta a aprobación.</p>
      </aside>
    </div>
  );
}

function FreeTextAssistant({
  onAdd,
}: {
  onAdd: (lines: { product: CatalogItem; quantity: number }[]) => void;
}) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});

  const propose = async () => {
    setLoading(true);
    setError(null);
    setProposal(null);
    try {
      const result = await quoteApi.propose(text);
      setProposal(result);
      setChosen(Object.fromEntries(result.items.map((i) => [i.product_id, String(i.quantity)])));
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Has usado el asistente muchas veces. Intenta más tarde o elige en el catálogo.");
      } else {
        setError(err instanceof ApiError ? err.message : "No fue posible conectar con el servidor.");
      }
    } finally {
      setLoading(false);
    }
  };

  const confirm = () => {
    if (!proposal) return;
    onAdd(
      proposal.items
        .filter((item) => item.product_id in chosen && Number(chosen[item.product_id]) > 0)
        .map((item) => ({
          product: {
            id: item.product_id,
            code: item.product_code,
            name: item.description,
            unit_of_measure: item.unit_of_measure,
          },
          quantity: Math.min(100000, Number(chosen[item.product_id])),
        })),
    );
    setProposal(null);
    setText("");
  };

  const toggle = (id: string, quantity: number) => {
    const next = { ...chosen };
    if (id in next) delete next[id];
    else next[id] = String(quantity);
    setChosen(next);
  };

  return (
    <div className="space-y-3 rounded-lg border border-sky-200 bg-sky-50/50 p-4">
      <div>
        <label htmlFor="needs" className="font-medium">¿Prefieres contarnos qué necesitas? (opcional)</label>
        <p className="text-xs text-slate-600">
          Descríbelo con tus palabras y el asistente te propondrá productos del catálogo. Tú decides
          cuáles agregar. No incluyas datos personales: el texto no se guarda.
        </p>
      </div>
      <textarea
        id="needs"
        rows={3}
        maxLength={1000}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Por ejemplo: sillas y mesas para 3 salones de primaria de 35 estudiantes y un tablero por salón"
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={text.trim().length < 10 || loading} onClick={propose}>
          {loading ? "Analizando…" : "Proponer productos"}
        </Button>
        <span className="text-xs text-slate-500">{text.length}/1000</span>
      </div>
      {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {proposal && (
        <div className="space-y-3 rounded-md border border-slate-200 bg-white p-3 text-sm">
          {proposal.items.length === 0 ? (
            <p className="text-slate-600">
              No encontramos productos del catálogo para tu descripción. Búscalos en el catálogo.
            </p>
          ) : (
            <>
              <p className="font-medium">Propuesta del asistente: revisa y confirma</p>
              <ul className="space-y-2">
                {proposal.items.map((item) => {
                  const selected = item.product_id in chosen;
                  return (
                    <li key={item.product_id} className="flex flex-wrap items-center gap-3">
                      <label className="flex flex-1 items-center gap-2">
                        <input type="checkbox" checked={selected} onChange={() => toggle(item.product_id, item.quantity)} />
                        <span>
                          {item.description}{" "}
                          <span className="text-xs text-slate-500">{item.product_code}</span>
                        </span>
                      </label>
                      <input
                        aria-label={`Cantidad de ${item.description}`}
                        inputMode="numeric"
                        disabled={!selected}
                        value={chosen[item.product_id] ?? ""}
                        onChange={(e) => setChosen({ ...chosen, [item.product_id]: e.target.value.replace(/\D/g, "") })}
                        className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-100"
                      />
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          {proposal.unavailable.length > 0 && (
            <p className="text-xs text-amber-800">
              No disponibles en el catálogo: {proposal.unavailable.join(", ")}.
            </p>
          )}
          <div className="flex gap-2">
            {proposal.items.length > 0 && (
              <Button disabled={Object.keys(chosen).length === 0} onClick={confirm}>
                Agregar a mi selección
              </Button>
            )}
            <Button variant="secondary" onClick={() => setProposal(null)}>Descartar</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProductCard({
  product,
  quantity,
  onQuantity,
}: {
  product: CatalogItem;
  quantity: number;
  onQuantity: (quantity: number) => void;
}) {
  const [draft, setDraft] = useState(String(quantity || 1));
  const added = quantity > 0;
  const valid = /^\d+$/.test(draft) && Number(draft) > 0 && Number(draft) <= 100000;

  return (
    <li className={`rounded-lg border bg-white p-4 ${added ? "border-red-300" : "border-slate-200"}`}>
      <p className="font-medium">{product.name}</p>
      <p className="text-xs text-slate-500">{product.code} · {product.unit_of_measure}</p>
      <div className="mt-3 flex items-end gap-2">
        <label className="text-xs text-slate-600">
          Cantidad
          <input
            inputMode="numeric"
            value={draft}
            onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
            className="mt-1 block w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
        <Button variant={added ? "secondary" : "primary"} disabled={!valid} onClick={() => onQuantity(Number(draft))}>
          {added ? "Actualizar" : "Agregar"}
        </Button>
      </div>
      {!valid && <p className="mt-1 text-xs text-red-700">Ingrese una cantidad entre 1 y 100.000.</p>}
    </li>
  );
}

// --- Step 3: summary -----------------------------------------------------------------------------

function SummaryStep({ quotation, onRestart }: { quotation: PreliminaryQuotation; onRestart: () => void }) {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendEmail = async () => {
    setSending(true);
    setError(null);
    try {
      setSentTo((await quoteApi.email(quotation)).sent_to);
    } catch (err) {
      setError(
        `${err instanceof ApiError ? err.message : "No fue posible enviar el correo."} Puede intentarlo de nuevo o descargar el PDF.`,
      );
    } finally {
      setSending(false);
    }
  };

  const downloadPdf = async () => {
    setDownloading(true);
    setError(null);
    try {
      await quoteApi.pdf(quotation);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No fue posible descargar el PDF.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Tu cotización preliminar está lista</h1>
        <p className="text-sm text-slate-600">
          {quotation.number} · Solicitud de {quotation.requester_name}
        </p>
      </div>
      <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
        <strong>Preliminar sujeta a aprobación.</strong> La administradora revisará tu solicitud. Los
        precios, las condiciones y la fecha de despacho se confirman en la cotización formal.
      </p>

      <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">Código / producto</th>
              <th className="px-4 py-3">Cantidad</th>
              <th className="px-4 py-3">Precio unitario</th>
              <th className="px-4 py-3 text-right">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {quotation.items.map((item) => (
              <tr key={item.product_id} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <span className="font-mono text-xs">{item.product_code}</span> · {item.description}
                </td>
                <td className="px-4 py-3">{item.quantity}</td>
                <td className="px-4 py-3">
                  {formatRange(item.unit_price_min, item.unit_price_max)}
                  {item.price_source === "AI" && (
                    <span className="block text-xs text-slate-500">Estimado con IA (productos similares)</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">{formatRange(item.subtotal_min, item.subtotal_max, "Por confirmar")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-4 py-3">
          <span className="text-sm text-slate-600">Total estimado (COP)</span>
          <span className="text-xl font-semibold">
            {formatRange(quotation.total_min, quotation.total_max, "Por confirmar")}
          </span>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Info label="Fecha estimada de despacho">
          {quotation.estimated_dispatch_date
            ? `${formatDateOnly(quotation.estimated_dispatch_date)} (sujeta a confirmación)`
            : "Por confirmar por la empresa"}
        </Info>
        <Info label="Vigencia de la cotización">Hasta el {formatDateOnly(quotation.valid_until)}</Info>
      </div>

      <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-medium">Conserva tu cotización</h2>
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={downloadPdf} disabled={downloading}>
            {downloading ? "Generando…" : "Descargar PDF preliminar"}
          </Button>
          <Button variant="secondary" onClick={sendEmail} disabled={sending}>
            {sending ? "Enviando…" : "Recibir por correo"}
          </Button>
        </div>
        {sentTo && <p className="text-sm text-green-800">Enviamos la cotización a {sentTo}.</p>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <p className="text-xs text-slate-500">
          No necesitas una cuenta. Usa {quotation.number} como referencia al contactarnos.
        </p>
      </section>

      <Button variant="secondary" onClick={onRestart}>Hacer otra solicitud</Button>
    </div>
  );
}

function Info({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 font-medium">{children}</p>
    </div>
  );
}
