import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { PasswordField } from './PasswordField';

it('toggles visibility with pointer and keyboard without submitting or changing the password', async () => {
  const user = userEvent.setup();
  const submit = vi.fn((event) => event.preventDefault());
  render(
    <form aria-label="Account" onSubmit={submit}>
      <PasswordField label="Password" name="password" autoComplete="current-password" />
    </form>,
  );
  const field = screen.getByLabelText('Password');
  expect(field).toHaveAttribute('type', 'password');
  await user.type(field, 'private-password-123');
  await user.click(screen.getByRole('button', { name: 'Show password' }));
  expect(field).toHaveAttribute('type', 'text');
  expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await user.keyboard(' ');
  expect(field).toHaveAttribute('type', 'password');
  expect(field).toHaveValue('private-password-123');
  expect(field).toHaveAttribute('autocomplete', 'current-password');
  const form = screen.getByRole('form', { name: 'Account' }) as HTMLFormElement;
  expect(new FormData(form).get('password')).toBe('private-password-123');
  expect(submit).not.toHaveBeenCalled();
});

it('keeps confirmation visibility independent and masks both fields when the form resets', async () => {
  const user = userEvent.setup();
  render(
    <form>
      <PasswordField label="New password" name="password" />
      <PasswordField label="Confirm new password" name="confirmation" />
      <button type="reset">Reset form</button>
    </form>,
  );
  const password = screen.getByLabelText('New password');
  const confirmation = screen.getByLabelText('Confirm new password');
  await user.type(password, 'new-password-123');
  await user.type(confirmation, 'new-password-123');
  await user.click(screen.getByRole('button', { name: 'Show new password' }));
  expect(password).toHaveAttribute('type', 'text');
  expect(confirmation).toHaveAttribute('type', 'password');
  await user.click(screen.getByRole('button', { name: 'Show confirm new password' }));
  expect(confirmation).toHaveAttribute('type', 'text');
  await user.click(screen.getByRole('button', { name: 'Reset form' }));
  for (const field of [password, confirmation]) {
    expect(field).toHaveAttribute('type', 'password');
    expect(field).toHaveValue('');
  }
});

it('masks a revealed password during submission and disables the eye alongside the input', async () => {
  const user = userEvent.setup();
  const { rerender } = render(<PasswordField label="Initial password" name="password" />);
  await user.type(screen.getByLabelText('Initial password'), 'initial-password-123');
  await user.click(screen.getByRole('button', { name: 'Show initial password' }));
  rerender(<PasswordField label="Initial password" name="password" disabled />);
  expect(screen.getByLabelText('Initial password')).toBeDisabled();
  expect(screen.getByLabelText('Initial password')).toHaveAttribute('type', 'password');
  expect(screen.getByRole('button', { name: 'Show initial password' })).toBeDisabled();
  rerender(<PasswordField label="Initial password" name="password" />);
  expect(screen.getByLabelText('Initial password')).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText('Initial password')).toHaveValue('initial-password-123');
});

it('preserves validation and accessible help while associating the eye with its field', () => {
  render(
    <PasswordField
      id="new-password"
      label="New password"
      name="password"
      required
      minLength={8}
      maxLength={128}
      autoComplete="new-password"
      hint="At least 8 characters."
    />,
  );
  const input = screen.getByLabelText('New password');
  expect(input).toBeRequired();
  expect(input).toHaveAttribute('minlength', '8');
  expect(input).toHaveAttribute('maxlength', '128');
  expect(input).toHaveAccessibleDescription('At least 8 characters.');
  expect(screen.getByRole('button', { name: 'Show new password' })).toHaveAttribute(
    'aria-controls',
    input.id,
  );
});
