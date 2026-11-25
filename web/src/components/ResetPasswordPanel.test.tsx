import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AuthScreen } from './AuthScreen';
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => {
  window.history.replaceState(null, '', '/');
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((path) =>
        Promise.resolve(
          path === '/api/auth/config'
            ? json({ registration_enabled: true })
            : json({ message: 'If an active account exists, check your email.' }),
        ),
      ),
  );
});
afterEach(() => window.history.replaceState(null, '', '/'));

it('opens the reset page directly from signup and requests an emailed link', async () => {
  const user = userEvent.setup();
  render(<AuthScreen onAuthenticated={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));
  await user.click(screen.getByRole('link', { name: 'Forgot password?' }));
  expect(window.location.pathname).toBe('/reset-password');
  expect(screen.getByRole('heading', { name: 'Reset your password.' })).toBeVisible();
  expect(screen.queryByLabelText('Organisation name')).not.toBeInTheDocument();
  await user.type(screen.getByLabelText('Email'), 'alice@example.com');
  await user.click(screen.getByRole('button', { name: 'Send reset link' }));
  expect(await screen.findByText('If an active account exists, check your email.')).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    '/api/auth/forgot-password',
    expect.objectContaining({ body: JSON.stringify({ email: 'alice@example.com' }) }),
  );
});

it('opens an emailed reset link, validates confirmation, and returns to sign in', async () => {
  window.history.replaceState(null, '', '/reset-password#token=fake-reset-token');
  const user = userEvent.setup();
  render(<AuthScreen onAuthenticated={vi.fn()} />);
  expect(window.location.hash).toBe('');
  await user.type(screen.getByLabelText('New password'), 'new-password-123');
  await user.type(screen.getByLabelText('Confirm new password'), 'different-password');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(screen.getByRole('alert')).toHaveTextContent('do not match');
  await user.clear(screen.getByLabelText('Confirm new password'));
  await user.type(screen.getByLabelText('Confirm new password'), 'new-password-123');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(fetch).toHaveBeenCalledWith(
    '/api/auth/reset-password',
    expect.objectContaining({
      body: JSON.stringify({ token: 'fake-reset-token', password: 'new-password-123' }),
    }),
  );
  await screen.findByText('Your password was updated. Return to sign in.');
  expect(screen.queryByLabelText('New password')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Back to sign in' }));
  expect(window.location.pathname).toBe('/');
  expect(screen.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
});

it('shows expired-link errors and lets the user request a fresh link', async () => {
  window.history.replaceState(null, '', '/reset-password#token=expired');
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((path) =>
        Promise.resolve(
          path === '/api/auth/reset-password'
            ? json({ detail: 'This reset link is invalid or expired.' }, 400)
            : json({ registration_enabled: false }),
        ),
      ),
  );
  const user = userEvent.setup();
  render(<AuthScreen onAuthenticated={vi.fn()} />);
  await user.type(screen.getByLabelText('New password'), 'new-password-123');
  await user.type(screen.getByLabelText('Confirm new password'), 'new-password-123');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('invalid or expired');
  await user.click(screen.getByRole('button', { name: 'Request a new reset link' }));
  expect(screen.getByLabelText('Email')).toBeVisible();
});

it('resets a local account by email without requesting a link and clears password fields', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((path) =>
        Promise.resolve(
          path === '/api/auth/config'
            ? json({ registration_enabled: true, direct_password_reset_enabled: true })
            : json({ message: 'Your password has been updated. Sign in with your new password.' }),
        ),
      ),
  );
  const user = userEvent.setup();
  render(<AuthScreen onAuthenticated={vi.fn()} />);
  await user.click(screen.getByRole('link', { name: 'Forgot password?' }));
  await user.type(screen.getByLabelText('Email'), 'alice@example.com');
  await user.type(await screen.findByLabelText('New password'), 'new-password-123');
  await user.type(screen.getByLabelText('Confirm new password'), 'different-password');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(screen.getByRole('alert')).toHaveTextContent('do not match');
  expect(fetch).not.toHaveBeenCalledWith('/api/auth/reset-password/direct', expect.anything());
  await user.clear(screen.getByLabelText('Confirm new password'));
  await user.type(screen.getByLabelText('Confirm new password'), 'new-password-123');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(fetch).toHaveBeenCalledWith(
    '/api/auth/reset-password/direct',
    expect.objectContaining({
      body: JSON.stringify({ email: 'alice@example.com', password: 'new-password-123' }),
    }),
  );
  expect(fetch).not.toHaveBeenCalledWith('/api/auth/forgot-password', expect.anything());
  expect(await screen.findByText('Your password was updated. Return to sign in.')).toBeVisible();
  expect(screen.queryByLabelText('New password')).not.toBeInTheDocument();
});

it('keeps the direct reset form available when an email is not found', async () => {
  window.history.replaceState(null, '', '/reset-password');
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((path) =>
        Promise.resolve(
          path === '/api/auth/config'
            ? json({ registration_enabled: true, direct_password_reset_enabled: true })
            : json({ detail: 'No active account found for this email.' }, 400),
        ),
      ),
  );
  const user = userEvent.setup();
  render(<AuthScreen onAuthenticated={vi.fn()} />);
  await user.type(await screen.findByLabelText('New password'), 'new-password-123');
  await user.type(screen.getByLabelText('Confirm new password'), 'new-password-123');
  await user.type(screen.getByLabelText('Email'), 'missing@example.com');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No active account found');
  expect(screen.getByLabelText('Email')).toBeEnabled();
});
