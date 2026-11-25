import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button, InputField } from '@portfolio/porcelain-azure';
import { ApiClient, errorMessage, isCancelled } from '../api/client';
import { Feedback } from './Feedback';
import { PasswordField } from './PasswordField';

export function ResetPasswordPanel({
  onBack,
  directResetEnabled = false,
}: {
  onBack: () => void;
  directResetEnabled?: boolean;
}) {
  const [token, setToken] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get('token') || '',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [complete, setComplete] = useState(false);
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const changingPassword = !!token || directResetEnabled;
  useEffect(() => {
    // Fragments are not sent to the server; remove the token from history after reading it.
    if (window.location.hash) window.history.replaceState(null, '', '/reset-password');
    return () => controller.current?.abort();
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const element = event.currentTarget;
    const form = new FormData(element);
    const password = String(form.get('password') || '');
    if (changingPassword && password !== form.get('confirmation')) {
      setError('The passwords do not match.');
      return;
    }
    pending.current = true;
    setBusy(true);
    setError('');
    setMessage('');
    controller.current = new AbortController();
    try {
      const api = new ApiClient();
      const response = token
        ? await api.resetPassword(token, password, controller.current.signal)
        : directResetEnabled
          ? await api.resetPasswordDirect(
              String(form.get('email') || '').trim(),
              password,
              controller.current.signal,
            )
          : await api.forgotPassword(
              String(form.get('email') || '').trim(),
              controller.current.signal,
            );
      setMessage(response.message);
      if (changingPassword) {
        setComplete(true);
        setToken('');
        element.reset();
      }
    } catch (error) {
      if (!isCancelled(error)) setError(errorMessage(error));
    } finally {
      pending.current = false;
      if (!controller.current?.signal.aborted) setBusy(false);
    }
  }
  return (
    <>
      <h2 className="text-2xl font-bold tracking-tight">Reset your password.</h2>
      <p className="mb-6 mt-2 text-xs text-muted">
        {token
          ? 'Choose a new password for your account.'
          : complete
            ? 'Your password was updated. Return to sign in.'
            : directResetEnabled
              ? 'Enter your account email and choose a new password.'
              : 'Enter your account email to receive a password reset link.'}
      </p>
      {!complete && (
        <form aria-label="Reset password form" className="space-y-5" onSubmit={submit}>
          {!token && (
            <InputField
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              required
              disabled={busy}
            />
          )}
          {changingPassword && (
            <>
              <PasswordField
                label="New password"
                name="password"
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
                disabled={busy}
                hint="At least 8 characters."
              />
              <PasswordField
                label="Confirm new password"
                name="confirmation"
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
                disabled={busy}
              />
            </>
          )}
          {error && <Feedback error>{error}</Feedback>}
          {message && <Feedback>{message}</Feedback>}
          <Button type="submit" className="w-full" loading={busy}>
            {busy ? 'Please wait…' : changingPassword ? 'Update password' : 'Send reset link'}
          </Button>
        </form>
      )}
      {complete && <Feedback>{message}</Feedback>}
      {!!token && (
        <Button
          variant="ghost"
          className="mt-3"
          disabled={busy}
          onClick={() => {
            setToken('');
            setError('');
            setMessage('');
          }}
        >
          Request a new reset link
        </Button>
      )}
      <Button variant="ghost" className="mt-3" disabled={busy} onClick={onBack}>
        Back to sign in
      </Button>
    </>
  );
}
