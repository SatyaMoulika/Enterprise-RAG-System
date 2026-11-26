import { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge, Eyebrow, ThemeProvider } from '@portfolio/porcelain-azure';
import { ApiClient } from './api/client';
import type { DocumentRecord, User } from './api/types';
import { AuthScreen } from './components/AuthScreen';
import { ChatPanel } from './components/ChatPanel';
import { DocumentsPanel } from './components/DocumentsPanel';
import { MembersPanel } from './components/MembersPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { AccountMenu } from './components/AccountMenu';
import { AtlasLogo } from './components/AtlasLogo';
import { NavigationIcon } from './components/NavigationIcon';
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
    <div className="flex min-h-dvh w-full flex-col">
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:block focus:p-3">
        Skip to workspace
      </a>
      <header className="sticky top-0 z-20 flex min-h-16 flex-wrap items-center justify-between gap-4 border-b border-line bg-surface px-5 py-3 sm:px-6">
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
      <div className="flex-1 md:grid md:grid-cols-[240px_minmax(0,1fr)]">
        <aside aria-label="Organisation navigation" className="border-r border-line bg-[#F2F7FD]">
          <div className="hidden border-b border-line p-5 md:block">
            <Eyebrow className="break-words">{organisationName}</Eyebrow>
            <div className="mt-3">
              <Badge>{session.user.role === 'admin' ? 'Administrator' : 'Employee'}</Badge>
            </div>
          </div>
          <nav
            aria-label="Workspace navigation"
            className="flex gap-1 overflow-auto px-3 py-4 md:block md:space-y-1"
          >
            {[
              { id: 'overview', label: 'Overview', icon: <NavigationIcon name="overview" /> },
              { id: 'chat', label: 'Ask documents', icon: <NavigationIcon name="chat" /> },
              { id: 'documents', label: 'My documents', icon: <NavigationIcon name="documents" /> },
              ...(session.user.role === 'admin'
                ? [{ id: 'members', label: 'Members', icon: <NavigationIcon name="members" /> }]
                : []),
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                aria-current={view === item.id ? 'page' : undefined}
                onClick={() => {
                  setView(item.id);
                  if (item.id === 'documents') membersChanged();
                }}
                className={`flex shrink-0 items-center gap-3 whitespace-nowrap rounded-xl border px-3.5 py-3 text-sm transition md:w-full ${view === item.id ? 'border-line bg-surface font-bold text-azure' : 'border-transparent font-semibold text-muted hover:bg-surface/60'}`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>
          {profile.name?.trim() && (
            <div className="mx-3 mt-4 hidden rounded-xl border border-line bg-surface p-4 text-xs md:block">
              <p className="font-bold">Signed in as</p>
              <p className="mt-1 break-words text-muted">{profile.name}</p>
            </div>
          )}
        </aside>
        <main id="workspace-main" className="min-w-0 bg-[#F6FAFE] p-5 sm:p-8 lg:p-10">
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
