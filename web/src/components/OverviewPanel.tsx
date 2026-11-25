import { Badge, Button, Card, Eyebrow } from '@portfolio/porcelain-azure';
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
}: {
  user: User;
  documents: DocumentRecord[] | null;
  error: string;
  onOpenDocuments: () => void;
  onAsk: () => void;
  onMembers: () => void;
  onChat: (document: DocumentRecord) => void;
}) {
  const personal = documents?.filter((document) => document.visibility === 'personal');
  const recent = [...(documents || [])]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, 5);
  const displayName = user.name?.trim();
  return (
    <section aria-labelledby="overview-heading" className="space-y-7">
      <Card className="grid items-center gap-7 p-5 sm:p-8 xl:grid-cols-[minmax(0,1fr)_minmax(340px,1fr)]">
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
          <div className="mt-5 flex flex-wrap gap-3">
            <Button onClick={onAsk}>Ask your documents ↗</Button>
            <Button variant="secondary" onClick={onOpenDocuments}>
              My documents ↗
            </Button>
          </div>
        </div>
        <Card className="bg-soft/40 p-5 sm:p-6">
          <Eyebrow>A clear path to a sourced answer</Eyebrow>
          <ol className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ['Your question', 'Ask in your own words'],
              ['Your knowledge', 'Documents shared with you'],
              ['Relevant sources', 'Open the original documents'],
            ].map(([title, description], index) => (
              <li key={title}>
                <Card className="h-full p-4">
                  <Badge>{index + 1}</Badge>
                  <p className="mt-3 text-sm font-semibold">{title}</p>
                  <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
                </Card>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-xs leading-6 text-muted">
            Find answers in the company knowledge and personal documents shared with you.
          </p>
        </Card>
      </Card>
      {error && <Feedback error>{error} Open My documents to refresh the list.</Feedback>}
      {!documents && !error && (
        <p role="status" className="text-sm text-muted">
          Loading your workspace overview…
        </p>
      )}

      <div className="grid items-start gap-6 xl:grid-cols-2">
        <Card className="min-w-0 p-5 sm:p-6">
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
              <Button variant="secondary" className="mt-4" onClick={onOpenDocuments}>
                {user.role === 'admin' ? 'Add your first document' : 'Open my documents'}
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted">
              {error ? 'Document activity is unavailable.' : 'Loading recent documents…'}
            </p>
          )}
        </Card>
        <div className="space-y-5">
          <Card className="p-5 sm:p-6">
            <Eyebrow>Ask your organisation</Eyebrow>
            <h2 className="mt-2 text-lg font-bold">Find out more about your workplace.</h2>
            <div className="mt-5 flex flex-col items-start gap-3">
              <Button variant="secondary" onClick={onAsk}>
                Ask a question
              </Button>
              <Button variant="ghost" onClick={onOpenDocuments}>
                {user.role === 'admin' ? 'Manage documents' : 'Browse my documents'}
              </Button>
              {user.role === 'admin' && (
                <Button variant="ghost" onClick={onMembers}>
                  Manage members
                </Button>
              )}
            </div>
          </Card>
          <Card className="bg-soft/40 p-5 sm:p-6">
            <Eyebrow>Your access</Eyebrow>
            <h2 className="mt-2 text-lg font-bold">Knowledge shared with you</h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              {documents
                ? `${personal?.length || 0} personal document${personal?.length === 1 ? '' : 's'}, alongside company and restricted knowledge you can access.`
                : 'Your overview includes only documents available to your account.'}
            </p>
            <p className="mt-3 text-xs leading-6 text-muted">
              Follow the numbered references when reviewing an answer. Open the original documents
              for the full context.
            </p>
          </Card>
        </div>
      </div>
    </section>
  );
}
