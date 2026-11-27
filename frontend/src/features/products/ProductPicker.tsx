import { useState } from "react";

import { useProducts } from "./api";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200 disabled:bg-slate-100";

export type PickedProduct = { id: string; code: string; name: string; unit_of_measure: string };

/** Search box over ACTIVE catalog products (quotation review, work orders). */
export function ProductPicker({ onPick }: { onPick: (product: { id: string; code: string; name: string; unit_of_measure: string }) => void }) {
  const [text, setText] = useState("");
  const query = text.trim();
  const { data } = useProducts({ name: query, status: "ACTIVE" }, 1, 8);
  const results = query.length >= 2 ? (data?.results ?? []) : [];

  return (
    <div className="relative mt-4 max-w-md">
      <label htmlFor="add-product" className="mb-1 block text-sm font-medium text-slate-700">
        Agregar producto del catálogo
      </label>
      <input id="add-product" placeholder="Escriba al menos 2 letras del nombre" className={inputClass}
        value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
          {results.map((product) => (
            <li key={product.id}>
              <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                onClick={() => { onPick(product); setText(""); }}>
                <span className="font-medium">{product.name}</span>{" "}
                <span className="text-xs text-slate-500">{product.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.length >= 2 && data && data.results.length === 0 && (
        <p className="mt-1 text-xs text-slate-500">No hay productos activos con ese nombre.</p>
      )}
    </div>
  );
}
