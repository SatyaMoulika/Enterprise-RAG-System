import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button, Card, Eyebrow, InputField } from '@portfolio/porcelain-azure';
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
    <main className="grid min-h-dvh w-full lg:grid-cols-2">
      <section className="auth-intro flex min-h-[440px] flex-col justify-between border-b border-line p-7 sm:p-12 lg:min-h-dvh lg:border-b-0 lg:border-r lg:p-14">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AtlasLogo />
            <span className="font-editorial text-xs italic text-muted">knowledge</span>
          </div>
        </div>
        <div className="my-10 max-w-lg lg:my-0">
          <Eyebrow className="text-azure">Question · Context · Understanding</Eyebrow>
          <h1 className="mt-4 text-[32px] font-extrabold leading-[1.12] tracking-tight sm:text-[40px]">
            Your organisation’s
            <br />
            knowledge,{' '}
            <span className="font-editorial font-medium italic text-azure">together.</span>
          </h1>
          <p className="mt-4 text-sm leading-7 text-muted">
            Atlas connects personal offer letters, company handbooks and restricted policies in one
            workspace, so you can check answers against their sources.
          </p>
          <div className="mt-9" aria-hidden="true">
            <svg viewBox="0 0 510 155" className="w-full max-w-lg" fill="none">
              <path
                d="M120 80 C165 80 165 55 210 55 M310 55 C350 55 350 80 390 80"
                stroke="var(--pa-azure)"
                strokeOpacity=".45"
                strokeWidth="2"
                strokeDasharray="5 6"
              />
              <circle cx="170" cy="67" r="5" fill="var(--pa-teal)" />
              <circle cx="350" cy="67" r="5" fill="var(--pa-teal)" />
              <rect
                x="10"
                y="8"
                width="130"
                height="136"
                rx="16"
                fill="var(--pa-surface)"
                stroke="var(--pa-line)"
              />
              <rect x="26" y="24" width="28" height="28" rx="8" fill="var(--pa-soft)" />
              <path
                d="M34 33h12m-12 5h12m-12 5h8"
                stroke="var(--pa-azure)"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M28 69h94M28 81h76M28 93h84"
                stroke="var(--pa-line)"
                strokeWidth="5"
                strokeLinecap="round"
              />
              <rect x="28" y="114" width="58" height="12" rx="6" fill="var(--pa-soft)" />
              <rect
                x="202"
                y="26"
                width="116"
                height="86"
                rx="15"
                fill="var(--pa-surface)"
                stroke="var(--pa-line)"
              />
              <circle cx="220" cy="45" r="5" fill="var(--pa-violet)" />
              <path
                d="M234 45h46M220 65h79M220 77h58M220 89h40"
                stroke="var(--pa-line)"
                strokeWidth="5"
                strokeLinecap="round"
              />
              <rect
                x="380"
                y="8"
                width="118"
                height="136"
                rx="16"
                fill="var(--pa-surface)"
                stroke="var(--pa-line)"
              />
              <circle cx="398" cy="28" r="9" fill="var(--pa-soft)" />
              <path d="M398 23v10m-5-5h10" stroke="var(--pa-azure)" strokeWidth="2" />
              <path
                d="M419 28h54M396 54h80M396 66h64"
                stroke="var(--pa-line)"
                strokeWidth="5"
                strokeLinecap="round"
              />
              <rect
                x="394"
                y="91"
                width="88"
                height="36"
                rx="10"
                fill="var(--pa-soft)"
                stroke="var(--pa-line)"
              />
              <path
                d="M406 103h57M406 114h41"
                stroke="var(--pa-line)"
                strokeWidth="4"
                strokeLinecap="round"
              />
            </svg>
            <div className="mt-3 flex justify-between text-xs text-muted">
              <span>Documents → Evidence → Answers</span>
              <span className="font-editorial italic">conceptual flow</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted">
          <span>◇ &nbsp;Role-scoped document access</span>
          <span>♧ &nbsp;Verify answers against original sources</span>
        </div>
      </section>
      <section
        className="flex items-center justify-center bg-soft/35 p-6 sm:p-10 lg:p-14"
        aria-label="Account access"
      >
        <Card
          className={`w-full ${mode === 'register' ? 'max-w-[620px]' : 'max-w-[460px]'} p-7 shadow-xl sm:p-9`}
        >
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
              <div
                className="mb-7 inline-flex gap-1 rounded-xl border border-line bg-soft p-1"
                aria-label="Account action"
              >
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
                {mode === 'login' ? 'Welcome back' : 'Create your workspace'}
              </h2>
              <p className="mb-6 mt-2 text-sm leading-6 text-muted">
                {mode === 'login'
                  ? 'Sign in to your organisation on Atlas.'
                  : 'Register your organisation and create your administrator account.'}
              </p>
              {notice && (
                <div className="mb-4">
                  <Feedback>{notice}</Feedback>
                </div>
              )}
              <form
                onSubmit={submit}
                aria-label={mode === 'login' ? 'Sign in form' : 'Create workspace form'}
                className={mode === 'register' ? 'space-y-4' : 'space-y-5'}
              >
                {mode === 'register' && (
                  <InputField
                    label="Organisation name"
                    name="workspace"
                    required
                    maxLength={255}
                    autoComplete="organization"
                    disabled={busy}
                  />
                )}
                <div className={mode === 'register' ? 'grid gap-4 sm:grid-cols-2' : ''}>
                  {mode === 'register' && (
                    <InputField
                      label="Your full name"
                      name="name"
                      required
                      maxLength={120}
                      autoComplete="name"
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
                </div>
                {mode === 'register' && (
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
                )}
                <div className={mode === 'register' ? 'grid gap-4 sm:grid-cols-2' : ''}>
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
                </div>
                {mode === 'login' && (
                  <a
                    href="/reset-password"
                    className="block text-right text-xs font-semibold text-azure"
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
                )}
                {error && <Feedback error>{error}</Feedback>}
                <Button type="submit" loading={busy} className="w-full py-3 text-sm shadow-sm">
                  {busy
                    ? 'Connecting…'
                    : mode === 'login'
                      ? 'Sign in to Atlas →'
                      : 'Create workspace →'}
                </Button>
              </form>
            </>
          )}
        </Card>
      </section>
    </main>
  );
}
