import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { TextField } from "@/shared/ui/TextField";

import { useChangePassword, type UserAccount } from "./api";
import { PASSWORD_RULE, refinePassword } from "./passwordRules";

const schema = z
  .object({ password: z.string().optional(), generate_password: z.boolean() })
  .superRefine(refinePassword);
type Values = z.infer<typeof schema>;

/** US 1.19: new password (manual or generated), emailed to the user. */
export function PasswordModal({ user, onClose }: { user: UserAccount | null; onClose: () => void }) {
  const changePassword = useChangePassword();
  const [generalError, setGeneralError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const generate = watch("generate_password");

  useEffect(() => {
    if (user) {
      reset({ password: "", generate_password: true });
      setGeneralError(null);
    }
  }, [user, reset]);

  const onSubmit = async (values: Values) => {
    if (!user) return;
    try {
      await changePassword.mutateAsync({
        id: user.id,
        generate_password: values.generate_password,
        password: values.generate_password ? undefined : values.password,
      });
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors.password) {
        setError("password", { message: error.fieldErrors.password[0] });
      } else {
        setGeneralError(error instanceof ApiError ? error.message : "No fue posible conectar con el servidor.");
      }
    }
  };

  return (
    <Modal open={user !== null} title="Cambiar contraseña" onClose={onClose}>
      {user && (
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3 text-sm">
          <p>
            Cuenta: <span className="font-medium">{user.full_name}</span> ({user.email})
          </p>
          <label className="flex items-center gap-2">
            <input type="radio" checked={generate} onChange={() => setValue("generate_password", true)} />
            Generar una contraseña nueva (recomendado)
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" checked={!generate} onChange={() => setValue("generate_password", false)} />
            Ingresarla manualmente
          </label>
          {!generate && (
            <TextField
              label="Nueva contraseña"
              type="password"
              autoComplete="new-password"
              hint={PASSWORD_RULE}
              error={errors.password?.message}
              {...register("password")}
            />
          )}
          <p className="rounded-md bg-amber-50 p-3 text-amber-900">
            La nueva contraseña se enviará por correo y se cerrarán las sesiones abiertas de esta
            cuenta.
          </p>
          {generalError && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-red-800">
              {generalError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Guardando…" : "Cambiar contraseña"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
