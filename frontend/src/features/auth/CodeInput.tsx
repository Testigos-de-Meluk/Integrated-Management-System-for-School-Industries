import { useId } from "react";

/** 6-digit code from the authenticator app. Only digits are kept (US 1.3.3). */
export function CodeInput({
  value,
  onChange,
  error,
  autoFocus = true,
}: {
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  autoFocus?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        Código de verificación
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
        inputMode="numeric"
        autoComplete="one-time-code"
        autoFocus={autoFocus}
        placeholder="000000"
        aria-invalid={Boolean(error)}
        className={`w-full rounded-md border px-3 py-3 text-center font-mono text-2xl tracking-[0.5em] outline-none focus:ring-2 ${
          error ? "border-red-400 focus:ring-red-200" : "border-slate-300 focus:ring-slate-200"
        }`}
      />
      <p className="mt-1 text-xs text-slate-500">
        Seis dígitos de su aplicación autenticadora. Nunca llega por correo ni por mensaje de texto.
      </p>
    </div>
  );
}
