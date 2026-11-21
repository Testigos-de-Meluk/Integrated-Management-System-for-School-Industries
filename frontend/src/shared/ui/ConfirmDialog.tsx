import { useState, type ReactNode } from "react";

import { ApiError } from "@/shared/api/http";

import { Button } from "./Button";
import { Modal } from "./Modal";

/** Explicit confirmation before a high-impact action (NFR-03-02). */
export function ConfirmDialog({
  open,
  title,
  confirmLabel,
  danger = false,
  onConfirm,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
  children: ReactNode;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    setError(null);
    onClose();
  };

  const confirm = async () => {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      close();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No fue posible completar la acción.");
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal open={open} title={title} onClose={close}>
      <div className="space-y-4 text-sm">
        <div>{children}</div>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={close}>
            Cancelar
          </Button>
          <Button variant={danger ? "danger" : "primary"} disabled={pending} onClick={confirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
