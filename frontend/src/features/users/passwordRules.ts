import { z } from "zod";

/** Same rule as the backend (FR-01-11); the backend remains the final authority. */
export const PASSWORD_RULE =
  "Mínimo 8 caracteres, con al menos una mayúscula, una minúscula, un número y un carácter especial.";

export function satisfiesPolicy(password: string): boolean {
  return (
    password.length >= 8 &&
    password.length <= 64 &&
    // Same rule as the backend's str.isupper()/str.islower(): any cased letter, not just A-Z.
    /\p{Lu}/u.test(password) &&
    /\p{Ll}/u.test(password) &&
    /\d/.test(password) &&
    /[^\p{L}\p{N}\s]/u.test(password)
  );
}

/** Adds the "manual password" check to a form schema that has password + generate_password. */
export function refinePassword<T extends { password?: string; generate_password: boolean }>(
  values: T,
  ctx: z.RefinementCtx,
) {
  if (values.generate_password) return;
  if (!values.password) {
    ctx.addIssue({
      code: "custom",
      path: ["password"],
      message: "Ingrese una contraseña o solicite una generada automáticamente.",
    });
  } else if (!satisfiesPolicy(values.password)) {
    ctx.addIssue({ code: "custom", path: ["password"], message: PASSWORD_RULE });
  }
}
