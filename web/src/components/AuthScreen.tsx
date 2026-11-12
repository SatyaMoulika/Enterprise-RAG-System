import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  AIMotion,
  Button,
  Card,
  Eyebrow,
  InputField,
  MotionToggle,
} from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import type { User } from '../api/types';
import { Feedback } from './Feedback';
export function AuthScreen({
  onAuthenticated,
  notice,
}: {
  onAuthenticated: (token: string, user: User) => void;
  notice?: string;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') || '').trim();
    const password = String(form.get('password') || '');
    const name = String(form.get('workspace') || '').trim();
    if (mode === 'register' && !name) {
      setError('Enter a workspace name.');
      return;
    }
    pending.current = true;
    setBusy(true);
    setError('');
    controller.current = new AbortController();
    try {
      const api = new ApiClient();
      const session =
        mode === 'login'
          ? await api.login(email, password, controller.current.signal)
          : await api.register(
              { enterprise_name: name, email, password },
              controller.current.signal,
            );
      const user = await new ApiClient(session.access_token).me(controller.current.signal);
      onAuthenticated(session.access_token, user);
    } catch (error) {
      if (!isCancelled(error)) setError(errorMessage(error));
    } finally {
      pending.current = false;
      if (!controller.current?.signal.aborted) setBusy(false);
    }
  }
  return (
    <main className="mx-auto max-w-6xl px-5 py-6 sm:px-10">
      <header className="flex items-center justify-between">
        <span className="text-xl font-extrabold tracking-tight">
          atlas<span className="text-azure"> ✧</span>
        </span>
        <MotionToggle />
      </header>
      <div className="grid items-center gap-10 py-12 md:grid-cols-2 md:py-20">
        <section>
          <Eyebrow>Your documents / A clearer perspective</Eyebrow>
          <h1 className="my-5 text-5xl font-extrabold leading-[1.12] tracking-[-.05em]">
            Find the answer.
            <br />
            <span className="font-editorial font-medium italic text-azure">See the source.</span>
          </h1>
          <p className="max-w-md text-sm leading-7 text-muted">
            Bring your workspace documents together. Ask a question, explore the retrieved excerpts,
            and check the answer against the original context.
          </p>
          <AIMotion kind="embeddings" className="mt-4 h-52 max-w-sm" />
        </section>
        <Card className="p-6 sm:p-8">
          <div className="mb-7 flex gap-2" aria-label="Account action">
            <Button
              variant={mode === 'login' ? 'primary' : 'ghost'}
              aria-pressed={mode === 'login'}
              disabled={busy}
              onClick={() => {
                setMode('login');
                setError('');
              }}
            >
              Sign in
            </Button>
            <Button
              variant={mode === 'register' ? 'primary' : 'ghost'}
              aria-pressed={mode === 'register'}
              disabled={busy}
              onClick={() => {
                setMode('register');
                setError('');
              }}
            >
              Create workspace
            </Button>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            {mode === 'login' ? 'Welcome back.' : 'Make room for your knowledge.'}
          </h2>
          <p className="mb-6 mt-2 text-xs text-muted">
            {mode === 'login'
              ? 'Sign in to your workspace to continue.'
              : 'Create a new workspace and its administrator account.'}
          </p>
          {notice && (
            <div className="mb-4">
              <Feedback>{notice}</Feedback>
            </div>
          )}
          <form
            onSubmit={submit}
            aria-label={mode === 'login' ? 'Sign in form' : 'Create workspace form'}
            className="space-y-5"
          >
            {mode === 'register' && (
              <InputField
                label="Workspace name"
                name="workspace"
                required
                maxLength={255}
                autoComplete="organization"
                disabled={busy}
              />
            )}
            <InputField
              label="Email"
              name="email"
              type="email"
              required
              autoComplete="email"
              disabled={busy}
            />
            <InputField
              label="Password"
              name="password"
              type="password"
              required
              minLength={mode === 'register' ? 8 : 1}
              maxLength={128}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              hint={mode === 'register' ? 'At least 8 characters.' : undefined}
              disabled={busy}
            />
            {error && <Feedback error>{error}</Feedback>}
            <Button type="submit" loading={busy} className="w-full">
              {busy
                ? 'Connecting…'
                : mode === 'login'
                  ? 'Continue to workspace ↗'
                  : 'Create my workspace ↗'}
            </Button>
          </form>
          <p className="mt-5 text-[11px] leading-5 text-muted">
            Your session stays in this tab. Refreshing the page signs you out.
          </p>
        </Card>
      </div>
    </main>
  );
}
