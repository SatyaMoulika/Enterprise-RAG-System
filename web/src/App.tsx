import { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge, Eyebrow, Sidebar, ThemeProvider } from '@portfolio/porcelain-azure';
import { ApiClient } from './api/client';
import type { DocumentRecord, User } from './api/types';
import { AuthScreen } from './components/AuthScreen';
import { ChatPanel } from './components/ChatPanel';
import { DocumentsPanel } from './components/DocumentsPanel';
import { MembersPanel } from './components/MembersPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { AccountMenu } from './components/AccountMenu';
import { AtlasLogo } from './components/AtlasLogo';
interface Session {
  token: string;
  user: User;
}
function Workspace({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const [profile, setProfile] = useState(session.user);
  const [quickQuestion, setQuickQuestion] = useState<{ text: string; id: number } | null>(null);
  const [membersCount, setMembersCount] = useState<number | null>(null);
  const [uploadRequest, setUploadRequest] = useState(0);
  const [view, setView] = useState('overview');
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [overviewError, setOverviewError] = useState('');
  const documentsChanged = useCallback((items: DocumentRecord[] | null, error = '') => {
    setDocuments(items);
    setOverviewError(error);
  }, []);
  const [membersRevision, setMembersRevision] = useState(0);
  const membersChanged = useCallback(() => setMembersRevision((n) => n + 1), []);
  const [chatDocument, setChatDocument] = useState<DocumentRecord | null>(null);
  const api = useMemo(() => new ApiClient(session.token, onSignOut), [session.token, onSignOut]);
  useEffect(() => {
    if (session.user.role !== 'admin') return;
    const controller = new AbortController();
    setMembersCount(null);
    void api
      .members(controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setMembersCount(rows.length);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMembersCount(null);
      });
    return () => controller.abort();
  }, [api, session.user.role, membersRevision]);
  const organisationName = profile.enterprise_name?.trim() || 'Your organisation';
  useEffect(() => {
    const page =
      {
        overview: 'Overview',
        chat: 'Ask documents',
        documents: 'My documents',
        members: 'Members',
      }[view] || 'Overview';
    document.title = `${page} · ${organisationName} | Atlas`;
  }, [view, organisationName]);
  return (
    <div className="flex min-h-dvh w-full flex-col px-3 py-3 sm:px-5 lg:px-6">
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:block focus:p-3">
        Skip to workspace
      </a>
      <header className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-surface px-5 py-4">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <button
            type="button"
            aria-label="Atlas home"
            className="rounded-lg text-left focus-visible:outline-2 focus-visible:outline-azure"
            onClick={() => setView('overview')}
          >
            <AtlasLogo />
          </button>
        </div>
        <AccountMenu user={profile} api={api} onUpdated={setProfile} onSignOut={onSignOut} />
      </header>
      <div className="flex-1 overflow-hidden rounded-xl border border-line bg-surface md:grid md:grid-cols-[220px_minmax(0,1fr)]">
        <aside aria-label="Organisation navigation" className="bg-soft/45">
          <div className="hidden border-b border-line p-5 md:block">
            <Eyebrow className="break-words">{organisationName}</Eyebrow>
            <div className="mt-3">
              <Badge>{session.user.role === 'admin' ? 'Administrator' : 'Employee'}</Badge>
            </div>
          </div>
          <Sidebar
            items={[
              { id: 'overview', label: 'Overview', icon: '◈' },
              { id: 'chat', label: 'Ask documents', icon: '✧' },
              { id: 'documents', label: 'My documents', icon: '▤' },
              ...(session.user.role === 'admin'
                ? [{ id: 'members', label: 'Members', icon: '♧' }]
                : []),
            ]}
            active={view}
            onChange={(next) => {
              setView(next);
              if (next === 'documents') membersChanged();
            }}
          />
        </aside>
        <main id="workspace-main" className="min-w-0 p-5 sm:p-8">
          {view === 'overview' && (
            <OverviewPanel
              user={profile}
              documents={documents}
              error={overviewError}
              onOpenDocuments={() => setView('documents')}
              onUpload={() => {
                setUploadRequest((value) => value + 1);
                setView('documents');
              }}
              membersCount={membersCount}
              onQuickAsk={(text) => {
                setChatDocument(null);
                setQuickQuestion({ text, id: Date.now() });
                setView('chat');
              }}
              onAsk={() => {
                setChatDocument(null);
                setView('chat');
              }}
              onMembers={() => setView('members')}
              onChat={(document) => {
                setChatDocument(document);
                setView('chat');
              }}
            />
          )}
          <div hidden={view !== 'chat'}>
            <ChatPanel
              key={chatDocument?.id || 'all'}
              document={chatDocument}
              initialQuestion={quickQuestion}
              onClearScope={() => setChatDocument(null)}
              api={api}
              onOpenDocuments={() => setView('documents')}
            />
          </div>
          <div hidden={view !== 'documents'}>
            <DocumentsPanel
              api={api}
              uploadRequest={uploadRequest}
              isAdmin={session.user.role === 'admin'}
              onDocumentsChange={documentsChanged}
              membersRevision={membersRevision}
              onChat={(document) => {
                setChatDocument(document);
                setView('chat');
              }}
            />
          </div>
          {session.user.role === 'admin' && view === 'members' && (
            <MembersPanel
              api={api}
              currentUser={profile}
              onMembersChanged={membersChanged}
              onCurrentUserUpdated={setProfile}
            />
          )}
        </main>
      </div>
      <footer className="px-2 py-5 text-[10px] text-muted">
        Atlas · Your organisation’s knowledge, together. Verify answers against the original
        sources.
      </footer>
    </div>
  );
}
export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState('');
  const endSession = useCallback(() => {
    setSession(null);
    setNotice('Your session has ended. Sign in to continue.');
  }, []);
  return (
    <ThemeProvider className="min-h-dvh w-full bg-[#F4F8FC]">
      {session ? (
        <Workspace key={session.token} session={session} onSignOut={endSession} />
      ) : (
        <AuthScreen
          notice={notice}
          onAuthenticated={(token, user) => {
            setNotice('');
            setSession({ token, user });
          }}
        />
      )}
    </ThemeProvider>
  );
}
