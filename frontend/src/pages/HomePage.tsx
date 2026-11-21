import { SystemStatus } from "@/features/system/SystemStatus";

export function HomePage() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold text-slate-900">IMSI · Industrias Escolares</h1>
      <p className="mt-1 text-slate-600">Sistema de gestión integral</p>
      <section className="mt-8 rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Estado del sistema</h2>
        <SystemStatus />
      </section>
    </main>
  );
}
