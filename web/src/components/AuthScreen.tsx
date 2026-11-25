import { useEffect, useRef, useState, type FormEvent } from 'react';
import { AIMotion, Button, Card, Eyebrow, InputField } from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import type { User } from '../api/types';
import { Feedback } from './Feedback';
import { ResetPasswordPanel } from './ResetPasswordPanel';
import { PasswordField } from './PasswordField';
import { AtlasLogo } from './AtlasLogo';
export function AuthScreen({
  onAuthenticated,
  notice,
}: {
  onAuthenticated: (token: string, user: User) => void;
  notice?: string;
}) {
  const [mode, setMode] = useState<'login' | 'register' | 'reset'>(() =>
    window.location.pathname === '/reset-password' ? 'reset' : 'login',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [registrationEnabled, setRegistrationEnabled] = useState(true);
  const [directResetEnabled, setDirectResetEnabled] = useState(false);
  useEffect(() => {
    document.title = `${mode === 'register' ? 'Create organisation' : mode === 'reset' ? 'Reset password' : 'Sign in'} | Atlas`;
  }, [mode]);
  useEffect(() => {
    const abort = new AbortController();
    void new ApiClient()
      .authConfig(abort.signal)
      .then((config) => {
        if (abort.signal.aborted) return;
        setRegistrationEnabled(config.registration_enabled);
        setDirectResetEnabled(config.direct_password_reset_enabled === true);
        if (!config.registration_enabled)
          setMode((current) => (current === 'register' ? 'login' : current));
      })
      .catch(() => {
        /* The API still enforces registration policy if discovery fails. */
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    const sync = () => setMode(window.location.pathname === '/reset-password' ? 'reset' : 'login');
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') || '').trim();
    const password = String(form.get('password') || '');
    const organisationName = String(form.get('workspace') || '').trim();
    const administratorName = String(form.get('name') || '').trim();
    if (mode === 'register') {
      if (!organisationName || !administratorName) {
        setError('Enter your organisation name and your full name.');
        return;
      }
      if (form.get('is_admin') !== 'on') {
        setError('Confirm that you are registering as the organisation administrator.');
        return;
      }
      if (password !== String(form.get('confirmation') || '')) {
        setError('The passwords do not match.');
        return;
      }
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
              {
                enterprise_name: organisationName,
                name: administratorName,
                is_admin: true,
                email,
                password,
              },
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
    <main className="flex min-h-dvh w-full flex-col px-5 py-6 sm:px-10 lg:px-16">
      <header className="flex items-center justify-between">
        <AtlasLogo />
      </header>
      <div className="grid flex-1 items-center gap-10 py-12 md:grid-cols-2 md:py-20 lg:gap-20">
        <section>
          <Eyebrow>Your documents / A clearer perspective</Eyebrow>
          <h1 className="my-5 text-5xl font-extrabold leading-[1.12] tracking-[-.05em]">
            Find the answer.
            <br />
            <span className="font-editorial font-medium italic text-azure">See the source.</span>
          </h1>
          <p className="max-w-md text-sm leading-7 text-muted">
            Bring your organisation’s documents together. Ask a question and check the answer
            against the original sources.
          </p>
          <AIMotion kind="embeddings" className="mt-4 h-52 max-w-sm" />
        </section>
        <Card className="p-6 sm:p-8">
          {mode === 'reset' ? (
            <ResetPasswordPanel
              directResetEnabled={directResetEnabled}
              onBack={() => {
                window.history.pushState(null, '', '/');
                setMode('login');
                setError('');
              }}
            />
          ) : (
            <>
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
                {registrationEnabled && (
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
                )}
              </div>
              <h2 className="text-2xl font-bold tracking-tight">
                {mode === 'login' ? 'Welcome back.' : 'Make room for your knowledge.'}
              </h2>
              <p className="mb-6 mt-2 text-xs text-muted">
                {mode === 'login'
                  ? 'Sign in to your workspace to continue.'
                  : 'Register your organisation and create your administrator account. Employees receive accounts from their organisation administrator.'}
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
                  <>
                    <InputField
                      label="Organisation name"
                      name="workspace"
                      required
                      maxLength={255}
                      autoComplete="organization"
                      disabled={busy}
                    />
                    <InputField
                      label="Your full name"
                      name="name"
                      required
                      maxLength={120}
                      autoComplete="name"
                      disabled={busy}
                    />
                    <label className="flex items-start gap-3 text-xs leading-6 text-ink">
                      <input
                        type="checkbox"
                        name="is_admin"
                        required
                        disabled={busy}
                        className="mt-1 h-4 w-4 shrink-0 accent-azure"
                      />
                      I am registering as this organisation’s administrator.
                    </label>
                  </>
                )}
                <InputField
                  label="Email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  disabled={busy}
                />
                <PasswordField
                  key={mode}
                  label="Password"
                  name="password"
                  required
                  minLength={mode === 'register' ? 8 : 1}
                  maxLength={128}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  hint={mode === 'register' ? 'At least 8 characters.' : undefined}
                  disabled={busy}
                />
                {mode === 'register' && (
                  <PasswordField
                    label="Confirm password"
                    name="confirmation"
                    required
                    minLength={8}
                    maxLength={128}
                    autoComplete="new-password"
                    disabled={busy}
                  />
                )}
                {error && <Feedback error>{error}</Feedback>}
                <Button type="submit" loading={busy} className="w-full">
                  {busy
                    ? 'Connecting…'
                    : mode === 'login'
                      ? 'Continue to workspace ↗'
                      : 'Create my workspace ↗'}
                </Button>
              </form>
              <a
                href="/reset-password"
                className="mt-4 inline-block text-xs font-semibold text-azure"
                onClick={(event) => {
                  event.preventDefault();
                  if (busy) return;
                  window.history.pushState(null, '', '/reset-password');
                  setMode('reset');
                  setError('');
                }}
              >
                Forgot password?
              </a>
              <p className="mt-5 text-[11px] leading-5 text-muted">
                Your session stays in this tab. Refreshing the page signs you out.
              </p>
            </>
          )}
        </Card>
      </div>
    </main>
  );
}
