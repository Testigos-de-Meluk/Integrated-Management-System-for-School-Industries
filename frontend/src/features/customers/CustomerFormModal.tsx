import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "@/shared/forms/serverErrors";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { TextField } from "@/shared/ui/TextField";

import {
  FIELD_LABELS,
  TYPE_LABELS,
  useCreateCustomer,
  useUpdateCustomer,
  type Customer,
  type CustomerType,
} from "./api";

const REQUIRED = "Este campo es obligatorio.";

const contactFields = {
  name: z.string().trim().min(1, REQUIRED).max(200, "Máximo 200 caracteres."),
  address: z.string().trim().min(1, REQUIRED).max(250, "Máximo 250 caracteres."),
  primary_phone: z
    .string()
    .trim()
    .min(1, REQUIRED)
    .regex(/^\+?[\d\s()-]{7,30}$/, "Ingrese un teléfono válido (solo números, espacios o +)."),
  email: z.string().trim().min(1, REQUIRED).email("Ingrese un correo electrónico válido."),
  commercial_contact: z.string().trim().max(150, "Máximo 150 caracteres."),
};

const createSchema = z.object({
  customer_type: z.enum(["NATURAL_PERSON", "LEGAL_ENTITY"]),
  tax_id: z.string().trim().min(1, REQUIRED),
  ...contactFields,
});
type CreateValues = z.infer<typeof createSchema>;

const editSchema = z.object(contactFields);
type EditValues = z.infer<typeof editSchema>;

/** Registers a customer (US 2.16) or edits its contact data (US 2.17: type and NIT are fixed). */
export function CustomerFormModal({
  open,
  customer,
  onClose,
}: {
  open: boolean;
  customer: Customer | null;
  onClose: () => void;
}) {
  return (
    <Modal open={open} title={customer ? "Editar cliente" : "Registrar cliente"} onClose={onClose}>
      {customer ? <EditForm customer={customer} onDone={onClose} /> : <CreateForm onDone={onClose} />}
    </Modal>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const createCustomer = useCreateCustomer();
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
      customer_type: "LEGAL_ENTITY",
      tax_id: "",
      name: "",
      address: "",
      primary_phone: "",
      email: "",
      commercial_contact: "",
    },
  });
  const type = watch("customer_type");
  const labels = FIELD_LABELS[type];

  const onSubmit = async (values: CreateValues) => {
    setGeneralError(null);
    try {
      await createCustomer.mutateAsync(values);
      onDone();
    } catch (error) {
      setGeneralError(applyServerErrors(error, values, setError));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Tipo de cliente *</legend>
        <div className="flex gap-4">
          {(Object.keys(TYPE_LABELS) as CustomerType[]).map((option) => (
            <label key={option} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={type === option}
                onChange={() => setValue("customer_type", option)}
              />
              {TYPE_LABELS[option]}
            </label>
          ))}
        </div>
      </fieldset>
      <TextField
        label={`${labels.taxId} *`}
        hint={`${labels.taxIdHint} No se podrá modificar después.`}
        error={errors.tax_id?.message}
        {...register("tax_id")}
      />
      <ContactInputs register={register} errors={errors} nameLabel={labels.name} />
      <Footer error={generalError} submitting={isSubmitting} label="Registrar cliente" onCancel={onDone} />
    </form>
  );
}

function EditForm({ customer, onDone }: { customer: Customer; onDone: () => void }) {
  const updateCustomer = useUpdateCustomer();
  const [generalError, setGeneralError] = useState<string | null>(null);
  const labels = FIELD_LABELS[customer.customer_type];
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: customer.name,
      address: customer.address,
      primary_phone: customer.primary_phone,
      email: customer.email,
      commercial_contact: customer.commercial_contact,
    },
  });

  const onSubmit = async (values: EditValues) => {
    setGeneralError(null);
    try {
      await updateCustomer.mutateAsync({ id: customer.id, ...values });
      onDone();
    } catch (error) {
      setGeneralError(applyServerErrors(error, values, setError));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          id="customer_type"
          name="customer_type"
          label="Tipo de cliente"
          value={TYPE_LABELS[customer.customer_type]}
          disabled
          readOnly
        />
        <TextField
          id="tax_id"
          name="tax_id"
          label={labels.taxId}
          value={customer.tax_id}
          disabled
          readOnly
          hint="No se puede modificar."
        />
      </div>
      <ContactInputs register={register} errors={errors} nameLabel={labels.name} />
      <p className="text-xs text-slate-500">
        Los cambios aplican a la ficha y a las operaciones nuevas; los registros anteriores conservan
        los datos con los que se crearon.
      </p>
      <Footer error={generalError} submitting={isSubmitting} label="Guardar cambios" onCancel={onDone} />
    </form>
  );
}

// --- Shared pieces ------------------------------------------------------------------------------

type ContactErrors = Partial<Record<keyof EditValues, { message?: string }>>;

function ContactInputs({
  register,
  errors,
  nameLabel,
}: {
  // Both forms share these fields; typed loosely so each form can pass its own register.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: (name: keyof EditValues) => any;
  errors: ContactErrors;
  nameLabel: string;
}) {
  return (
    <>
      <TextField label={`${nameLabel} *`} error={errors.name?.message} {...register("name")} />
      <TextField
        label="Dirección (fiscal o de domicilio) *"
        error={errors.address?.message}
        {...register("address")}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="Teléfono principal *"
          inputMode="tel"
          error={errors.primary_phone?.message}
          {...register("primary_phone")}
        />
        <TextField label="Correo electrónico *" type="email" error={errors.email?.message} {...register("email")} />
      </div>
      <TextField
        label="Contacto comercial (opcional)"
        hint="Por ejemplo: Laura Méndez · 310 456 7890"
        error={errors.commercial_contact?.message}
        {...register("commercial_contact")}
      />
    </>
  );
}

function Footer({
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
