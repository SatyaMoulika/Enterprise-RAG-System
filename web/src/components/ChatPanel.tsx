import { useEffect, useRef, useState, type FormEvent } from 'react';
import { AIMotion, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import type { Answer, DocumentRecord } from '../api/types';
import { Feedback } from './Feedback';
import { DocumentViewer } from './DocumentViewer';
import { MarkdownAnswer } from './MarkdownAnswer';
import { SourceDocuments } from './SourceDocuments';
interface Turn {
  id: number;
  question: string;
  result?: Answer;
  error?: string;
}
export function ChatPanel({
  api,
  onOpenDocuments,
  document,
  onClearScope,
  initialQuestion,
}: {
  api: ApiClient;
  onOpenDocuments: () => void;
  document?: DocumentRecord | null;
  onClearScope?: () => void;
  initialQuestion?: { text: string; id: number } | null;
}) {
  const [activeCitation, setActiveCitation] = useState<{ turn: number; marker: number } | null>(
    null,
  );
  const [sourcePreview, setSourcePreview] = useState<
    (Pick<DocumentRecord, 'id' | 'title'> & { page?: number | null }) | null
  >(null);
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState('');
  const pending = useRef(false);
  const sequence = useRef(0);
  const active = useRef<AbortController | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    if (initialQuestion) setQuestion(initialQuestion.text);
  }, [initialQuestion]);
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (pending.current) return;
    const text = question.trim();
    if (!text) {
      setValidation('Enter a question about your documents.');
      input.current?.focus();
      return;
    }
    setValidation('');
    setActiveCitation(null);
    setSourcePreview(null);
    pending.current = true;
    setBusy(true);
    const id = ++sequence.current;
    setTurns((previous) => [...previous, { id, question: text }]);
    setQuestion('');
    active.current = new AbortController();
    try {
      const result = await api.ask(text, active.current.signal, document?.id);
      setTurns((previous) => previous.map((turn) => (turn.id === id ? { ...turn, result } : turn)));
    } catch (error) {
      if (!isCancelled(error))
        setTurns((previous) =>
          previous.map((turn) => (turn.id === id ? { ...turn, error: errorMessage(error) } : turn)),
        );
    } finally {
      pending.current = false;
      if (!active.current?.signal.aborted) {
        setBusy(false);
        input.current?.focus();
      }
    }
  }
  const sourceTurn =
    (activeCitation && turns.find((turn) => turn.id === activeCitation.turn)) ||
    [...turns].reverse().find((turn) => turn.result);
  return (
    <section aria-labelledby="chat-heading">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Question / Context / Understanding</Eyebrow>
          <h1 id="chat-heading" className="mt-2 text-3xl font-bold tracking-tight">
            Ask your{' '}
            <span className="font-editorial font-medium italic text-azure">documents.</span>
          </h1>
          <p className="mt-3 text-sm text-muted">
            {document
              ? `Searching only: ${document.title}`
              : 'Ask about your personal documents and company knowledge you can access.'}
          </p>
        </div>
        <Button
          variant="ghost"
          disabled={!turns.length || busy}
          onClick={() => {
            setTurns([]);
            setActiveCitation(null);
            setSourcePreview(null);
          }}
        >
          Clear conversation
        </Button>
      </div>
      {document && (
        <div className="mb-5 space-y-3">
          <Button variant="secondary" onClick={onClearScope}>
            Search all my documents
          </Button>
          <p className="text-xs leading-6 text-muted">
            Answers are limited to this file. To ask about another employee or document, switch
            files or search all your documents.
          </p>
        </div>
      )}
      {sourcePreview && (
        <DocumentViewer
          key={sourcePreview.id}
          api={api}
          document={sourcePreview}
          page={sourcePreview.page}
          onClose={() => setSourcePreview(null)}
        />
      )}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <div className="min-w-0">
          {!turns.length ? (
            <Card className="mb-5 p-6 sm:p-7">
              <div className="grid items-center gap-3 sm:grid-cols-[1fr_150px]">
                <div>
                  <h2 className="text-lg font-bold">Start with a question.</h2>
                  <p className="mb-4 mt-3 max-w-md text-sm leading-6 text-muted">
                    Ask about your offer letter, appointment details, company policies or products.
                    Open the source documents to verify an answer.
                  </p>
                  <Button variant="secondary" onClick={onOpenDocuments}>
                    Open documents ↗
                  </Button>
                </div>
                <AIMotion kind="vectors" decorative className="hidden h-36 sm:block" />
              </div>
              <div className="mt-6 border-t border-line/50 pt-4">
                <p className="text-xs font-semibold uppercase text-muted">Suggested questions</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    'What is the salary offered to me?',
                    'How many PTO days are included in the employee handbook?',
                    'Who has access to restricted security documents?',
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      className="rounded-xl border border-line bg-soft/50 px-3 py-2 text-left text-xs hover:bg-soft"
                      onClick={() => {
                        setQuestion(suggestion);
                        setValidation('');
                        input.current?.focus();
                      }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          ) : (
            <div
              className="mb-6 space-y-5"
              role="log"
              aria-label="Conversation"
              aria-live="polite"
              aria-relevant="additions text"
            >
              {turns.map((turn) => (
                <article key={turn.id} className="space-y-3">
                  <div className="ml-auto max-w-[86%] rounded-2xl border border-line/60 bg-soft p-5">
                    <Eyebrow>Your question</Eyebrow>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{turn.question}</p>
                  </div>
                  <Card className="p-6">
                    <Eyebrow>Document answer</Eyebrow>
                    {turn.result ? (
                      <>
                        <MarkdownAnswer
                          citations={turn.result.citations}
                          onCitation={(marker) => setActiveCitation({ turn: turn.id, marker })}
                        >
                          {turn.result.answer}
                        </MarkdownAnswer>
                      </>
                    ) : turn.error ? (
                      <div className="mt-3">
                        <Feedback error>{turn.error}</Feedback>
                      </div>
                    ) : (
                      <p className="mt-3 text-xs text-muted" role="status">
                        Searching your documents and preparing an answer…
                      </p>
                    )}
                  </Card>
                </article>
              ))}
            </div>
          )}
          <form onSubmit={ask} className="rounded-xl border border-line bg-surface p-6">
            <label htmlFor="question" className="mb-2 block text-xs font-semibold">
              Your question
            </label>
            <textarea
              ref={input}
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={2000}
              rows={3}
              disabled={busy}
              placeholder="What would you like to know?"
              className="w-full resize-y rounded-lg border border-line bg-canvas p-3 text-sm text-ink placeholder:text-muted disabled:opacity-60"
            />
            {validation && (
              <p role="alert" className="mt-2 text-xs text-[#883C3C]">
                {validation}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between gap-4">
              <span className="text-[10px] text-muted">
                {question.length}/2000 · Answers can be mistaken; verify the sources.
              </span>
              <Button type="submit" loading={busy} disabled={!question.trim() || busy}>
                {busy ? 'Preparing answer…' : 'Ask question ↗'}
              </Button>
            </div>
          </form>
        </div>
        <aside aria-label="Source documents" className="min-w-0 lg:sticky lg:top-20">
          <Card className="p-6">
            <Eyebrow>Source documents</Eyebrow>
            {sourceTurn?.result?.citations.length ? (
              <>
                <p className="mt-2 break-words text-xs leading-6 text-muted">
                  Sources for: {sourceTurn.question}
                </p>
                <SourceDocuments
                  key={sourceTurn.id}
                  citations={sourceTurn.result.citations}
                  answer={sourceTurn.result.answer}
                  activation={activeCitation}
                  activeMarker={
                    activeCitation?.turn === sourceTurn.id ? activeCitation.marker : undefined
                  }
                  onOpenSource={(source) =>
                    setSourcePreview({
                      id: source.document_id,
                      title: source.title,
                      page: source.page_start,
                    })
                  }
                />
              </>
            ) : (
              <p className="mt-3 text-sm leading-6 text-muted">
                {sourceTurn?.result
                  ? sourceTurn.result.answer_origin === 'account_context'
                    ? 'This response uses your signed-in account or document assignments. No document passage was needed.'
                    : 'No source documents were returned for this answer.'
                  : 'Relevant documents will appear here beside your conversation. Ask a question to get started.'}
              </p>
            )}
          </Card>
        </aside>
      </div>
    </section>
  );
}
