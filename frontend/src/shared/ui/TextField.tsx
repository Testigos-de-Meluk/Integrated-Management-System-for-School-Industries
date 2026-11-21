import { forwardRef, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
};

/** Labelled input that shows how to fix a validation error (NFR-03-02). */
export const TextField = forwardRef<HTMLInputElement, Props>(function TextField(
  { label, error, hint, id, className = "", ...props },
  ref,
) {
  const inputId = id ?? props.name;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={Boolean(error)}
        className={`w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 disabled:bg-slate-100 disabled:text-slate-500 ${
          error
            ? "border-red-400 focus:ring-red-200"
            : "border-slate-300 focus:border-slate-400 focus:ring-slate-200"
        }`}
        {...props}
      />
      {error ? (
        <p className="mt-1 text-xs text-red-700">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
});
