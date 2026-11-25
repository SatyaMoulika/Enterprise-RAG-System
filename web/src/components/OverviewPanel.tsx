import { useState } from 'react';
import { AIMotion, Badge, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
import type { DocumentRecord, User } from '../api/types';
import { Feedback } from './Feedback';

export function OverviewPanel({
  user,
  documents,
  error,
  onOpenDocuments,
  onAsk,
  onMembers,
  onChat,
  membersCount,
  onQuickAsk,
  onUpload,
}: {
  user: User;
  documents: DocumentRecord[] | null;
  error: string;
  onOpenDocuments: () => void;
  onAsk: () => void;
  onMembers: () => void;
  onChat: (document: DocumentRecord) => void;
  membersCount: number | null;
  onQuickAsk: (question: string) => void;
  onUpload?: () => void;
}) {
  const [quickQuestion, setQuickQuestion] = useState('');
  const recent = [...(documents || [])]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, 5);
  const displayName = user.name?.trim();
  return (
    <section aria-labelledby="overview-heading" className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Organisation / Overview</Eyebrow>
          <h1
            id="overview-heading"
            className="mt-2 break-words text-3xl font-bold tracking-tight sm:text-4xl"
          >
            {displayName ? `Welcome back, ${displayName}.` : 'Welcome back.'}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            Your organisation’s knowledge and personal documents, in one place.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {user.role === 'admin' && (
            <Button variant="secondary" onClick={onMembers}>
              Add member
            </Button>
          )}
          <Button onClick={user.role === 'admin' && onUpload ? onUpload : onOpenDocuments}>
            {user.role === 'admin' ? 'Upload documents' : 'My documents'}
          </Button>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          ...(user.role === 'admin'
            ? [['Total members', membersCount, 'Accounts in your organisation']]
            : []),
          [
            user.role === 'admin' ? 'Total documents' : 'Your documents',
            documents?.length,
            user.role === 'admin' ? 'Documents in your organisation' : 'Documents you can access',
          ],
          [
            'Failed uploads',
            documents?.filter((document) => document.index_status === 'failed').length,
            'Uploads needing attention',
          ],
        ].map(([label, value, description]) => (
          <Card key={String(label)} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs font-semibold text-muted">{label}</p>
              <span
                aria-hidden="true"
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-soft text-azure"
              >
                {label === 'Total members' ? '♧' : label === 'Failed uploads' ? '!' : '▤'}
              </span>
            </div>
            <p className="mt-3 text-3xl font-bold">{value ?? '—'}</p>
            <p className="mt-2 text-xs text-muted">{description}</p>
          </Card>
        ))}
      </div>
      <Card className="bg-soft/40 p-5 sm:p-6">
        <div className="grid items-center gap-5 lg:grid-cols-[minmax(0,1fr)_170px]">
          <div>
            <Eyebrow>Ask Atlas</Eyebrow>
            <h2 className="mt-2 text-lg font-bold">Ask across your documents</h2>
            <form
              className="mt-4 flex flex-wrap gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (quickQuestion.trim()) {
                  onQuickAsk(quickQuestion.trim());
                  setQuickQuestion('');
                }
              }}
            >
              <label htmlFor="overview-question" className="sr-only">
                Your question for Atlas
              </label>
              <input
                id="overview-question"
                value={quickQuestion}
                onChange={(event) => setQuickQuestion(event.target.value)}
                maxLength={2000}
                placeholder="What would you like to know?"
                className="min-w-0 flex-1 rounded-lg border border-line bg-canvas px-3 py-2.5 text-sm text-ink"
              />
              <Button type="submit" disabled={!quickQuestion.trim()}>
                Ask question
              </Button>
            </form>
          </div>
          {documents?.length === 0 && (
            <AIMotion kind="vectors" decorative className="hidden h-28 lg:block" />
          )}
        </div>
        {documents?.length === 0 && (
          <p className="mt-3 text-xs text-muted">
            Upload or receive a document to find answers with sources.
          </p>
        )}
      </Card>
      {error && <Feedback error>{error} Open My documents to refresh the list.</Feedback>}
      {!documents && !error && (
        <p role="status" className="text-sm text-muted">
          Loading your workspace overview…
        </p>
      )}

      <div className="grid items-start gap-6">
        <Card className="min-w-0 overflow-hidden p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <Eyebrow>Knowledge library</Eyebrow>
              <h2 className="mt-2 text-lg font-bold">Recent documents</h2>
            </div>
            <Button variant="ghost" onClick={onOpenDocuments}>
              View all documents ↗
            </Button>
          </div>
          {recent.length ? (
            <ul className="divide-y divide-line">
              {recent.map((document) => (
                <li
                  key={document.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-4"
                >
                  <span
                    aria-hidden="true"
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-soft text-azure"
                  >
                    ▤
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="break-words text-sm font-semibold">{document.title}</p>
                    <p className="mt-1 text-xs text-muted">
                      Added {new Date(document.created_at).toLocaleDateString()} ·{' '}
                      {document.visibility === 'personal'
                        ? 'Personal'
                        : document.visibility === 'restricted'
                          ? 'Restricted'
                          : 'Company'}
                    </p>
                  </div>
                  <Badge>
                    {document.index_status === 'queued'
                      ? 'Queued'
                      : document.index_status === 'indexing'
                        ? 'Preparing'
                        : document.index_status === 'failed'
                          ? 'Needs attention'
                          : 'Ready'}
                  </Badge>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      document.index_status === 'failed' ? onOpenDocuments() : onChat(document)
                    }
                  >
                    {document.index_status === 'failed' ? 'Review' : 'Ask about this'}
                  </Button>
                </li>
              ))}
            </ul>
          ) : documents ? (
            <div className="rounded-lg border border-dashed border-line bg-soft/35 p-7">
              <h3 className="font-semibold">Start your knowledge library.</h3>
              <p className="mt-2 text-sm leading-6 text-muted">
                {user.role === 'admin'
                  ? 'Upload a document, choose who can access it, and start asking questions once the upload finishes.'
                  : 'Documents shared with you will appear here. Your administrator can add company knowledge and personal letters.'}
              </p>
              <Button
                variant="secondary"
                className="mt-4"
                onClick={user.role === 'admin' && onUpload ? onUpload : onOpenDocuments}
              >
                {user.role === 'admin' ? 'Upload documents' : 'Open my documents'}
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted">
              {error ? 'Document activity is unavailable.' : 'Loading recent documents…'}
            </p>
          )}
        </Card>
      </div>
    </section>
  );
}
