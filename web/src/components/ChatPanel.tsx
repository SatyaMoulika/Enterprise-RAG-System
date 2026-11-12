import { useEffect, useRef, useState, type FormEvent } from 'react';
import { AIMotion, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import type { Answer } from '../api/types';
import { Feedback } from './Feedback';
import { MarkdownAnswer } from './MarkdownAnswer';
interface Turn {
  id: number;
  question: string;
  result?: Answer;
  error?: string;
}
export function ChatPanel({
  api,
  onOpenDocuments,
}: {
  api: ApiClient;
  onOpenDocuments: () => void;
}) {
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState('');
  const pending = useRef(false);
  const sequence = useRef(0);
  const active = useRef<AbortController | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => () => active.current?.abort(), []);
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
    pending.current = true;
    setBusy(true);
    const id = ++sequence.current;
    setTurns((previous) => [...previous, { id, question: text }]);
    setQuestion('');
    active.current = new AbortController();
    try {
      const result = await api.ask(text, active.current.signal);
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
  return (
    <section aria-labelledby="chat-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow>Question / Context / Understanding</Eyebrow>
          <h1 id="chat-heading" className="mt-2 text-3xl font-bold tracking-tight">
            Ask your documents.
          </h1>
          <p className="mt-2 text-xs text-muted">
            Each question searches the current documents in this workspace.
          </p>
        </div>
        <Button variant="ghost" disabled={!turns.length || busy} onClick={() => setTurns([])}>
          Clear conversation
        </Button>
      </div>
      {!turns.length ? (
        <Card className="mb-6 grid items-center gap-3 bg-soft/40 p-6 sm:grid-cols-[1fr_170px]">
          <div>
            <h2 className="text-lg font-bold">Start with a question.</h2>
            <p className="mb-4 mt-2 max-w-md text-xs leading-6 text-muted">
              Upload a document, then ask about a policy, a process, or a detail you want to
              understand. You can expand the retrieved excerpts to verify an answer.
            </p>
            <Button variant="secondary" onClick={onOpenDocuments}>
              Open documents ↗
            </Button>
          </div>
          <AIMotion kind="vectors" className="hidden h-36 sm:block" />
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
              <div className="ml-auto max-w-[90%] rounded-xl bg-soft p-4">
                <Eyebrow>Your question</Eyebrow>
                <p className="mt-2 whitespace-pre-wrap text-sm">{turn.question}</p>
              </div>
              <Card className="p-5">
                <Eyebrow>Document answer</Eyebrow>
                {turn.result ? (
                  <>
                    <MarkdownAnswer>{turn.result.answer}</MarkdownAnswer>
                    {turn.result.citations.length > 0 && (
                      <div className="mt-5 space-y-2 border-t border-line pt-4">
                        <p className="text-[11px] text-muted">
                          Retrieved excerpts · check these to verify the answer.
                        </p>
                        {turn.result.citations.map((source, index) => (
                          <details
                            key={`${source.document_id}-${source.chunk_index}`}
                            className="rounded-lg border border-line bg-soft/35"
                          >
                            <summary className="cursor-pointer px-3 py-3 text-xs font-semibold text-azure">
                              [{index + 1}] {source.title} · excerpt {source.chunk_index + 1}
                            </summary>
                            <p className="whitespace-pre-wrap border-t border-line px-3 py-3 text-xs leading-6 text-muted">
                              {source.excerpt}
                            </p>
                          </details>
                        ))}
                      </div>
                    )}
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
      <form onSubmit={ask} className="rounded-xl border border-line bg-surface p-4">
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
          <Button type="submit" loading={busy}>
            {busy ? 'Preparing answer…' : 'Ask question ↗'}
          </Button>
        </div>
      </form>
    </section>
  );
}
