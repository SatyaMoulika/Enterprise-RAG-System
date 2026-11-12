import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { AIMotion, Badge, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
import { ApiClient, ApiError, errorMessage, isCancelled } from '../api/client';
import type { DocumentLimits, DocumentRecord } from '../api/types';
import { Feedback } from './Feedback';
const sizeLabel = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${Math.round((bytes / 1024 / 1024) * 10) / 10} MB`
    : bytes >= 1024
      ? `${Math.round((bytes / 1024) * 10) / 10} KB`
      : `${bytes} bytes`;
function DeleteDialog({
  document,
  busy,
  error,
  uncertain,
  onCancel,
  onDelete,
}: {
  document: DocumentRecord;
  busy: boolean;
  error: string;
  uncertain: boolean;
  onCancel: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="delete-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      className="m-auto w-[calc(100%_-_2rem)] max-w-md rounded-xl border border-line bg-surface p-6 text-ink shadow-xl"
    >
      <h2 id="delete-title" className="text-xl font-bold">
        Delete this document?
      </h2>
      <p className="my-4 break-words text-sm leading-6 text-muted">
        “{document.title}” and its indexed excerpts will be removed from future answers.
      </p>
      {error && <Feedback error>{error}</Feedback>}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" disabled={busy} onClick={onCancel} autoFocus>
          {uncertain ? 'Close and refresh' : 'Keep document'}
        </Button>
        <Button loading={busy} disabled={uncertain} onClick={onDelete}>
          {busy ? 'Deleting…' : 'Delete document'}
        </Button>
      </div>
    </dialog>
  );
}
export function DocumentsPanel({
  api,
  isAdmin,
  onCount,
}: {
  api: ApiClient;
  isAdmin: boolean;
  onCount: (count: number) => void;
}) {
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [limits, setLimits] = useState<DocumentLimits | null>(null);
  const [limitsError, setLimitsError] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState<DocumentRecord | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const loader = useRef<AbortController | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    loader.current?.abort();
    const controller = new AbortController();
    loader.current = controller;
    setLoading(true);
    try {
      const items = await api.documents(controller.signal);
      if (controller.signal.aborted) return;
      setDocuments(items);
      onCount(items.length);
      setError('');
      setUncertain(false);
    } catch (error) {
      if (!isCancelled(error)) setError(errorMessage(error));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [api, onCount]);
  const loadLimits = useCallback(
    async (signal: AbortSignal) => {
      try {
        const value = await api.limits(signal);
        setLimits(value);
        setLimitsError('');
      } catch (error) {
        if (!isCancelled(error)) setLimitsError(errorMessage(error));
      }
    },
    [api],
  );
  useEffect(() => {
    lifetime.current = new AbortController();
    void load();
    void loadLimits(lifetime.current.signal);
    return () => {
      loader.current?.abort();
      lifetime.current?.abort();
    };
  }, [load, loadLimits]);
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (pending.current || !limits) return;
    if (!selected) {
      setError('Choose a PDF or text document first.');
      return;
    }
    const extension = selected.name.slice(selected.name.lastIndexOf('.')).toLowerCase();
    if (!limits.allowed_extensions.includes(extension)) {
      setError('Choose a supported PDF or UTF-8 text document.');
      return;
    }
    if (selected.size > limits.max_upload_bytes) {
      setError(`Choose a file no larger than ${sizeLabel(limits.max_upload_bytes)}.`);
      return;
    }
    pending.current = true;
    setUploading(true);
    setError('');
    setNotice('');
    try {
      const result = await api.upload(selected, lifetime.current?.signal);
      setSelected(null);
      if (input.current) input.current.value = '';
      setNotice(`“${result.title}” is indexed and ready for questions.`);
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setError(errorMessage(error));
        setUncertain(error instanceof ApiError && error.uncertain);
      }
    } finally {
      pending.current = false;
      if (!lifetime.current?.signal.aborted) setUploading(false);
    }
  }
  async function remove() {
    if (!confirm || pending.current) return;
    pending.current = true;
    setDeleting(true);
    setDeleteError('');
    setNotice('');
    try {
      await api.removeDocument(confirm.id, lifetime.current?.signal);
      setNotice(`“${confirm.title}” was deleted.`);
      setConfirm(null);
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setDeleteError(errorMessage(error));
        setUncertain(error instanceof ApiError && error.uncertain);
      }
    } finally {
      pending.current = false;
      if (!lifetime.current?.signal.aborted) setDeleting(false);
    }
  }
  return (
    <section aria-labelledby="documents-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow>Documents / Shared workspace knowledge</Eyebrow>
          <h1 id="documents-heading" className="mt-2 text-3xl font-bold tracking-tight">
            Your source material.
          </h1>
          <p className="mt-2 text-xs text-muted">
            {isAdmin
              ? 'Upload and manage the documents your workspace can search.'
              : 'Browse the documents your administrator has shared.'}
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={loading || uploading || deleting}
          onClick={() => {
            void load();
            if (lifetime.current) void loadLimits(lifetime.current.signal);
          }}
        >
          {loading ? 'Refreshing…' : 'Refresh documents'}
        </Button>
      </div>
      {isAdmin && (
        <Card className="mb-6 bg-soft/35 p-5">
          <form onSubmit={upload} aria-label="Upload document">
            <label className="block text-sm font-bold" htmlFor="upload-file">
              Add a document
            </label>
            <p className="mb-4 mt-2 text-xs leading-6 text-muted">
              {limits
                ? `Text-based PDFs and UTF-8 text files, up to ${sizeLabel(limits.max_upload_bytes)}. Scanned PDFs need OCR first.`
                : 'Loading supported upload limits…'}
            </p>
            {limitsError && (
              <div className="mb-4">
                <Feedback error>{limitsError} Use Refresh documents to try again.</Feedback>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-4">
              <input
                ref={input}
                id="upload-file"
                type="file"
                accept={limits?.allowed_extensions.join(',') || '.pdf,.txt'}
                disabled={!limits || uploading || deleting || uncertain}
                onChange={(event) => {
                  setSelected(event.target.files?.[0] || null);
                  setError('');
                }}
                className="min-w-0 flex-1 rounded-lg border border-line bg-surface p-3 text-xs file:mr-3 file:rounded file:border-0 file:bg-soft file:px-3 file:py-2 file:text-azure"
              />
              <Button type="submit" loading={uploading} disabled={!limits || deleting || uncertain}>
                {uploading ? 'Indexing document…' : 'Upload and index ↗'}
              </Button>
            </div>
            {uploading && (
              <p role="status" className="mt-3 text-xs text-muted">
                Extracting and indexing your document. This may take a moment.
              </p>
            )}
          </form>
        </Card>
      )}
      <div className="mb-5 space-y-3">
        {error && <Feedback error>{error}</Feedback>}
        {uncertain && (
          <Feedback>Refresh the document list before repeating an upload or deletion.</Feedback>
        )}
        {notice && <Feedback>{notice}</Feedback>}
      </div>
      {documents === null ? (
        <p role="status" className="py-8 text-center text-sm text-muted">
          {loading
            ? 'Loading workspace documents…'
            : 'Document list is unavailable. Refresh to try again.'}
        </p>
      ) : documents.length === 0 ? (
        <Card className="grid items-center gap-4 p-8 sm:grid-cols-[1fr_150px]">
          <div>
            <h2 className="text-lg font-bold">No documents yet.</h2>
            <p className="mt-2 text-xs leading-6 text-muted">
              {isAdmin
                ? 'Add your first document above. Once indexing succeeds, you can ask questions about it.'
                : 'Your administrator can add documents for this workspace.'}
            </p>
          </div>
          <AIMotion kind="network" className="hidden h-32 sm:block" />
        </Card>
      ) : (
        <ul aria-label="Workspace documents" className="space-y-3">
          {documents.map((document) => (
            <li key={document.id}>
              <Card className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <span aria-hidden="true" className="text-azure">
                      ▤
                    </span>
                    <h2 className="break-words text-sm font-bold">{document.title}</h2>
                  </div>
                  <p className="text-[11px] text-muted">
                    Added {new Date(document.created_at).toLocaleDateString()} · Document #
                    {document.id}
                  </p>
                </div>
                <Badge>Stored</Badge>
                {isAdmin && (
                  <Button
                    variant="ghost"
                    disabled={uploading || deleting || uncertain}
                    aria-label={`Delete ${document.title}`}
                    onClick={() => {
                      setConfirm(document);
                      setDeleteError('');
                    }}
                  >
                    Delete
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
      {confirm && (
        <DeleteDialog
          document={confirm}
          busy={deleting}
          error={deleteError}
          uncertain={uncertain}
          onCancel={() => {
            if (!deleting) {
              setConfirm(null);
              if (uncertain) void load();
            }
          }}
          onDelete={() => void remove()}
        />
      )}
    </section>
  );
}
