import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "@/shared/forms/serverErrors";
import { Button } from "@/shared/ui/Button";
import { Modal } from "@/shared/ui/Modal";
import { TextField } from "@/shared/ui/TextField";

import { useCreateProduct, useUpdateProduct, type Product } from "./api";

const REQUIRED = "Este campo es obligatorio.";

// Same rules as the backend domain; the server remains the final authority.
const schema = z.object({
  code: z
    .string()
    .trim()
    .min(1, REQUIRED)
    .max(30, "Máximo 30 caracteres.")
    .regex(/^[A-Za-z0-9][A-Za-z0-9-]*$/, "Use solo letras, números y guiones (por ejemplo, SIL-001)."),
  name: z.string().trim().min(1, REQUIRED).max(200, "Máximo 200 caracteres."),
  unit_of_measure: z.string().trim().min(1, REQUIRED).max(30, "Máximo 30 caracteres."),
});

type FormValues = z.infer<typeof schema>;

/** Registers a new product, or edits name and unit of an existing one (the code is read-only). */
export function ProductFormModal({
  open,
  product,
  onClose,
}: {
  open: boolean;
  product: Product | null;
  onClose: () => void;
}) {
  const isEdit = product !== null;
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const [generalError, setGeneralError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      reset({
        code: product?.code ?? "",
        name: product?.name ?? "",
        unit_of_measure: product?.unit_of_measure ?? "Unidad",
      });
      setGeneralError(null);
    }
  }, [open, product, reset]);

  const onSubmit = async (values: FormValues) => {
    setGeneralError(null);
    try {
      if (product) {
        await updateProduct.mutateAsync({
          id: product.id,
          name: values.name,
          unit_of_measure: values.unit_of_measure,
        });
      } else {
        await createProduct.mutateAsync(values);
      }
      onClose();
    } catch (error) {
      setGeneralError(applyServerErrors(error, values, setError));
    }
  };

  return (
    <Modal open={open} title={isEdit ? "Editar producto" : "Nuevo producto"} onClose={onClose}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <TextField
          label="Código *"
          disabled={isEdit}
          hint={isEdit ? "El código no se puede modificar." : "Ejemplo: SIL-001"}
          error={errors.code?.message}
          {...register("code")}
        />
        <TextField label="Descripción o nombre *" error={errors.name?.message} {...register("name")} />
        <TextField
          label="Unidad de medida *"
          list="units-of-measure"
          error={errors.unit_of_measure?.message}
          {...register("unit_of_measure")}
        />
        <datalist id="units-of-measure">
          <option value="Unidad" />
          <option value="Juego" />
          <option value="Par" />
        </datalist>

        {generalError && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
            {generalError}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Guardando…" : isEdit ? "Guardar cambios" : "Registrar producto"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
