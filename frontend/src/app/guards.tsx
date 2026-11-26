import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
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
      <div className="flex min-h-screen items-center justify-center px-4 text-center text-slate-500">
        {session.retryAt ? <RetryCountdown retryAt={session.retryAt} /> : "Cargando…"}
      </div>
    );
  }
  return children;
}

/** The session check was rate-limited (429): the session is still open, so wait and retry. */
function RetryCountdown({ retryAt }: { retryAt: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.ceil((retryAt - now) / 1000));
  return (
    <p role="status" className="max-w-md">
      Demasiadas solicitudes desde esta conexión.{" "}
      {seconds > 0
        ? `Reintentando en ${seconds} segundo${seconds === 1 ? "" : "s"}…`
        : "Reintentando…"}
    </p>
  );
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
