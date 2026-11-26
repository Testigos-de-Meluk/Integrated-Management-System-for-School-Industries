import { useState } from "react";

import { ApiError } from "@/shared/api/http";
import { Button } from "@/shared/ui/Button";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";

import { useAddNote, useDeleteNote, useEditNote, useNotes, type Note } from "./api";

const MAX_LENGTH = 2000;
const dateFormat = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Bogota",
});

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "No fue posible completar la acción.";
}

/** Internal commercial notes of a customer (US 2.21 … US 2.24). */
export function NotesSection({ customerId, readOnly }: { customerId: string; readOnly: boolean }) {
  const [page, setPage] = useState(1);
  const { data, isError, isPending } = useNotes(customerId, page);
  const addNote = useAddNote();
  const deleteNote = useDeleteNote();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Note | null>(null);

  const add = async () => {
    setError(null);
    if (!text.trim()) {
      setError("La nota no puede estar vacía.");
      return;
    }
    try {
      await addNote.mutateAsync({ customerId, content: text });
      setText("");
      setPage(1);
    } catch (err) {
      setError(messageOf(err));
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-medium">Notas privadas</h2>
      <p className="mb-4 text-xs text-slate-500">
        Solo para el equipo interno: nunca se incluyen en PDF ni en correos al cliente.
      </p>

      {readOnly ? (
        <p className="mb-4 rounded-md bg-slate-100 p-3 text-sm text-slate-600">
          El cliente está inactivo: su ficha es de solo lectura.
        </p>
      ) : (
        <div className="mb-5 space-y-2">
          <label htmlFor="new-note" className="block text-sm font-medium text-slate-700">
            Agregar nota
          </label>
          <textarea
            id="new-note"
            rows={3}
            maxLength={MAX_LENGTH}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Escriba una nota para el equipo…"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200"
          />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">{text.length}/{MAX_LENGTH}</span>
            <Button onClick={add} disabled={addNote.isPending}>
              {addNote.isPending ? "Guardando…" : "Agregar nota"}
            </Button>
          </div>
        </div>
      )}

      {isError ? (
        <p role="alert" className="text-sm text-red-700">
          No fue posible cargar las notas. Intente de nuevo.
        </p>
      ) : isPending ? (
        <p className="text-sm text-slate-500">Cargando notas…</p>
      ) : !data || data.results.length === 0 ? (
        <p className="text-sm text-slate-500">Este cliente no tiene notas registradas.</p>
      ) : (
        <ul className="space-y-3">
          {data.results.map((note) => (
            <NoteItem
              key={note.id}
              note={note}
              customerId={customerId}
              readOnly={readOnly}
              onDelete={() => setToDelete(note)}
            />
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span>Página {data.page} de {data.total_pages}</span>
          <Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
            Siguiente
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Eliminar nota"
        confirmLabel="Eliminar"
        danger
        onConfirm={() => deleteNote.mutateAsync({ customerId, noteId: toDelete!.id })}
        onClose={() => setToDelete(null)}
      >
        ¿Eliminar esta nota de {toDelete?.author_name}? Dejará de verse en la ficha; su contenido
        queda registrado en la bitácora de auditoría.
      </ConfirmDialog>
    </section>
  );
}

function NoteItem({
  note,
  customerId,
  readOnly,
  onDelete,
}: {
  note: Note;
  customerId: string;
  readOnly: boolean;
  onDelete: () => void;
}) {
  const editNote = useEditNote();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.content);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setError(null);
    if (!text.trim()) {
      setError("La nota no puede estar vacía.");
      return;
    }
    try {
      await editNote.mutateAsync({ customerId, noteId: note.id, content: text });
      setEditing(false);
    } catch (err) {
      setError(messageOf(err));
    }
  };

  return (
    <li className="rounded-md border border-slate-100 bg-slate-50 p-3">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-xs text-slate-500">
        <span>
          <span className="font-medium text-slate-700">{note.author_name}</span> ·{" "}
          {dateFormat.format(new Date(note.created_at))}
          {note.is_edited && note.updated_at && (
            <> · editada por {note.updated_by_name} el {dateFormat.format(new Date(note.updated_at))}</>
          )}
        </span>
        {!readOnly && !editing && (
          <span className="flex gap-3">
            {note.can_edit && (
              <Button variant="link" onClick={() => { setText(note.content); setEditing(true); }}>
                Editar
              </Button>
            )}
            <Button variant="link" onClick={onDelete}>Eliminar</Button>
          </span>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            rows={3}
            maxLength={MAX_LENGTH}
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Editar nota"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditing(false)}>Cancelar</Button>
            <Button onClick={save} disabled={editNote.isPending}>Guardar</Button>
          </div>
        </div>
      ) : (
        <p className="text-sm whitespace-pre-wrap text-slate-800">{note.content}</p>
      )}
    </li>
  );
}
