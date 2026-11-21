import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router";

import { ROLE_LABELS, setDevRole, useDevRole, type Role } from "@/shared/auth/devRole";

const NAV_ITEMS = [
  { to: "/", label: "Inicio", end: true },
  { to: "/catalogo", label: "Catálogo", end: false },
];

export function AppLayout() {
  const role = useDevRole();
  const queryClient = useQueryClient();

  const changeRole = (newRole: Role) => {
    setDevRole(newRole);
    // Data visible to each role may differ: reload everything with the new role.
    void queryClient.invalidateQueries();
  };

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <div className="mb-6">
          <p className="text-lg font-bold text-red-700">Industrias Escolares</p>
          <p className="text-xs tracking-wide text-slate-500 uppercase">Sistema de gestión</p>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm ${
                  isActive ? "bg-red-50 font-medium text-red-700" : "text-slate-700 hover:bg-slate-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <p className="mt-auto rounded-md bg-slate-100 p-3 text-xs text-slate-600">
          Equipo compartido: recuerde cerrar sesión al terminar.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3">
          <nav className="flex gap-3 text-sm md:hidden">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="text-red-700">
                {item.label}
              </NavLink>
            ))}
          </nav>
          <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
            <span title="Temporal: se reemplaza por el inicio de sesión real">Rol de prueba</span>
            <select
              value={role}
              onChange={(event) => changeRole(event.target.value as Role)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
            >
              {(Object.keys(ROLE_LABELS) as Role[]).map((value) => (
                <option key={value} value={value}>
                  {ROLE_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
