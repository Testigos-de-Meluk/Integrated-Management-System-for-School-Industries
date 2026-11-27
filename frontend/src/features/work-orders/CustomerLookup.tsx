import { useState } from "react";

import { CustomerFormModal } from "@/features/customers/CustomerFormModal";
import type { Customer } from "@/features/customers/api";
import { api, ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";

export type ChosenCustomer = { id: string; tax_id: string; name: string };

/**
 * Finds a registered customer by NIT / document (any common format) or registers a new one.
 * Only active customers can be chosen for a work order.
 */
export function CustomerLookup({
  chosen,
  onChoose,
}: {
  chosen: ChosenCustomer | null;
  onChoose: (customer: ChosenCustomer | null) => void;
}) {
  const [taxId, setTaxId] = useState("");
  const [found, setFound] = useState<Customer | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);

  const search = async () => {
    setMessage(null);
    setFound(null);
    try {
      setFound(await api.get<Customer>(`/customers/by-tax-id/${encodeURIComponent(taxId.trim())}/`));
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "No fue posible buscar el cliente.");
    }
  };

  if (chosen) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-3 text-sm">
        <div>
          <p className="font-medium">{chosen.name}</p>
          <p className="text-xs text-slate-500">{chosen.tax_id}</p>
        </div>
        <Button variant="link" onClick={() => onChoose(null)}>
          Cambiar cliente
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm">
      <div className="flex gap-2">
        <input
          aria-label="NIT o documento del cliente"
          placeholder="NIT o documento del cliente"
          className={inputClass}
          value={taxId}
          onChange={(e) => setTaxId(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && taxId.trim()) {
              e.preventDefault();
              void search();
            }
          }}
        />
        <Button variant="secondary" disabled={!taxId.trim()} onClick={search}>
          Buscar
        </Button>
      </div>
      {found && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-3">
          <div>
            <p className="font-medium">{found.name}</p>
            <p className="text-xs text-slate-500">
              {found.tax_id}
              {!found.is_active && " · Inactivo: reactívelo en Clientes para usarlo"}
            </p>
          </div>
          <Button
            disabled={!found.is_active}
            onClick={() => onChoose({ id: found.id, tax_id: found.tax_id, name: found.name })}
          >
            Elegir
          </Button>
        </div>
      )}
      {message && (
        <p role="alert" className="text-red-700">
          {message}
        </p>
      )}
      <p className="text-xs text-slate-500">
        ¿No está registrado?{" "}
        <button type="button" className="text-red-700 hover:underline" onClick={() => setRegistering(true)}>
          Registrar cliente
        </button>{" "}
        y luego búsquelo por su NIT o documento.
      </p>
      <CustomerFormModal open={registering} customer={null} onClose={() => setRegistering(false)} />
    </div>
  );
}
