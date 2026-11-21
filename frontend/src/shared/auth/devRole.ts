/**
 * TEMPORARY role selector, until the authentication module exists.
 *
 * The chosen role is sent to the API in the `X-Dev-Role` header (the backend only accepts it in
 * development). When login is implemented, this file is replaced by the authenticated session.
 */
import { useSyncExternalStore } from "react";

export type Role = "SUPERADMIN" | "ADMIN" | "OPERATOR";

export const ROLE_LABELS: Record<Role, string> = {
  SUPERADMIN: "Superadministrador",
  ADMIN: "Administrador",
  OPERATOR: "Operador",
};

export type Permission =
  | "CATALOG_VIEW"
  | "CATALOG_EDIT"
  | "CUSTOMER_MANAGE"
  | "QUOTATION_MANAGE"
  | "EXPORT_QUEUE_MANAGE"
  | "WORK_ORDER_MANAGE";

// Mirrors backend/modules/shared_kernel/domain/security.py (used only to show or hide actions;
// the backend always enforces permissions).
const OPERATOR_PERMISSIONS: Permission[] = [
  "CATALOG_VIEW",
  "CUSTOMER_MANAGE",
  "EXPORT_QUEUE_MANAGE",
  "WORK_ORDER_MANAGE",
];

export function hasPermission(role: Role, permission: Permission): boolean {
  return role !== "OPERATOR" || OPERATOR_PERMISSIONS.includes(permission);
}

const STORAGE_KEY = "imsi.devRole";
const listeners = new Set<() => void>();

function readStoredRole(): Role {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "SUPERADMIN" || stored === "ADMIN" || stored === "OPERATOR") {
      return stored;
    }
  } catch {
    // Storage may be unavailable (private mode): fall back to the default role.
  }
  return "SUPERADMIN";
}

let currentRole: Role = readStoredRole();

export function getDevRole(): Role {
  return currentRole;
}

export function setDevRole(role: Role): void {
  currentRole = role;
  try {
    window.localStorage.setItem(STORAGE_KEY, role);
  } catch {
    // Ignore: the role still applies for this session.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDevRole(): Role {
  return useSyncExternalStore(subscribe, getDevRole);
}
