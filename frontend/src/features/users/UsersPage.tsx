import { useState, type FormEvent, type ReactNode } from "react";

import { ApiError } from "@/shared/api/http";
import { ROLE_LABELS, useSession, type Role } from "@/shared/auth/session";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

import {
  STATUS_LABELS,
  useUserAction,
  useUsers,
  type AccountStatus,
  type UserAccount,
  type UserFilters,
} from "./api";
import { PasswordModal } from "./PasswordModal";
import { UserFormModal } from "./UserFormModal";

const PAGE_SIZE = 20;
const EMPTY: UserFilters = { name: "", email: "", job_title: "", role: "", status: "" };
const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200";
const dateFormat = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

type PendingAction = { user: UserAccount; action: "activate" | "deactivate" | "unlock" };

/** Accounts and permissions (US 1.15 … US 1.23). Administrador and Superadministrador only. */
export function UsersPage() {
  const { user: me } = useSession();
  const [draft, setDraft] = useState<UserFilters>(EMPTY);
  const [filters, setFilters] = useState<UserFilters>(EMPTY);
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error, isFetching } = useUsers(filters, page, PAGE_SIZE);
  const userAction = useUserAction();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UserAccount | null>(null);
  const [passwordFor, setPasswordFor] = useState<UserAccount | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const search = (event: FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Inicio / Cuentas y permisos</p>
          <h1 className="text-2xl font-semibold">Cuentas y permisos</h1>
          <p className="text-sm text-slate-600">
            Tres perfiles fijos. Las cuentas no se eliminan: se desactivan.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          Crear cuenta
        </Button>
      </div>

      <form
        onSubmit={search}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-6"
      >
        <input aria-label="Nombre" placeholder="Nombre" className={inputClass} value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <input aria-label="Correo" placeholder="Correo" className={inputClass} value={draft.email}
          onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        <input aria-label="Cargo" placeholder="Cargo" className={inputClass} value={draft.job_title}
          onChange={(e) => setDraft({ ...draft, job_title: e.target.value })} />
        <select aria-label="Rol" className={inputClass} value={draft.role}
          onChange={(e) => setDraft({ ...draft, role: e.target.value as Role | "" })}>
          <option value="">Todos los roles</option>
          {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
            <option key={role} value={role}>{ROLE_LABELS[role]}</option>
          ))}
        </select>
        <select aria-label="Estado" className={inputClass} value={draft.status}
          onChange={(e) => setDraft({ ...draft, status: e.target.value as AccountStatus | "" })}>
          <option value="">Todos los estados</option>
          <option value="ACTIVE">Activo</option>
          <option value="INACTIVE">Inactivo</option>
        </select>
        <div className="flex gap-2">
          <Button type="submit" className="flex-1">Buscar</Button>
          <Button variant="secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>
            Limpiar
          </Button>
        </div>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="bg-slate-100 text-xs tracking-wide text-slate-600 uppercase">
            <tr>
              <th className="px-4 py-3">Nombre / correo</th>
              <th className="px-4 py-3">Cargo</th>
              <th className="px-4 py-3">Rol</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3">Último acceso</th>
              <th className="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className={isFetching && !isPending ? "opacity-60" : ""}>
            {isPending ? (
              <Message>Cargando cuentas…</Message>
            ) : isError ? (
              <Message tone="error">
                {error instanceof ApiError ? error.message : "No fue posible cargar las cuentas."}
              </Message>
            ) : data.results.length === 0 ? (
              <Message>No se encontraron cuentas con los filtros aplicados.</Message>
            ) : (
              data.results.map((account) => {
                const isMe = account.id === me?.id;
                return (
                  <tr key={account.id} className="border-t border-slate-100 align-top">
                    <td className="px-4 py-3">
                      <p className="font-medium">
                        {account.full_name} {isMe && <span className="text-xs text-slate-500">(usted)</span>}
                      </p>
                      <p className="text-xs text-slate-500">{account.email}</p>
                    </td>
                    <td className="px-4 py-3">{account.job_title}</td>
                    <td className="px-4 py-3">{ROLE_LABELS[account.role]}</td>
                    <td className="space-y-1 px-4 py-3">
                      <Badge tone={account.status === "ACTIVE" ? "green" : "slate"}>
                        {STATUS_LABELS[account.status]}
                      </Badge>
                      {account.is_locked && <Badge tone="amber">Bloqueada</Badge>}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {account.last_access_at
                        ? dateFormat.format(new Date(account.last_access_at))
                        : "Sin ingresos registrados"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="flex justify-end gap-3">
                        <Button variant="link" onClick={() => { setEditing(account); setFormOpen(true); }}>
                          Editar
                        </Button>
                        <Button variant="link" onClick={() => setPasswordFor(account)}>
                          Contraseña
                        </Button>
                        {account.is_locked && (
                          <Button variant="link" onClick={() => setPending({ user: account, action: "unlock" })}>
                            Desbloquear
                          </Button>
                        )}
                        {account.status === "ACTIVE" ? (
                          <Button variant="link" disabled={isMe}
                            title={isMe ? "No puede desactivar su propia cuenta" : undefined}
                            onClick={() => setPending({ user: account, action: "deactivate" })}>
                            Desactivar
                          </Button>
                        ) : (
                          <Button variant="link" onClick={() => setPending({ user: account, action: "activate" })}>
                            Reactivar
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {data && data.count > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <span>
            Mostrando {(data.page - 1) * data.page_size + 1}–
            {Math.min(data.page * data.page_size, data.count)} de {data.count} cuentas
          </span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
            <span>Página {data.page} de {data.total_pages}</span>
            <Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
              Siguiente
            </Button>
          </div>
        </div>
      )}

      <UserFormModal open={formOpen} user={editing} currentUserId={me?.id} onClose={() => setFormOpen(false)} />
      <PasswordModal user={passwordFor} onClose={() => setPasswordFor(null)} />
      <ConfirmDialog
        open={pending !== null}
        title={
          pending?.action === "deactivate"
            ? "Desactivar cuenta"
            : pending?.action === "activate"
              ? "Reactivar cuenta"
              : "Desbloquear cuenta"
        }
        confirmLabel={
          pending?.action === "deactivate" ? "Desactivar" : pending?.action === "activate" ? "Reactivar" : "Desbloquear"
        }
        danger={pending?.action === "deactivate"}
        onConfirm={() => userAction.mutateAsync({ id: pending!.user.id, action: pending!.action })}
        onClose={() => setPending(null)}
      >
        {pending?.action === "deactivate" &&
          `¿Desactivar la cuenta de ${pending.user.full_name}? Se cerrarán sus sesiones y no podrá ingresar. Sus registros se conservan.`}
        {pending?.action === "activate" &&
          `¿Reactivar la cuenta de ${pending.user.full_name}? Podrá ingresar de nuevo con su rol actual.`}
        {pending?.action === "unlock" &&
          `¿Desbloquear la cuenta de ${pending.user.full_name}? Podrá intentar ingresar de inmediato.`}
      </ConfirmDialog>
    </div>
  );
}

function Badge({ tone, children }: { tone: "green" | "slate" | "amber"; children: ReactNode }) {
  const styles = {
    green: "bg-green-50 text-green-800",
    slate: "bg-slate-100 text-slate-600",
    amber: "bg-amber-50 text-amber-800",
  }[tone];
  return <span className={`mr-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}>{children}</span>;
}

function Message({ tone = "info", children }: { tone?: "info" | "error"; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={6} className={`px-4 py-10 text-center ${tone === "error" ? "text-red-700" : "text-slate-500"}`}>
        {children}
      </td>
    </tr>
  );
}
