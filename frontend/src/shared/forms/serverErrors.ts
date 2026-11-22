import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/shared/api/http";

/**
 * Puts the API's field errors (`{"errors": {"email": ["..."]}}`) under their inputs.
 * Returns a general message when no field matches (or the server could not be reached).
 */
export function applyServerErrors<T extends FieldValues>(
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
