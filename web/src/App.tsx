import { useCallback, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Eyebrow,
  MotionToggle,
  Sidebar,
  ThemeProvider,
} from '@portfolio/porcelain-azure';
import { ApiClient } from './api/client';
import type { User } from './api/types';
import { AuthScreen } from './components/AuthScreen';
import { ChatPanel } from './components/ChatPanel';
import { DocumentsPanel } from './components/DocumentsPanel';
import { MembersPanel } from './components/MembersPanel';
interface Session {
  token: string;
  user: User;
}
function Workspace({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const [view, setView] = useState('chat');
  const [count, setCount] = useState<number | null>(null);
  const api = useMemo(() => new ApiClient(session.token, onSignOut), [session.token, onSignOut]);
  return (
    <div className="mx-auto max-w-7xl px-3 py-4 sm:px-6">
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:block focus:p-3">
        Skip to workspace
      </a>
      <header className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-surface px-5 py-4">
        <div>
          <span className="text-xl font-extrabold tracking-tight">
            atlas<span className="text-azure"> ✧</span>
          </span>
          <span className="ml-3 text-[11px] text-muted">Document workspace</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <MotionToggle />
          <span className="max-w-52 truncate text-xs text-muted" title={session.user.email}>
            {session.user.email}
          </span>
          <Button variant="ghost" onClick={onSignOut}>
            Sign out
          </Button>
        </div>
      </header>
      <div className="overflow-hidden rounded-xl border border-line bg-surface md:grid md:grid-cols-[190px_1fr]">
        <aside className="bg-soft/45">
          <div className="hidden border-b border-line p-5 md:block">
            <Eyebrow>Workspace #{session.user.enterprise_id}</Eyebrow>
            <div className="mt-3">
              <Badge>{session.user.role === 'admin' ? 'Administrator' : 'Member'}</Badge>
            </div>
            <p className="mt-3 text-[11px] text-muted">
              {count === null
                ? 'Document count unavailable'
                : `${count} document${count === 1 ? '' : 's'}`}
            </p>
          </div>
          <Sidebar
            items={[
              { id: 'chat', label: 'Ask documents', icon: '✧' },
              { id: 'documents', label: 'Documents', icon: '▤' },
              ...(session.user.role === 'admin'
                ? [{ id: 'members', label: 'Members', icon: '♧' }]
                : []),
            ]}
            active={view}
            onChange={setView}
          />
        </aside>
        <main id="workspace-main" className="min-w-0 p-5 sm:p-8">
          <div hidden={view !== 'chat'}>
            <ChatPanel api={api} onOpenDocuments={() => setView('documents')} />
          </div>
          <div hidden={view !== 'documents'}>
            <DocumentsPanel api={api} isAdmin={session.user.role === 'admin'} onCount={setCount} />
          </div>
          {session.user.role === 'admin' && view === 'members' && (
            <MembersPanel api={api} currentUser={session.user} />
          )}
        </main>
      </div>
      <footer className="px-2 py-5 text-[10px] text-muted">
        Workspace-scoped retrieval · Check answers against the source excerpts · Session and
        conversation clear on refresh or sign-out.
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
    <ThemeProvider className="min-h-screen bg-[#F4F8FC]">
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
