import { useEffect, useRef, useState } from 'react';
import { Button } from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import type { DocumentRecord } from '../api/types';
import { Feedback } from './Feedback';
export function DocumentViewer({
  api,
  document,
  onClose,
  page,
}: {
  api: ApiClient;
  document: Pick<DocumentRecord, 'id' | 'title'>;
  onClose: () => void;
  page?: number | null;
}) {
  const [url, setUrl] = useState('');
  const preview = useRef<HTMLElement>(null);
  useEffect(() => {
    preview.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
    preview.current?.focus();
  }, [document.id, page]);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = '';
    void api
      .documentFile(document.id, controller.signal)
      .then(async (blob) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
        if (!document.title.toLowerCase().endsWith('.pdf')) {
          const value = await blob.text();
          if (!controller.signal.aborted) setText(value);
        }
      })
      .catch((e) => {
        if (!isCancelled(e)) setError(errorMessage(e));
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [api, document.id, document.title]);
  return (
    <section
      ref={preview}
      tabIndex={-1}
      aria-label={`Preview ${document.title}`}
      className="my-5 rounded-xl border border-line bg-soft/30 p-5"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{document.title}</h2>
        <Button variant="ghost" onClick={onClose}>
          Close preview
        </Button>
      </div>
      {error ? (
        <Feedback error>{error}</Feedback>
      ) : !url ? (
        <p role="status">Loading document…</p>
      ) : (
        <>
          <a href={url} download={document.title} className="text-sm text-azure underline">
            Download document
          </a>
          {text !== null ? (
            <pre className="mt-4 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-4 text-sm">
              {text}
            </pre>
          ) : document.title.toLowerCase().endsWith('.pdf') ? (
            <iframe
              src={page && page > 0 ? `${url}#page=${page}` : url}
              title={document.title}
              className="mt-4 h-[60vh] w-full rounded-lg border border-line"
            />
          ) : null}
        </>
      )}
    </section>
  );
}
