import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="mt-4 inline-block text-red-700 underline">
        Volver al inicio
      </Link>
    </main>
  );
}
