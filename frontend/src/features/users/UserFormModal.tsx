import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, type FieldValues, type Path, type UseFormSetError } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/shared/api/http";
import { ROLE_LABELS, type Role } from "@/shared/auth/session";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { TextField } from "@/shared/ui/TextField";

import { useCreateUser, useUpdateUser, type UserAccount } from "./api";
import { PASSWORD_RULE, refinePassword } from "./passwordRules";

const REQUIRED = "Este campo es obligatorio.";
const ROLES = Object.keys(ROLE_LABELS) as Role[];

const profileFields = {
  full_name: z.string().trim().min(1, REQUIRED).max(150, "Máximo 150 caracteres."),
  job_title: z.string().trim().min(1, REQUIRED).max(100, "Máximo 100 caracteres."),
  role: z.enum(["SUPERADMIN", "ADMIN", "OPERATOR"], { message: "Seleccione un rol." }),
};

const createSchema = z
  .object({
    ...profileFields,
    email: z.string().trim().min(1, REQUIRED).email("Ingrese un correo electrónico válido."),
    password: z.string().optional(),
    generate_password: z.boolean(),
  })
  .superRefine(refinePassword);
type CreateValues = z.infer<typeof createSchema>;

const editSchema = z.object(profileFields);
type EditValues = z.infer<typeof editSchema>;

/** Creates an account (US 1.17) or edits name, job title and role (US 1.18; email is fixed). */
export function UserFormModal({
  open,
  user,
  currentUserId,
  onClose,
}: {
  open: boolean;
  user: UserAccount | null;
  currentUserId: string | undefined;
  onClose: () => void;
}) {
  return (
    <Modal open={open} title={user ? "Editar cuenta" : "Crear cuenta"} onClose={onClose}>
      {/* The modal only renders its content while open, so each form starts fresh. */}
      {user ? (
        <EditForm user={user} isSelf={user.id === currentUserId} onDone={onClose} />
      ) : (
        <CreateForm onDone={onClose} />
      )}
    </Modal>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const createUser = useCreateUser();
  const [generalError, setGeneralError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      full_name: "",
      email: "",
      job_title: "",
      role: "OPERATOR",
      password: "",
      generate_password: true,
    },
  });
  const generate = watch("generate_password");

  const onSubmit = async (values: CreateValues) => {
    setGeneralError(null);
    try {
      await createUser.mutateAsync({
        ...values,
        password: values.generate_password ? undefined : values.password,
      });
      onDone();
    } catch (error) {
      setGeneralError(applyServerErrors(error, values, setError));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <TextField label="Nombre completo *" error={errors.full_name?.message} {...register("full_name")} />
      <TextField
        label="Correo electrónico *"
        type="email"
        hint="Será su usuario de acceso y no se podrá modificar."
        error={errors.email?.message}
        {...register("email")}
      />
      <TextField label="Cargo *" error={errors.job_title?.message} {...register("job_title")} />
      <RoleSelect register={register("role")} disabled={false} />

      <fieldset className="space-y-2 rounded-md border border-slate-200 p-3">
        <legend className="px-1 text-sm font-medium text-slate-700">Contraseña inicial</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" checked={generate} onChange={() => setValue("generate_password", true)} />
          Generarla automáticamente (recomendado)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" checked={!generate} onChange={() => setValue("generate_password", false)} />
          Ingresarla manualmente
        </label>
        {!generate && (
          <TextField
            label="Contraseña"
            type="password"
            autoComplete="new-password"
            hint={PASSWORD_RULE}
            error={errors.password?.message}
            {...register("password")}
          />
        )}
        <p className="text-xs text-slate-500">
          Las credenciales se envían al correo del usuario. En su primer ingreso vinculará su
          aplicación autenticadora.
        </p>
      </fieldset>

      <FormFooter error={generalError} submitting={isSubmitting} label="Crear cuenta" onCancel={onDone} />
    </form>
  );
}

function EditForm({ user, isSelf, onDone }: { user: UserAccount; isSelf: boolean; onDone: () => void }) {
  const updateUser = useUpdateUser();
  const [generalError, setGeneralError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { full_name: user.full_name, job_title: user.job_title, role: user.role },
  });

  const onSubmit = async (values: EditValues) => {
    setGeneralError(null);
    try {
      await updateUser.mutateAsync({ id: user.id, ...values });
      onDone();
    } catch (error) {
      setGeneralError(applyServerErrors(error, values, setError));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <TextField label="Nombre completo *" error={errors.full_name?.message} {...register("full_name")} />
      <TextField
        label="Correo electrónico"
        value={user.email}
        disabled
        readOnly
        hint="El correo identifica la cuenta y no se puede modificar."
      />
      <TextField label="Cargo *" error={errors.job_title?.message} {...register("job_title")} />
      <RoleSelect register={register("role")} disabled={isSelf} />
      <FormFooter error={generalError} submitting={isSubmitting} label="Guardar cambios" onCancel={onDone} />
    </form>
  );
}

// --- Shared pieces ------------------------------------------------------------------------------

function RoleSelect({
  register,
  disabled,
}: {
  register: ReturnType<ReturnType<typeof useForm<EditValues>>["register"]>;
  disabled: boolean;
}) {
  return (
    <div>
      <label htmlFor="role" className="mb-1 block text-sm font-medium text-slate-700">
        Rol *
      </label>
      <select
        id="role"
        disabled={disabled}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm disabled:bg-slate-100"
        {...register}
      >
        {ROLES.map((role) => (
          <option key={role} value={role}>
            {ROLE_LABELS[role]}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-slate-500">
        {disabled
          ? "No puede cambiar su propio rol."
          : "Tres perfiles fijos; no se asignan permisos individuales."}
      </p>
    </div>
  );
}

function FormFooter({
  error,
  submitting,
  label,
  onCancel,
}: {
  error: string | null;
  submitting: boolean;
  label: string;
  onCancel: () => void;
}) {
  return (
    <>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Guardando…" : label}
        </Button>
      </div>
    </>
  );
}

/** Puts server field errors under their inputs; returns a general message when none applies. */
function applyServerErrors<T extends FieldValues>(
  error: unknown,
  values: T,
  setError: UseFormSetError<T>,
): string | null {
  if (!(error instanceof ApiError)) {
    return "No fue posible conectar con el servidor. Intente de nuevo.";
  }
  const fields = Object.entries(error.fieldErrors).filter(([field]) => field in values);
  fields.forEach(([field, messages]) => setError(field as Path<T>, { message: messages[0] }));
  return fields.length === 0 ? error.message : null;
}
