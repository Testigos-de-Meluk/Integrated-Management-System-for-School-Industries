import { useState } from "react";

import { ApiError } from "@/shared/api/http";

import { Button } from "./Button";
import { Modal } from "./Modal";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200 disabled:bg-slate-100";

/** Asks for a mandatory reason (reject a quotation, annul a work order…). */
export function ReasonDialog({
  open, title, label, hint, confirmLabel, danger = false, warning, onConfirm, onClose,
}: {
  open: boolean;
  title: string;
  label: string;
  hint: string;
  confirmLabel: string;
  danger?: boolean;
  /** Shown above the reason, e.g. "anúlela también en Odoo". */
  warning?: string;
  onConfirm: (reason: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const close = () => {
    setReason("");
    setError(null);
    onClose();
  };

  const confirm = async () => {
    if (!reason.trim()) {
      setError("El motivo es obligatorio.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      close();
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldMessages = Object.values(err.fieldErrors).flat();
        setError(fieldMessages.length ? fieldMessages.join(" ") : err.message);
      } else {
        setError("No fue posible conectar con el servidor. Intente de nuevo.");
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={title} onClose={close}>
      <div className="space-y-3 text-sm">
        {warning && <p className="rounded-md bg-amber-50 p-3 text-amber-900">{warning}</p>}
        <label htmlFor="reason" className="block font-medium text-slate-700">{label}</label>
        <textarea id="reason" rows={4} maxLength={1000} className={inputClass} value={reason}
          onChange={(e) => setReason(e.target.value)} />
        <p className="text-xs text-slate-500">{hint}</p>
        {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={close}>Cancelar</Button>
          <Button variant={danger ? "danger" : "primary"} disabled={pending} onClick={confirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
