import { useState, type FormEvent, type ReactNode } from "react";

import { ApiError } from "@/shared/api/http";
import { hasPermission, useDevRole } from "@/shared/auth/devRole";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";

import {
  STATUS_LABELS,
  useChangeProductStatus,
  useProducts,
  type Product,
  type ProductFilters,
  type ProductStatus,
} from "./api";
import { ProductFormModal } from "./ProductFormModal";

const PAGE_SIZE = 20;
const EMPTY_FILTERS: ProductFilters = { code: "", name: "", unit_of_measure: "", status: "" };

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";

export function ProductsPage() {
  const role = useDevRole();
  const canEdit = hasPermission(role, "CATALOG_EDIT");

  const [draftFilters, setDraftFilters] = useState<ProductFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<ProductFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error, isFetching } = useProducts(filters, page, PAGE_SIZE);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [statusTarget, setStatusTarget] = useState<Product | null>(null);

  const hasActiveFilters = Object.values(filters).some(Boolean);

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draftFilters);
    setPage(1);
  };

  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (product: Product) => {
    setEditing(product);
    setFormOpen(true);
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Inicio / Catálogo</p>
          <h1 className="text-2xl font-semibold">Catálogo de productos</h1>
          <p className="text-sm text-slate-600">
            Repositorio de productos. Los precios se definen en cada cotización.
          </p>
        </div>
        {canEdit && <Button onClick={openCreate}>Nuevo producto</Button>}
      </div>

      <form
        onSubmit={applyFilters}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        <input
          aria-label="Código"
          placeholder="Código"
          className={inputClass}
          value={draftFilters.code}
          onChange={(e) => setDraftFilters({ ...draftFilters, code: e.target.value })}
        />
        <input
          aria-label="Descripción"
          placeholder="Descripción"
          className={inputClass}
          value={draftFilters.name}
          onChange={(e) => setDraftFilters({ ...draftFilters, name: e.target.value })}
        />
        <input
          aria-label="Unidad de medida"
          placeholder="Unidad de medida"
          className={inputClass}
          value={draftFilters.unit_of_measure}
          onChange={(e) => setDraftFilters({ ...draftFilters, unit_of_measure: e.target.value })}
        />
        <select
          aria-label="Estado"
          className={inputClass}
          value={draftFilters.status}
          onChange={(e) =>
            setDraftFilters({ ...draftFilters, status: e.target.value as ProductStatus | "" })
          }
        >
          <option value="">Todos los estados</option>
          <option value="ACTIVE">Activo</option>
          <option value="INACTIVE">Inactivo</option>
        </select>
        <div className="flex gap-2">
          <Button type="submit" className="flex-1">
            Buscar
          </Button>
          <Button variant="secondary" onClick={clearFilters}>
            Limpiar
          </Button>
        </div>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">Código</th>
              <th className="px-4 py-3">Descripción</th>
              <th className="px-4 py-3">Unidad</th>
              <th className="px-4 py-3">Estado</th>
              {canEdit && <th className="px-4 py-3 text-right">Acciones</th>}
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <MessageRow colSpan={canEdit ? 5 : 4}>Cargando productos…</MessageRow>
            ) : isError ? (
              <MessageRow colSpan={canEdit ? 5 : 4} tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar el catálogo."}
              </MessageRow>
            ) : data.results.length === 0 ? (
              <MessageRow colSpan={canEdit ? 5 : 4}>
                {hasActiveFilters
                  ? "No se encontraron productos con los filtros aplicados."
                  : "No hay productos registrados en el catálogo."}
              </MessageRow>
            ) : (
              data.results.map((product) => (
                <tr key={product.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-mono text-xs">{product.code}</td>
                  <td className="px-4 py-3">{product.name}</td>
                  <td className="px-4 py-3">{product.unit_of_measure}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={product.status} />
                  </td>
                  {canEdit && (
                    <td className="space-x-4 px-4 py-3 text-right whitespace-nowrap">
                      <Button variant="link" onClick={() => openEdit(product)}>
                        Editar
                      </Button>
                      <Button variant="link" onClick={() => setStatusTarget(product)}>
                        {product.status === "ACTIVE" ? "Desactivar" : "Activar"}
                      </Button>
                    </td>
                  )}
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
            {Math.min(data.page * data.page_size, data.count)} de {data.count} productos
          </span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Anterior
            </Button>
            <span>
              Página {data.page} de {data.total_pages}
            </span>
            <Button
              variant="secondary"
              disabled={page >= data.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}

      {!canEdit && (
        <p className="mt-6 rounded-md bg-blue-50 p-3 text-sm text-blue-900">
          Vista de solo consulta: su rol no permite registrar ni modificar productos.
        </p>
      )}

      <ProductFormModal open={formOpen} product={editing} onClose={() => setFormOpen(false)} />
      <ChangeStatusModal product={statusTarget} onClose={() => setStatusTarget(null)} />
    </div>
  );
}

function StatusBadge({ status }: { status: ProductStatus }) {
  const styles =
    status === "ACTIVE" ? "bg-green-50 text-green-800" : "bg-slate-100 text-slate-600";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

function MessageRow({
  colSpan,
  tone = "info",
  children,
}: {
  colSpan: number;
  tone?: "info" | "error";
  children: ReactNode;
}) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className={`px-4 py-10 text-center ${tone === "error" ? "text-red-700" : "text-slate-500"}`}
      >
        {children}
      </td>
    </tr>
  );
}

/** Explicit confirmation before a high-impact action (NFR-03-02). */
function ChangeStatusModal({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const changeStatus = useChangeProductStatus();
  const activate = product?.status === "INACTIVE";

  const confirm = async () => {
    if (!product) return;
    try {
      await changeStatus.mutateAsync({ id: product.id, activate });
      onClose();
    } catch {
      // The error message is shown below.
    }
  };

  return (
    <Modal
      open={product !== null}
      title={activate ? "Activar producto" : "Desactivar producto"}
      onClose={() => {
        changeStatus.reset();
        onClose();
      }}
    >
      {product && (
        <div className="space-y-4 text-sm">
          <p>
            {activate
              ? `¿Activar ${product.code} · ${product.name}? Volverá a estar disponible para nuevas cotizaciones.`
              : `¿Desactivar ${product.code} · ${product.name}? No se podrá seleccionar en nuevas cotizaciones, pero seguirá visible en el historial.`}
          </p>
          {changeStatus.error && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">
              {changeStatus.error.message}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              variant={activate ? "primary" : "danger"}
              disabled={changeStatus.isPending}
              onClick={confirm}
            >
              {activate ? "Activar" : "Desactivar"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
