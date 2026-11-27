import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

import {
  FIELD_LABELS,
  STATUS_LABELS,
  TYPE_LABELS,
  useCustomerByTaxId,
  useCustomerStatus,
} from "./api";
import { CustomerFormModal } from "./CustomerFormModal";
import { HistorySection } from "./HistorySection";
import { NotesSection } from "./NotesSection";


/** Unified 360° profile, identified by NIT / document number (FR-02-08, US 2.19 … US 2.24). */
export function CustomerProfilePage() {
  const { taxId = "" } = useParams();
  const { data: customer, isPending, error } = useCustomerByTaxId(taxId);
  const changeStatus = useCustomerStatus();
  const [editing, setEditing] = useState(false);
  const [confirmStatus, setConfirmStatus] = useState(false);

  if (isPending) {
    return <p className="text-slate-500">Cargando ficha del cliente…</p>;
  }
  if (error || !customer) {
    return (
      <div className="mx-auto max-w-2xl rounded-lg bg-red-50 p-6 text-red-800">
        <p>{error instanceof ApiError ? error.message : "No fue posible cargar el cliente."}</p>
        <Link to="/clientes" className="mt-3 inline-block text-sm font-medium underline">
          Volver a clientes
        </Link>
      </div>
    );
  }

  const labels = FIELD_LABELS[customer.customer_type];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">
            <Link to="/clientes" className="hover:underline">Clientes</Link> / Ficha 360
          </p>
          <h1 className="text-2xl font-semibold">{customer.name}</h1>
          <p className="text-sm text-slate-600">
            {labels.taxId} {customer.tax_id} · {TYPE_LABELS[customer.customer_type]}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${
          customer.is_active ? "bg-green-50 text-green-800" : "bg-slate-200 text-slate-700"
        }`}>
          {STATUS_LABELS[customer.status]}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-medium">Datos generales y de contacto</h2>
            {customer.is_active && (
              <Button variant="secondary" onClick={() => setEditing(true)}>Editar datos</Button>
            )}
          </div>
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Field label={labels.name}>{customer.name}</Field>
            <Field label={`${labels.taxId} (no editable)`}>{customer.tax_id}</Field>
            <Field label="Dirección">{customer.address}</Field>
            <Field label="Teléfono principal">{customer.primary_phone}</Field>
            <Field label="Correo electrónico">{customer.email}</Field>
            <Field label="Contacto comercial">{customer.commercial_contact || "—"}</Field>
          </dl>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-2 text-lg font-medium">Estado del cliente</h2>
          <p className="mb-4 text-sm text-slate-600">
            {customer.is_active
              ? "Activo: disponible para cotizaciones y órdenes de trabajo."
              : "Inactivo: no se puede asociar a nuevas cotizaciones ni órdenes. Su ficha e historial siguen disponibles en solo lectura."}
          </p>
          <Button variant={customer.is_active ? "danger" : "primary"} onClick={() => setConfirmStatus(true)}>
            {customer.is_active ? "Desactivar cliente" : "Reactivar cliente"}
          </Button>
        </section>
      </div>

      <HistorySection customerId={customer.id} />

      <NotesSection customerId={customer.id} readOnly={!customer.is_active} />

      <CustomerFormModal open={editing} customer={customer} onClose={() => setEditing(false)} />
      <ConfirmDialog
        open={confirmStatus}
        title={customer.is_active ? "Desactivar cliente" : "Reactivar cliente"}
        confirmLabel={customer.is_active ? "Desactivar" : "Reactivar"}
        danger={customer.is_active}
        onConfirm={() => changeStatus.mutateAsync({ id: customer.id, activate: !customer.is_active })}
        onClose={() => setConfirmStatus(false)}
      >
        {customer.is_active
          ? `¿Desactivar a ${customer.name}? No se podrá usar en nuevas cotizaciones ni órdenes; su historial se conserva.`
          : `¿Reactivar a ${customer.name}? Volverá a estar disponible para nuevas operaciones.`}
      </ConfirmDialog>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-slate-900">{children}</dd>
    </div>
  );
}
