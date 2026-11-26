import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { AIMotion, Badge, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
import { ApiClient, ApiError, errorMessage, isCancelled } from '../api/client';
import type { DocumentAccess, DocumentLimits, DocumentRecord } from '../api/types';
import { Feedback } from './Feedback';
import { DocumentAccessFields } from './DocumentAccessFields';
import { DocumentViewer } from './DocumentViewer';
import { ConfirmationDialog } from './ConfirmationDialog';
const sizeLabel = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${Math.round((bytes / 1024 / 1024) * 10) / 10} MB`
    : bytes >= 1024
      ? `${Math.round((bytes / 1024) * 10) / 10} KB`
      : `${bytes} bytes`;
export function DocumentsPanel({
  api,
  isAdmin,
  onCount,
  uploadRequest,
  onChat,
  membersRevision,
  onDocumentsChange,
}: {
  api: ApiClient;
  isAdmin: boolean;
  onCount?: (count: number) => void;
  uploadRequest?: number;
  onChat?: (document: DocumentRecord) => void;
  membersRevision?: number;
  onDocumentsChange?: (documents: DocumentRecord[] | null, error?: string) => void;
}) {
  const [access, setAccess] = useState<DocumentAccess>({
    visibility: 'company',
    recipient_ids: [],
  });
  const [editing, setEditing] = useState<DocumentRecord | null>(null);
  const [editAccess, setEditAccess] = useState<DocumentAccess>({
    visibility: 'company',
    recipient_ids: [],
  });
  const [savingAccess, setSavingAccess] = useState(false);
  const [preview, setPreview] = useState<DocumentRecord | null>(null);
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const previouslyFailed = useRef(new Set<number>());
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [limits, setLimits] = useState<DocumentLimits | null>(null);
  const [limitsError, setLimitsError] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  useEffect(() => {
    if (uploadRequest && isAdmin) setShowUpload(true);
  }, [uploadRequest, isAdmin]);
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState<DocumentRecord | null>(null);
  const [failedDocumentId, setFailedDocumentId] = useState<number | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);
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
      onDocumentsChange?.(items);
      onCount?.(items.length);
      setError('');
      setUncertain(false);
    } catch (error) {
      if (!isCancelled(error)) {
        setError('Could not load documents. Try again.');
        onDocumentsChange?.(null, errorMessage(error));
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [api, onCount, onDocumentsChange]);
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
  useEffect(() => {
    if (
      !documents?.some((document) => ['queued', 'indexing'].includes(document.index_status || ''))
    )
      return;
    const timer = window.setInterval(() => {
      void load();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [documents, load]);
  useEffect(() => {
    const failed = (documents || []).filter((document) => document.index_status === 'failed');
    const newlyFailed = failed.find((document) => !previouslyFailed.current.has(document.id));
    previouslyFailed.current = new Set(failed.map((document) => document.id));
    if (newlyFailed) {
      setFailedDocumentId(newlyFailed.id);
      setNotice('');
      setError(
        isAdmin
          ? `Upload failed for “${newlyFailed.title}”. Choose Try again beside the document.`
          : `“${newlyFailed.title}” could not be prepared. Ask your administrator to try again.`,
      );
    }
  }, [documents, isAdmin]);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);
  async function tryDocumentAgain(id: number) {
    if (pending.current) return;
    pending.current = true;
    setRetrying(id);
    setError('');
    setNotice('');
    try {
      await api.reindexDocument(id, lifetime.current?.signal);
      previouslyFailed.current.delete(id);
      setFailedDocumentId(null);
      setNotice('Trying again. Your document will be available shortly.');
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setFailedDocumentId(id);
        setError('Upload failed. Please try again.');
      }
    } finally {
      pending.current = false;
      setRetrying(null);
    }
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (pending.current || !limits) return;
    setFailedDocumentId(null);
    if (access.visibility !== 'company' && !access.recipient_ids.length) {
      setError('Select at least one employee before uploading.');
      return;
    }
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
      const result = await api.upload(selected, lifetime.current?.signal, access);
      setSelected(null);
      if (input.current) input.current.value = '';
      setNotice(
        result.index_status === 'failed'
          ? `“${result.title}” could not be prepared. Try again below.`
          : result.index_status === 'indexing'
            ? `“${result.title}” is being prepared.`
            : result.index_status === 'queued'
              ? `“${result.title}” is being uploaded.`
              : `“${result.title}” is ready for questions.`,
      );
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setError(
          error instanceof ApiError && error.uncertain
            ? errorMessage(error)
            : 'Upload failed. Please try again.',
        );
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
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Employee hub / Your knowledge library</Eyebrow>
          <h1 id="documents-heading" className="mt-2 text-3xl font-bold tracking-tight">
            Your documents,{' '}
            <span className="font-editorial font-medium italic text-azure">together.</span>
          </h1>
          <p className="mt-3 text-sm text-muted">
            {isAdmin
              ? 'Share company knowledge, assign personal letters and control employee access.'
              : 'Your personal letters and the company knowledge shared with you, in one place.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {isAdmin && (
            <Button
              aria-expanded={showUpload}
              aria-controls="document-upload-panel"
              disabled={uploading || deleting}
              onClick={() => setShowUpload((value) => !value)}
            >
              {showUpload ? 'Close upload' : 'Upload documents ↗'}
            </Button>
          )}
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
      </div>
      {isAdmin && (
        <div id="document-upload-panel" hidden={!showUpload}>
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
              <DocumentAccessFields
                membersRevision={membersRevision}
                api={api}
                value={access}
                onChange={setAccess}
                disabled={uploading || uncertain}
              />
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
                <Button
                  type="submit"
                  loading={uploading}
                  disabled={!limits || deleting || uncertain}
                >
                  {uploading ? 'Uploading document…' : 'Upload document ↗'}
                </Button>
              </div>
              {uploading && (
                <p role="status" className="mt-3 text-xs text-muted">
                  Uploading your document. Indexing will continue in the background.
                </p>
              )}
            </form>
          </Card>
        </div>
      )}
      <div className="mb-5 space-y-3">
        {(error || notice) && (
          <div
            className="fixed bottom-5 right-5 z-40 w-[min(380px,calc(100vw-40px))] rounded-xl border border-line bg-surface p-3 shadow-lg"
            aria-label="Document notification"
          >
            <Feedback error={!!error}>{error || notice}</Feedback>
            <div className="mt-2 flex gap-2">
              {error && selected && !uncertain && (
                <Button variant="ghost" disabled={uploading} onClick={upload}>
                  Try again
                </Button>
              )}
              {error && isAdmin && !selected && failedDocumentId !== null && !uncertain && (
                <Button
                  variant="ghost"
                  aria-label="Try upload again"
                  disabled={retrying !== null}
                  onClick={() => void tryDocumentAgain(failedDocumentId)}
                >
                  Try again
                </Button>
              )}
              {error && uncertain && (
                <Button variant="ghost" onClick={() => void load()}>
                  Check upload status
                </Button>
              )}
              <Button
                variant="ghost"
                onClick={() => {
                  setError('');
                  setNotice('');
                }}
              >
                Dismiss
              </Button>
            </div>
          </div>
        )}
        {uncertain && (
          <Feedback>Refresh the document list before repeating an upload or deletion.</Feedback>
        )}
      </div>
      {documents && (
        <div className="mb-6 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              ['personal', 'Personal documents'],
              ['company', 'Company knowledge'],
              ['restricted', 'Restricted documents'],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setCategory(value)}
                aria-pressed={category === value}
                className="rounded-2xl border border-line bg-surface p-5 text-left shadow-sm"
              >
                <span className="block text-2xl font-bold text-azure">
                  {documents.filter((d) => (d.visibility || 'company') === value).length}
                </span>
                <span className="text-xs text-muted">{label}</span>
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="min-w-0 flex-1 text-xs font-semibold">
              Find a document
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search offer letters, policies, products…"
                className="mt-2 block w-full rounded-lg border border-line bg-surface p-3 text-sm"
              />
            </label>
            <label className="text-xs font-semibold">
              Show
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-2 block w-full rounded-lg border border-line bg-surface p-3 text-sm font-normal sm:min-w-64"
              >
                <option value="all">All documents</option>
                <option value="personal">Personal</option>
                <option value="company">Company</option>
                <option value="restricted">Restricted</option>
              </select>
            </label>
          </div>
          {documents.length > 0 &&
            !documents.some(
              (d) =>
                (category === 'all' || (d.visibility || 'company') === category) &&
                d.title.toLowerCase().includes(search.toLowerCase()),
            ) && (
              <p role="status" className="text-sm text-muted">
                No documents match your filters.
              </p>
            )}
        </div>
      )}
      {preview && (
        <DocumentViewer
          key={preview.id}
          api={api}
          document={preview}
          onClose={() => setPreview(null)}
        />
      )}
      {editing && (
        <Card className="mb-5 p-5">
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (savingAccess) return;
              if (editAccess.visibility !== 'company' && !editAccess.recipient_ids.length) {
                setError('Select at least one employee before saving access.');
                return;
              }
              setSavingAccess(true);
              setError('');
              try {
                await api.updateAccess(editing.id, editAccess, lifetime.current?.signal);
                setEditing(null);
                setPreview(null);
                setNotice('Document access updated.');
                await load();
              } catch (err) {
                if (!isCancelled(err)) setError('Could not complete this request. Try again.');
              } finally {
                setSavingAccess(false);
              }
            }}
          >
            <h2 className="font-bold">Manage access · {editing.title}</h2>
            <DocumentAccessFields
              membersRevision={membersRevision}
              api={api}
              value={editAccess}
              onChange={setEditAccess}
              disabled={savingAccess}
            />
            <div className="flex gap-3">
              <Button type="submit" disabled={savingAccess}>
                Save access
              </Button>
              <Button variant="ghost" disabled={savingAccess} onClick={() => setEditing(null)}>
                Cancel access changes
              </Button>
            </div>
          </form>
        </Card>
      )}
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
                ? 'Add your first document above. Once the upload finishes, you can ask questions about it.'
                : 'Your administrator can add documents for this workspace.'}
            </p>
          </div>
          <AIMotion kind="network" className="hidden h-32 sm:block" />
        </Card>
      ) : (
        <div>
          <ul aria-label="Workspace documents" className="space-y-3">
            {documents
              .filter(
                (d) =>
                  (category === 'all' || (d.visibility || 'company') === category) &&
                  d.title.toLowerCase().includes(search.toLowerCase()),
              )
              .map((document) => (
                <li key={document.id}>
                  <Card className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex items-center gap-2">
                        <span aria-hidden="true" className="text-azure">
                          ▤
                        </span>
                        <h2 className="break-words text-sm font-bold">{document.title}</h2>
                      </div>
                      <p className="text-[11px] text-muted">
                        Added {new Date(document.created_at).toLocaleDateString()}
                      </p>
                      {document.index_status && document.index_status !== 'ready' && (
                        <p role="status" className="mt-2 text-xs text-muted">
                          {document.index_status === 'queued'
                            ? 'Uploading document…'
                            : document.index_status === 'indexing'
                              ? 'Preparing document…'
                              : 'Upload failed. Try again.'}
                        </p>
                      )}
                      {!!document.extraction_warnings?.length && (
                        <details className="mt-2 text-xs text-muted">
                          <summary>Source extraction notes</summary>
                          <ul>
                            {document.extraction_warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                    <Badge
                      className="access-chip"
                      tone={
                        document.visibility === 'restricted'
                          ? 'violet'
                          : document.visibility === 'company' || !document.visibility
                            ? 'teal'
                            : 'azure'
                      }
                    >
                      {document.visibility === 'personal'
                        ? 'Personal'
                        : document.visibility === 'restricted'
                          ? 'Restricted'
                          : 'Company knowledge'}
                    </Badge>
                    <div className="flex flex-wrap items-center gap-3">
                      <Button variant="secondary" onClick={() => setPreview(document)}>
                        View
                      </Button>
                      <Button variant="secondary" onClick={() => onChat?.(document)}>
                        Ask about this
                      </Button>
                      {isAdmin && document.index_status === 'failed' && (
                        <Button
                          variant="ghost"
                          disabled={retrying !== null || uploading || deleting || uncertain}
                          onClick={() => void tryDocumentAgain(document.id)}
                        >
                          {retrying === document.id ? 'Trying again…' : 'Try again'}
                        </Button>
                      )}
                      {isAdmin && (
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setEditing(document);
                            setEditAccess({
                              visibility: document.visibility || 'company',
                              recipient_ids: document.recipient_ids || [],
                            });
                          }}
                        >
                          Manage access
                        </Button>
                      )}
                      {isAdmin && (
                        <Button
                          variant="ghost"
                          disabled={uploading || deleting || uncertain}
                          aria-label={`Delete ${document.title}`}
                          title={`Delete ${document.title}`}
                          onClick={() => {
                            setConfirm(document);
                            setDeleteError('');
                          }}
                        >
                          <svg
                            aria-hidden="true"
                            className="text-[#883C3C]"
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.7"
                          >
                            <path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" />
                          </svg>
                        </Button>
                      )}
                    </div>
                  </Card>
                </li>
              ))}
          </ul>
        </div>
      )}
      {confirm && (
        <ConfirmationDialog
          title="Delete this document?"
          confirmLabel="Delete document"
          cancelLabel="Keep document"
          busyLabel="Deleting…"
          busy={deleting}
          error={deleteError}
          uncertain={uncertain}
          onCancel={() => {
            if (!deleting) {
              setConfirm(null);
              if (uncertain) void load();
            }
          }}
          onConfirm={() => void remove()}
        >
          “{confirm.title}” and its source passages will be removed from future answers.
        </ConfirmationDialog>
      )}
    </section>
  );
}
