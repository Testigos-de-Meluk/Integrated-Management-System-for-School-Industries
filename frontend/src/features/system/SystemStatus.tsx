import { useHealth } from "./useHealth";

const LABELS: Record<string, string> = {
  database: "Base de datos",
  redis: "Cola de tareas (Redis)",
};

export function SystemStatus() {
  const { data, isPending, isError } = useHealth();

  if (isPending) {
    return <p className="text-slate-500">Consultando el estado del sistema…</p>;
  }
  if (isError) {
    return <p className="text-red-700">No fue posible conectar con el servidor.</p>;
  }

  return (
    <ul className="space-y-2">
      <li className="font-medium">
        Servidor: {data.status === "ok" ? "operativo" : "con fallas"}
      </li>
      {Object.entries(data.checks).map(([name, state]) => (
        <li key={name} className={state === "ok" ? "text-green-700" : "text-red-700"}>
          {LABELS[name] ?? name}: {state === "ok" ? "disponible" : "no disponible"}
        </li>
      ))}
    </ul>
  );
}
