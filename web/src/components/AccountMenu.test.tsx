import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { AccountMenu } from './AccountMenu';
import { ApiClient } from '../api/client';
const account = {
  id: 1,
  name: 'Alice Morgan',
  email: 'alice@example.com',
  role: 'employee' as const,
  enterprise_id: 1,
  is_active: true,
};
it('opens account details from an icon, saves a name and photo, and supports removing the photo', async () => {
  const user = userEvent.setup(),
    api = new ApiClient('session'),
    updated = vi.fn();
  const save = vi
    .spyOn(api, 'updateProfile')
    .mockImplementation(async (body) => ({ ...account, ...body }));
  render(<AccountMenu user={account} api={api} onUpdated={updated} onSignOut={vi.fn()} />);
  expect(screen.queryByText(account.email)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Account' }));
  await user.clear(screen.getByLabelText('Full name'));
  await user.type(screen.getByLabelText('Full name'), 'Alice Reed');
  await user.upload(
    screen.getByLabelText('Profile photo'),
    new File(['photo'], 'avatar.png', { type: 'image/png' }),
  );
  await screen.findByAltText('Profile photo preview');
  await user.click(screen.getByRole('button', { name: 'Save account details' }));
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith({
      name: 'Alice Reed',
      profile_photo: expect.stringMatching(/^data:image\/png;base64,/),
    }),
  );
  expect(updated).toHaveBeenCalledWith(expect.objectContaining({ name: 'Alice Reed' }));
  await user.click(screen.getByRole('button', { name: 'Remove photo' }));
  await user.click(screen.getByRole('button', { name: 'Save account details' }));
  await waitFor(() =>
    expect(save).toHaveBeenLastCalledWith({ name: 'Alice Reed', profile_photo: null }),
  );
});
it('validates password confirmation and signs out only after a successful authenticated change', async () => {
  const user = userEvent.setup(),
    api = new ApiClient('session'),
    signout = vi.fn();
  const change = vi.spyOn(api, 'changePassword').mockResolvedValue({ message: 'Password changed' });
  render(<AccountMenu user={account} api={api} onUpdated={vi.fn()} onSignOut={signout} />);
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Account' }));
  await user.click(screen.getByRole('button', { name: 'Change password' }));
  await user.type(screen.getByLabelText('Current password'), 'old-password');
  await user.type(screen.getByLabelText('New password'), 'new-password-123');
  await user.type(screen.getByLabelText('Confirm new password'), 'different-password');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(change).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('do not match');
  await user.clear(screen.getByLabelText('Confirm new password'));
  await user.type(screen.getByLabelText('Confirm new password'), 'new-password-123');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  await waitFor(() => expect(signout).toHaveBeenCalledOnce());
  expect(change).toHaveBeenCalledWith({
    current_password: 'old-password',
    password: 'new-password-123',
  });
});
it('rejects oversized photos without sending them to the server', async () => {
  const user = userEvent.setup(),
    api = new ApiClient('session');
  const save = vi.spyOn(api, 'updateProfile');
  render(<AccountMenu user={account} api={api} onUpdated={vi.fn()} onSignOut={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Account' }));
  await user.upload(
    screen.getByLabelText('Profile photo'),
    new File([new Uint8Array(280001)], 'large.png', { type: 'image/png' }),
  );
  expect(screen.getByRole('alert')).toHaveTextContent('smaller than 280 KB');
  expect(save).not.toHaveBeenCalled();
});

it('shows a compact menu, opens account in a modal and discards unsaved changes on close', async () => {
  const user = userEvent.setup(),
    api = new ApiClient('session'),
    updated = vi.fn();
  render(<AccountMenu user={account} api={api} onUpdated={updated} onSignOut={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  expect(screen.getAllByRole('menuitem')).toHaveLength(2);
  expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument();
  await user.click(screen.getByRole('menuitem', { name: 'Account' }));
  expect(screen.getByRole('dialog', { name: 'Your account' })).toBeVisible();
  await user.clear(screen.getByLabelText('Full name'));
  await user.type(screen.getByLabelText('Full name'), 'Unsaved name');
  await user.click(screen.getByRole('button', { name: 'Close' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(updated).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Account' }));
  expect(screen.getByLabelText('Full name')).toHaveValue('Alice Morgan');
});

it('keeps the session on cancel and signs out only after confirmation', async () => {
  const user = userEvent.setup(),
    signout = vi.fn();
  render(
    <AccountMenu
      user={account}
      api={new ApiClient('session')}
      onUpdated={vi.fn()}
      onSignOut={signout}
    />,
  );
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
  expect(screen.getByRole('dialog', { name: 'Sign out of Atlas?' })).toBeVisible();
  expect(signout).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(signout).not.toHaveBeenCalled();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
  await user.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(signout).toHaveBeenCalledOnce();
});
