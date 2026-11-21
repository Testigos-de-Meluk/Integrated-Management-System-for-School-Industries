import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { refreshSession } from "@/shared/api/http";
import { hasPermission, useSession, type Permission } from "@/shared/auth/session";

/** On page load, tries to restore the session from the httpOnly refresh cookie. */
export function SessionBootstrap({ children }: { children: ReactNode }) {
  const session = useSession();
  const queryClient = useQueryClient();
  const started = useRef(false);

  useEffect(() => {
    if (!started.current) {
      started.current = true;
      void refreshSession();
    }
  }, []);

  // Never keep another user's data in memory after logout or session expiry.
  useEffect(() => {
    if (session.status === "anonymous") {
      queryClient.clear();
    }
  }, [session.status, queryClient]);

  if (session.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        Cargando…
      </div>
    );
  }
  return children;
}

/** Protected area: without a session, go to the login screen (US 1.3.4). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();
  if (session.status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

/** Screens only some roles can open. The backend denies the data anyway. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission;
  children: ReactNode;
}) {
  const { user } = useSession();
  if (!hasPermission(user, permission)) {
    return (
      <div className="mx-auto max-w-2xl rounded-lg bg-red-50 p-6 text-red-800">
        No tiene permisos para realizar esta acción.
      </div>
    );
  }
  return children;
}
