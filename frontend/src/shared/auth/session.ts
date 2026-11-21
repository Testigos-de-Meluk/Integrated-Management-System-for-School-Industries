/**
 * Session state of the browser tab.
 *
 * - The ACCESS token lives only in memory (this module). It is never written to localStorage, so a
 *   malicious script cannot read it from storage, and it disappears when the tab is closed.
 * - The REFRESH token is an httpOnly cookie set by the backend: JavaScript can't read it at all.
 *   On page load the app asks /api/auth/refresh/ for a new access token (see http.ts).
 */
import { useSyncExternalStore } from "react";

export type Role = "SUPERADMIN" | "ADMIN" | "OPERATOR";

export const ROLE_LABELS: Record<Role, string> = {
  SUPERADMIN: "Superadministrador",
  ADMIN: "Administrador",
  OPERATOR: "Operador",
};

export type Permission =
  | "USER_MANAGE"
  | "BACKUP_MANAGE"
  | "BACKUP_RESTORE"
  | "CATALOG_VIEW"
  | "CATALOG_EDIT"
  | "CUSTOMER_MANAGE"
  | "QUOTATION_MANAGE"
  | "EXPORT_QUEUE_MANAGE"
  | "WORK_ORDER_MANAGE"
  | "AUDIT_LOG_VIEW"
  | "PRICE_HISTORY_IMPORT";

export type CurrentUser = {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  permissions: Permission[];
};

export type SessionState = {
  /** "loading" while the app checks whether the refresh cookie still opens a session. */
  status: "loading" | "authenticated" | "anonymous";
  user: CurrentUser | null;
  /** Message for the login screen, e.g. "Su sesión ha caducado por inactividad". */
  notice: string | null;
};

let accessToken: string | null = null;
let state: SessionState = { status: "loading", user: null, notice: null };
const listeners = new Set<() => void>();

function setState(next: SessionState) {
  state = next;
  listeners.forEach((listener) => listener());
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getSessionState(): SessionState {
  return state;
}

export function startSession(token: string, user: CurrentUser): void {
  accessToken = token;
  setState({ status: "authenticated", user, notice: null });
}

/** Ends the session in this tab. ``notice`` is shown on the login screen. */
export function endSession(notice: string | null = null): void {
  accessToken = null;
  setState({ status: "anonymous", user: null, notice });
}

export function clearNotice(): void {
  if (state.notice) setState({ ...state, notice: null });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSession(): SessionState {
  return useSyncExternalStore(subscribe, getSessionState);
}

/** Only shows or hides actions: the backend always enforces permissions. */
export function hasPermission(user: CurrentUser | null, permission: Permission): boolean {
  return Boolean(user?.permissions.includes(permission));
}
