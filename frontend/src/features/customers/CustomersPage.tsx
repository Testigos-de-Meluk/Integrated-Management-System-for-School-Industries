import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";

import {
  STATUS_LABELS,
  TYPE_LABELS,
  useCustomers,
  type CustomerFilters,
  type CustomerStatus,
} from "./api";
import { CustomerFormModal } from "./CustomerFormModal";

const PAGE_SIZE = 20;
const EMPTY: CustomerFilters = { tax_id: "", name: "", commercial_contact: "", status: "" };
const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";

/** Customer list (US 2.14, US 2.15). */
export function CustomersPage() {
  const [draft, setDraft] = useState<CustomerFilters>(EMPTY);
  const [filters, setFilters] = useState<CustomerFilters>(EMPTY);
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const { data, isPending, isError, error, isFetching } = useCustomers(filters, page, PAGE_SIZE);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };

  const emptyMessage = filters.tax_id
    ? "No existe un cliente con ese NIT o número de documento."
    : Object.values(filters).some(Boolean)
      ? "No se encontraron clientes con los filtros aplicados."
      : "No hay clientes registrados.";

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Inicio / Clientes</p>
          <h1 className="text-2xl font-semibold">Clientes</h1>
          <p className="text-sm text-slate-600">
            Busque por NIT o documento para abrir la ficha 360. Los clientes no se eliminan: se
            desactivan.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>Registrar cliente</Button>
      </div>

      <form
        onSubmit={search}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        <input aria-label="NIT o documento" placeholder="NIT o documento" className={inputClass}
          value={draft.tax_id} onChange={(e) => setDraft({ ...draft, tax_id: e.target.value })} />
        <input aria-label="Nombre o razón social" placeholder="Nombre o razón social" className={inputClass}
          value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <input aria-label="Contacto comercial" placeholder="Contacto comercial" className={inputClass}
          value={draft.commercial_contact}
          onChange={(e) => setDraft({ ...draft, commercial_contact: e.target.value })} />
        <select aria-label="Estado" className={inputClass} value={draft.status}
          onChange={(e) => setDraft({ ...draft, status: e.target.value as CustomerStatus | "" })}>
          <option value="">Todos los estados</option>
          <option value="ACTIVE">Activo</option>
          <option value="INACTIVE">Inactivo</option>
        </select>
        <div className="flex gap-2">
          <Button type="submit" className="flex-1">Buscar</Button>
          <Button variant="secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>
            Limpiar
          </Button>
        </div>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">NIT / documento</th>
              <th className="px-4 py-3">Nombre o razón social</th>
              <th className="px-4 py-3">Tipo</th>
              <th className="px-4 py-3">Contacto comercial</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3 text-right">Acción</th>
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Message>Cargando clientes…</Message>
            ) : isError ? (
              <Message tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar los clientes."}
              </Message>
            ) : data.results.length === 0 ? (
              <Message>{emptyMessage}</Message>
            ) : (
              data.results.map((customer) => (
                <tr key={customer.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-mono text-xs">{customer.tax_id}</td>
                  <td className="px-4 py-3 font-medium">{customer.name}</td>
                  <td className="px-4 py-3">{TYPE_LABELS[customer.customer_type]}</td>
                  <td className="px-4 py-3 text-slate-600">{customer.commercial_contact || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      customer.is_active ? "bg-green-50 text-green-800" : "bg-slate-100 text-slate-600"
                    }`}>
                      {STATUS_LABELS[customer.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/clientes/${encodeURIComponent(customer.tax_id)}`}
                      className="text-sm font-medium text-red-700 hover:underline">
                      Ver ficha
                    </Link>
                  </td>
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
            {Math.min(data.page * data.page_size, data.count)} de {data.count} clientes
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

      <CustomerFormModal open={formOpen} customer={null} onClose={() => setFormOpen(false)} />
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
