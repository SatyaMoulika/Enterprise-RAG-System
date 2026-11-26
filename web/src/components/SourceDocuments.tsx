import { useEffect, useRef } from 'react';
import { Button } from '@portfolio/porcelain-azure';
import type { Citation } from '../api/types';

type Reference = Citation & { marker: number };
interface SourceDocument {
  id: number;
  title: string;
  references: Reference[];
}

function pageLabel(references: Reference[]) {
  const ranges = references
    .filter((source) => Number.isInteger(source.page_start) && source.page_start! > 0)
    .map((source) => {
      const start = source.page_start!;
      const end =
        Number.isInteger(source.page_end) && source.page_end! >= start ? source.page_end! : start;
      return [start, end];
    })
    .sort((a, b) => a[0] - b[0]);
  const merged: number[][] = [];
  for (const range of ranges) {
    const previous = merged[merged.length - 1];
    if (previous && range[0] <= previous[1] + 1) previous[1] = Math.max(previous[1], range[1]);
    else merged.push([...range]);
  }
  if (!merged.length) return '';
  const pages = merged.map(([start, end]) => (start === end ? `${start}` : `${start}–${end}`));
  return `${merged.length === 1 && merged[0][0] === merged[0][1] ? 'Page' : 'Pages'} ${pages.join(', ')}`;
}

export function SourceDocuments({
  citations,
  answer,
  activeMarker,
  activation,
  onOpenSource,
}: {
  citations: Citation[];
  answer: string;
  activeMarker?: number;
  activation?: object | null;
  onOpenSource: (source: Citation) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const markers = new Set(
    [...answer.matchAll(/(?<!!)\[(\d+)\](?!\()/g)].map((match) => Number(match[1])),
  );
  const documents = new Map<number, SourceDocument>();
  citations.forEach((source, index) => {
    let document = documents.get(source.document_id);
    if (!document) {
      document = { id: source.document_id, title: source.title, references: [] };
      documents.set(source.document_id, document);
    }
    const marker = source.marker ?? index + 1;
    if (!document.references.some((reference) => reference.marker === marker))
      document.references.push({ ...source, marker });
  });
  const cited = [...documents.values()].filter((document) =>
    document.references.some((source) => markers.has(source.marker)),
  );
  const additional = [...documents.values()].filter(
    (document) => !document.references.some((source) => markers.has(source.marker)),
  );
  const selectedDocumentId = citations.find(
    (source, index) => (source.marker ?? index + 1) === activeMarker,
  )?.document_id;
  useEffect(() => {
    if (selectedDocumentId === undefined) return;
    const card = root.current?.querySelector<HTMLElement>(
      `[data-source-document="${selectedDocumentId}"]`,
    );
    if (!card) return;
    const extra = card.closest<HTMLDetailsElement>('details[data-additional-sources]');
    if (extra) extra.open = true;
    card.focus();
    card.scrollIntoView?.({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
      block: 'nearest',
    });
  }, [activeMarker, activation, selectedDocumentId]);

  function documentCard(document: SourceDocument) {
    const citedReferences = document.references.filter((source) => markers.has(source.marker));
    const references = citedReferences.length ? citedReferences : document.references;
    const selected = references.find((source) => source.marker === activeMarker);
    const source = selected ?? references[0];
    const pages = pageLabel(references);
    return (
      <article
        key={document.id}
        tabIndex={-1}
        aria-label={`Source document: ${document.title}`}
        data-source-document={document.id}
        className={`rounded-xl border bg-soft/30 p-4 focus-visible:outline-2 focus-visible:outline-azure ${selected ? 'border-azure/40' : 'border-line'}`}
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-soft text-sm text-azure"
          >
            ▤
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="break-words text-sm font-semibold">{document.title}</h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              {pages && (
                <>
                  <span>{pages}</span> ·{' '}
                </>
              )}
              <span>
                {citedReferences.length
                  ? `Reference${citedReferences.length === 1 ? '' : 's'} ${citedReferences.map((reference) => `[${reference.marker}]`).join(', ')}`
                  : 'Retrieved document'}
              </span>
            </p>
            <Button
              variant="ghost"
              className="mt-3"
              aria-label={`View document: ${document.title}`}
              onClick={() => onOpenSource(source)}
            >
              {selected?.page_start
                ? `View document · page ${selected.page_start}`
                : 'View document ↗'}
            </Button>
          </div>
        </div>
      </article>
    );
  }

  return (
    <div
      ref={root}
      className="mt-5 space-y-3 border-t border-line pt-5"
      aria-label="Answer sources"
    >
      <p className="text-xs leading-5 text-muted">
        Open a document to verify the answer. Select a citation to locate its document and page.
      </p>
      {cited.map(documentCard)}
      {!!additional.length && (
        <details data-additional-sources className="rounded-xl bg-soft/35 px-4 py-3">
          <summary className="cursor-pointer text-xs font-semibold text-muted">
            {cited.length ? 'Other retrieved documents' : 'Retrieved documents'} (
            {additional.length})
          </summary>
          <p className="my-3 text-xs leading-5 text-muted">
            These documents were retrieved but were not cited in the displayed answer.
          </p>
          <div className="space-y-3">{additional.map(documentCard)}</div>
        </details>
      )}
    </div>
  );
}
