import { useState } from "react";
import { NavLink, Outlet } from "react-router";

import { authApi } from "@/features/auth/api";
import {
  endSession,
  getSessionState,
  hasPermission,
  ROLE_LABELS,
  useSession,
  type Permission,
} from "@/shared/auth/session";

import { useActivityTracker } from "./useActivityTracker";

type NavItem = { to: string; label: string; end?: boolean; permission?: Permission };

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Inicio", end: true },
  { to: "/catalogo", label: "Catálogo", permission: "CATALOG_VIEW" },
  { to: "/clientes", label: "Clientes", permission: "CUSTOMER_MANAGE" },
  { to: "/cotizaciones", label: "Cotizaciones", permission: "QUOTATION_MANAGE" },
  { to: "/cuentas", label: "Cuentas y permisos", permission: "USER_MANAGE" },
];

export function AppLayout() {
  const { user } = useSession();
  const [loggingOut, setLoggingOut] = useState(false);
  useActivityTracker();

  const items = NAV_ITEMS.filter((item) => !item.permission || hasPermission(user, item.permission));

  const logout = async () => {
    setLoggingOut(true);
    try {
      await authApi.logout();
    } catch {
      // Even if the request fails, this tab forgets the session.
    }
    // Another path (inactivity, token reuse) may have closed it with a reason: keep that notice.
    if (getSessionState().status !== "anonymous") endSession(null);
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-2 text-sm ${
      isActive ? "bg-red-50 font-medium text-red-700" : "text-slate-700 hover:bg-slate-100"
    }`;

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <div className="mb-6">
          <p className="text-lg font-bold text-red-700">Industrias Escolares</p>
          <p className="text-xs tracking-wide text-slate-500 uppercase">Sistema de gestión</p>
        </div>
        <nav className="flex flex-col gap-1">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-md bg-slate-100 p-3 text-xs text-slate-600">
          <p className="font-medium">PC compartido</p>
          <p>Cierre automático tras 15 minutos de inactividad.</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
          <nav className="flex flex-wrap gap-3 text-sm md:hidden">
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="text-red-700">
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            {user && (
              <div className="text-right leading-tight">
                <p className="text-sm font-medium">{user.full_name}</p>
                <p className="text-xs text-slate-500">{ROLE_LABELS[user.role]}</p>
              </div>
            )}
            <button
              type="button"
              onClick={logout}
              disabled={loggingOut}
              className="text-sm font-medium text-red-700 hover:underline disabled:text-slate-400"
            >
              Cerrar sesión
            </button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
