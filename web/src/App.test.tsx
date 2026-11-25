import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { DocumentRecord, Member } from './api/types';
const json = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
let members: Member[];
let docs: DocumentRecord[],
  role: 'admin' | 'employee',
  calls: { path: string; options: RequestInit }[];
let customize:
  ((path: string, options: RequestInit) => Response | Promise<Response> | undefined) | undefined;
beforeEach(() => {
  docs = [];
  members = [
    {
      id: 1,
      email: 'owner@example.com',
      role: 'admin',
      enterprise_id: 7,
      is_active: true,
      created_at: '2026-11-12T09:00:00Z',
    },
  ];
  role = 'admin';
  calls = [];
  customize = undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string, options: RequestInit) => {
      const path = String(input);
      calls.push({ path, options });
      const custom = customize?.(path, options);
      if (custom) return custom;
      if (path === '/api/auth/login' || path === '/api/auth/register')
        return json({ access_token: 'test-session', token_type: 'bearer' });
      if (path === '/api/users/me')
        return json({
          id: 1,
          email: 'owner@example.com',
          role,
          enterprise_id: 7,
          enterprise_name: 'Knowledge team',
          is_active: true,
        });
      if (path === '/api/users/get_all_users') return json(members);
      if (path === '/api/users/create_user') {
        const values = JSON.parse(String(options.body));
        const member: Member = {
          id: Math.max(0, ...members.map((m) => m.id)) + 1,
          name: values.name,
          email: values.email,
          role: values.role,
          enterprise_id: 7,
          is_active: true,
          created_at: '2026-11-12T09:00:00Z',
        };
        members = [...members, member];
        return json(member);
      }
      if (path === '/api/users/delete_user/2' && options.method === 'DELETE') {
        members = members.filter((m) => m.id !== 2);
        return json({ message: 'deleted' });
      }
      if (path === '/api/documents/list') return json(docs);
      if (path === '/api/documents/limits')
        return json({ allowed_extensions: ['.pdf', '.txt'], max_upload_bytes: 10 * 1024 * 1024 });
      if (path === '/api/documents/upload') {
        const file = (options.body as FormData).get('file') as File;
        const doc = {
          id: 12,
          title: file.name,
          enterprise_id: 7,
          created_at: '2026-11-12T09:00:00Z',
        };
        docs = [...docs, doc];
        return json(doc, 201);
      }
      if (path === '/api/documents/12' && options.method === 'DELETE') {
        docs = docs.filter((d) => d.id !== 12);
        return json({ message: 'Document deleted successfully' });
      }
      if (path === '/api/chat/generate')
        return json({
          answer: 'The office opens at nine [1].',
          sources: [12],
          citations: [
            {
              document_id: 12,
              title: 'policy.txt',
              chunk_index: 0,
              excerpt: 'The office opens at nine.',
            },
          ],
        });
      return json({ detail: 'Unexpected request in test' }, 500);
    }),
  );
});
async function signIn() {
  const user = userEvent.setup();
  render(<App />);
  await user.type(screen.getByLabelText('Email'), 'owner@example.com');
  await user.type(screen.getByLabelText('Password'), 'test password');
  await user.click(screen.getByRole('button', { name: /Continue to workspace/ }));
  await screen.findByRole('heading', { level: 1, name: /^Welcome back(?:, .+)?\.$/ });
  await user.click(screen.getByRole('button', { name: 'Ask documents' }));
  return user;
}
describe('real-data workspace', () => {
  it('signs in with the API and never persists credentials in web storage', async () => {
    const local = vi.spyOn(Storage.prototype, 'setItem');
    await signIn();
    expect(calls.find((c) => c.path === '/api/auth/login')?.options.body).toBe(
      JSON.stringify({ email: 'owner@example.com', password: 'test password' }),
    );
    expect(calls.find((c) => c.path === '/api/users/me')?.options.headers).toBeInstanceOf(Headers);
    expect(local).not.toHaveBeenCalled();
    expect(
      within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
        'Knowledge team',
      ),
    ).toBeVisible();
    expect(screen.queryByText(/Workspace #\d/)).not.toBeInTheDocument();
  });
  it('creates a workspace and validates its session before entering', async () => {
    customize = (path) =>
      path === '/api/users/me'
        ? json({
            id: 1,
            name: 'Moulika Devi',
            email: 'owner@example.com',
            role: 'admin',
            enterprise_id: 7,
            enterprise_name: 'Knowledge team',
            is_active: true,
          })
        : undefined;
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Create workspace' }));
    await user.type(screen.getByLabelText('Organisation name'), 'Knowledge team');
    await user.type(screen.getByLabelText('Your full name'), '  Moulika Devi  ');
    await user.type(screen.getByLabelText('Email'), 'owner@example.com');
    await user.type(screen.getByLabelText('Password'), 'test password');
    await user.type(screen.getByLabelText('Confirm password'), 'different password');
    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text');
    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
    await user.click(screen.getByRole('button', { name: /Create my workspace/ }));
    expect(calls.some((call) => call.path === '/api/auth/register')).toBe(false);
    await user.click(screen.getByRole('checkbox', { name: /organisation’s administrator/ }));
    await user.click(screen.getByRole('button', { name: /Create my workspace/ }));
    expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.');
    expect(calls.some((call) => call.path === '/api/auth/register')).toBe(false);
    await user.clear(screen.getByLabelText('Confirm password'));
    await user.type(screen.getByLabelText('Confirm password'), 'test password');
    await user.click(screen.getByRole('button', { name: /Show confirm password/ }));
    expect(screen.getByLabelText('Confirm password')).toHaveAttribute('type', 'text');
    await user.click(screen.getByRole('button', { name: /Hide confirm password/ }));
    await user.click(screen.getByRole('button', { name: /Create my workspace/ }));
    await screen.findByRole('heading', { level: 1, name: /^Welcome back(?:, .+)?\.$/ });
    expect(
      JSON.parse(String(calls.find((c) => c.path === '/api/auth/register')?.options.body)),
    ).toEqual({
      enterprise_name: 'Knowledge team',
      name: 'Moulika Devi',
      is_admin: true,
      email: 'owner@example.com',
      password: 'test password',
    });
    expect(screen.getByRole('heading', { name: 'Welcome back, Moulika Devi.' })).toBeVisible();
    expect(
      within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
        /Knowledge team|Aster Technologies|Your organisation/,
      ),
    ).toHaveTextContent('Knowledge team');
  });
  it('keeps rejected sign-in on the sign-in screen', async () => {
    customize = (path) =>
      path === '/api/auth/login' ? json({ detail: 'Invalid credentials' }, 401) : undefined;
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Email'), 'owner@example.com');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /Continue to workspace/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
    expect(screen.queryByRole('heading', { name: 'Ask your documents.' })).not.toBeInTheDocument();
  });
  it('uploads real multipart data, refreshes the list and confirms deletion', async () => {
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: /My documents/ }));
    const file = new File(['The office opens at nine.'], 'policy.txt', { type: 'text/plain' });
    await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(screen.getByLabelText('Add a document'), file);
    await user.click(screen.getByRole('button', { name: /Upload document/ }));
    expect(await screen.findByRole('heading', { name: 'policy.txt' })).toBeInTheDocument();
    expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Delete policy.txt' }));
    const modal = screen.getByRole('dialog');
    expect(calls.filter((c) => c.options.method === 'DELETE')).toHaveLength(0);
    await user.click(within(modal).getByRole('button', { name: 'Delete document' }));
    await screen.findByRole('heading', { name: 'No documents yet.' });
    expect(calls.filter((c) => c.options.method === 'DELETE')).toHaveLength(1);
  });
  it('does not delete when the confirmation is cancelled', async () => {
    docs = [{ id: 12, title: 'policy.txt', enterprise_id: 7, created_at: '2026-11-12T09:00:00Z' }];
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    await user.click(await screen.findByRole('button', { name: 'Delete policy.txt' }));
    await user.click(screen.getByRole('button', { name: 'Keep document' }));
    expect(calls.filter((c) => c.options.method === 'DELETE')).toHaveLength(0);
  });
  it('uses server limits to reject oversized files before sending', async () => {
    customize = (path) =>
      path === '/api/documents/limits'
        ? json({ allowed_extensions: ['.txt'], max_upload_bytes: 3 })
        : undefined;
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(
      screen.getByLabelText('Add a document'),
      new File(['too big'], 'policy.txt', { type: 'text/plain' }),
    );
    await user.click(screen.getByRole('button', { name: /Upload document/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('no larger than');
    expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(0);
  });
  it('shows provider upload failures without inventing a successful document', async () => {
    customize = (path) =>
      path === '/api/documents/upload'
        ? json({ detail: 'Embedding provider unavailable. Try again later.' }, 503)
        : undefined;
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(
      screen.getByLabelText('Add a document'),
      new File(['text'], 'policy.txt', { type: 'text/plain' }),
    );
    await user.click(screen.getByRole('button', { name: /Upload document/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Upload failed. Please try again.');
    expect(screen.queryByRole('heading', { name: 'policy.txt' })).not.toBeInTheDocument();
  });
  it('renders source documents and keeps them across navigation', async () => {
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'When does the office open?');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    expect(
      await screen.findByRole('button', { name: 'View source 1: policy.txt' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'View source 1: policy.txt' }));
    const sources = screen.getByRole('complementary', { name: 'Source documents' });
    expect(within(sources).getByRole('heading', { name: 'policy.txt' })).toBeVisible();
    expect(within(sources).queryByText('The office opens at nine.')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    await user.click(screen.getByRole('button', { name: 'Ask documents' }));
    expect(screen.getByRole('button', { name: 'View source 1: policy.txt' })).toBeVisible();
    expect(calls.filter((c) => c.path === '/api/chat/generate')).toHaveLength(1);
  });
  it('renders untrusted model text as text, not executable markup', async () => {
    customize = (path) =>
      path === '/api/chat/generate'
        ? json({
            answer: 'Safe answer.\n\n<img src=x onerror=alert(1)>',
            sources: [],
            citations: [],
          })
        : undefined;
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'Question');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    expect(await screen.findByText('Safe answer.')).toBeInTheDocument();
    expect(document.querySelector('img[src="x"]')).toBeNull();
  });
  it('keeps an answer-provider failure separate from an answer', async () => {
    customize = (path) =>
      path === '/api/chat/generate'
        ? json({ detail: 'Answer provider unavailable. Try again later.' }, 503)
        : undefined;
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'When?');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Answer provider unavailable');
    expect(screen.queryByText('The office opens at nine [1].')).not.toBeInTheDocument();
  });
  it('hides administrator mutations for ordinary members', async () => {
    role = 'employee';
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    expect(screen.queryByLabelText('Add a document')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Upload document/ })).not.toBeInTheDocument();
  });
  it('ends an expired session and clears old workspace content', async () => {
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'When?');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    await screen.findByRole('button', { name: 'View source 1: policy.txt' });
    customize = (path) =>
      path === '/api/documents/list'
        ? json({ detail: 'Could not validate credentials' }, 401)
        : undefined;
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    await user.click(screen.getByRole('button', { name: 'Refresh documents' }));
    await screen.findByRole('heading', { level: 2, name: 'Welcome back.' });
    expect(screen.queryByText('The office opens at nine [1].')).not.toBeInTheDocument();
  });
  it('clears the workspace on explicit sign-out', async () => {
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'Account menu' }));
    if (!screen.queryByRole('menuitem', { name: 'Sign out' }))
      await user.click(screen.getByRole('button', { name: 'Account menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    await user.click(
      within(screen.getByRole('dialog', { name: 'Sign out of Atlas?' })).getByRole('button', {
        name: 'Sign out',
      }),
    );
    await screen.findByRole('heading', { level: 2, name: 'Welcome back.' });
    expect(screen.queryByText('owner@example.com')).not.toBeInTheDocument();
  });
});
it('sends a pending question once even when submit is clicked twice', async () => {
  let finish!: (response: Response) => void;
  customize = (path) =>
    path === '/api/chat/generate'
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : undefined;
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'When?');
  const button = screen.getByRole('button', { name: /Ask question/ });
  await user.dblClick(button);
  await waitFor(() => expect(calls.filter((c) => c.path === '/api/chat/generate')).toHaveLength(1));
  expect(button).toBeDisabled();
  finish(json({ answer: 'A supported answer.', sources: [], citations: [] }));
  await screen.findByText('A supported answer.');
});
it('requires a list refresh after an uncertain upload without retrying it', async () => {
  customize = (path) =>
    path === '/api/documents/upload' ? Promise.reject(new TypeError('Connection lost')) : undefined;
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
  await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
  await user.upload(
    screen.getByLabelText('Add a document'),
    new File(['text'], 'policy.txt', { type: 'text/plain' }),
  );
  await user.click(screen.getByRole('button', { name: /Upload document/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('result is uncertain');
  expect(screen.getByRole('button', { name: /Upload document/ })).toBeDisabled();
  expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: 'Refresh documents' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Upload document/ })).toBeEnabled(),
  );
  expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(1);
});
it('does not show motion controls on sign-in or in the workspace', async () => {
  const user = await signIn();
  expect(
    screen.queryByRole('button', { name: /Pause motion|Resume motion|Motion off/ }),
  ).not.toBeInTheDocument();
  if (!screen.queryByRole('menuitem', { name: 'Sign out' }))
    await user.click(screen.getByRole('button', { name: 'Account menu' }));
  await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
  await user.click(
    within(screen.getByRole('dialog', { name: 'Sign out of Atlas?' })).getByRole('button', {
      name: 'Sign out',
    }),
  );
  expect(
    screen.queryByRole('button', { name: /Pause motion|Resume motion|Motion off/ }),
  ).not.toBeInTheDocument();
});
it('honours the reduced-motion system preference without displaying a toggle', async () => {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  const { container } = render(<App />);
  await waitFor(() =>
    expect(container.querySelector('.pa-theme')).toHaveAttribute('data-motion', 'paused'),
  );
  expect(screen.queryByRole('button', { name: /motion/i })).not.toBeInTheDocument();
});
it('blocks another delete after a gateway timeout until the list is refreshed', async () => {
  docs = [{ id: 12, title: 'policy.txt', enterprise_id: 7, created_at: '2026-11-12T09:00:00Z' }];
  customize = (path, options) =>
    path === '/api/documents/12' && options.method === 'DELETE'
      ? new Response('Gateway timeout', { status: 504 })
      : undefined;
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  await user.click(await screen.findByRole('button', { name: 'Delete policy.txt' }));
  const modal = screen.getByRole('dialog');
  await user.click(within(modal).getByRole('button', { name: 'Delete document' }));
  expect(await within(modal).findByRole('alert')).toHaveTextContent('could not confirm');
  expect(within(modal).getByRole('button', { name: 'Delete document' })).toBeDisabled();
  expect(calls.filter((c) => c.options.method === 'DELETE')).toHaveLength(1);
  await user.click(within(modal).getByRole('button', { name: 'Close and refresh' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(calls.filter((c) => c.options.method === 'DELETE')).toHaveLength(1);
});

it('offers Members to administrators and creates a real account through the API', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await screen.findByRole('heading', { name: 'Your workspace team.' });
  await user.type(screen.getByLabelText('Member name'), 'Sam Taylor');
  await user.type(screen.getByLabelText('Member email'), 'staff@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'initial password');
  await user.click(screen.getByRole('button', { name: 'Add member ↗' }));
  expect(await screen.findByRole('heading', { name: 'Sam Taylor' })).toBeInTheDocument();
  expect(screen.getByLabelText('Initial password')).toHaveValue('');
  expect(calls.filter((c) => c.path === '/api/users/create_user')).toHaveLength(1);
  expect(
    JSON.parse(String(calls.find((c) => c.path === '/api/users/create_user')?.options.body)),
  ).toEqual({
    name: 'Sam Taylor',
    email: 'staff@example.com',
    password: 'initial password',
    role: 'employee',
  });
});
it('does not expose Members to ordinary workspace members', async () => {
  role = 'employee';
  await signIn();
  expect(screen.queryByRole('button', { name: 'Members' })).not.toBeInTheDocument();
  expect(calls.filter((c) => c.path === '/api/users/get_all_users')).toHaveLength(0);
});
it('lists real roles and protects the signed-in account from removal', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await screen.findByRole('heading', { name: 'owner@example.com' });
  expect(screen.getByRole('button', { name: 'Remove owner@example.com' })).toBeDisabled();
  expect(screen.getByText('You')).toBeInTheDocument();
});
it('requires confirmation before removing a member and refreshes the list', async () => {
  members.push({
    id: 2,
    email: 'staff@example.com',
    role: 'employee',
    enterprise_id: 7,
    is_active: true,
    created_at: '2026-11-12T09:00:00Z',
  });
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await user.click(await screen.findByRole('button', { name: 'Remove staff@example.com' }));
  expect(calls.filter((c) => c.path === '/api/users/delete_user/2')).toHaveLength(0);
  await user.click(
    within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove member' }),
  );
  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'staff@example.com' })).not.toBeInTheDocument(),
  );
  expect(calls.filter((c) => c.path === '/api/users/delete_user/2')).toHaveLength(1);
});
it('leaves a member intact when removal is cancelled', async () => {
  members.push({
    id: 2,
    email: 'staff@example.com',
    role: 'employee',
    enterprise_id: 7,
    is_active: true,
    created_at: '2026-11-12T09:00:00Z',
  });
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await user.click(await screen.findByRole('button', { name: 'Remove staff@example.com' }));
  await user.click(screen.getByRole('button', { name: 'Keep member' }));
  expect(calls.filter((c) => c.path === '/api/users/delete_user/2')).toHaveLength(0);
});
it('shows duplicate-account errors and clears the password', async () => {
  customize = (path) =>
    path === '/api/users/create_user'
      ? json({ detail: 'An account already uses this email' }, 409)
      : undefined;
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await user.type(screen.getByLabelText('Member email'), 'staff@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'initial password');
  await user.click(screen.getByRole('button', { name: 'Add member ↗' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('already uses this email');
  expect(screen.getByLabelText('Initial password')).toHaveValue('');
});
it('blocks repeating an uncertain account creation until the list is refreshed', async () => {
  customize = (path) =>
    path === '/api/users/create_user' ? Promise.reject(new TypeError('network lost')) : undefined;
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await user.type(screen.getByLabelText('Member email'), 'staff@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'initial password');
  await user.click(screen.getByRole('button', { name: 'Add member ↗' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('uncertain');
  expect(screen.getByRole('button', { name: 'Add member ↗' })).toBeDisabled();
  expect(screen.getByLabelText('Initial password')).toHaveValue('');
  await user.click(screen.getByRole('button', { name: 'Refresh members' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add member ↗' })).toBeEnabled());
  expect(calls.filter((c) => c.path === '/api/users/create_user')).toHaveLength(1);
});
it('lets administrators assign the administrator role explicitly', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await user.type(screen.getByLabelText('Member email'), 'admin@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'initial password');
  await user.selectOptions(screen.getByLabelText('Account role'), 'admin');
  await user.click(screen.getByRole('button', { name: 'Add member ↗' }));
  await screen.findByRole('heading', { name: 'admin@example.com' });
  expect(
    JSON.parse(String(calls.find((c) => c.path === '/api/users/create_user')?.options.body)).role,
  ).toBe('admin');
});
it('filters the account list by email', async () => {
  members.push({
    id: 2,
    email: 'staff@example.com',
    role: 'employee',
    enterprise_id: 7,
    is_active: true,
    created_at: '2026-11-12T09:00:00Z',
  });
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  await screen.findByRole('heading', { name: 'staff@example.com' });
  await user.type(screen.getByLabelText('Find a member'), 'staff');
  expect(screen.queryByRole('heading', { name: 'owner@example.com' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'staff@example.com' })).toBeInTheDocument();
});

it('filters personal documents and scopes chat to the selected document', async () => {
  role = 'employee';
  docs = [
    {
      id: 12,
      title: 'My offer.txt',
      visibility: 'personal',
      recipient_ids: [1],
      enterprise_id: 7,
      created_at: '2026-11-12T09:00:00Z',
    },
    {
      id: 13,
      title: 'Company policy.txt',
      visibility: 'company',
      enterprise_id: 7,
      created_at: '2026-11-12T09:00:00Z',
    },
  ];
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  await user.click(screen.getByRole('button', { name: /Personal documents/ }));
  expect(screen.getByRole('heading', { name: 'My offer.txt' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Company policy.txt' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Manage access' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Ask about this' }));
  expect(screen.getByText('Searching only: My offer.txt')).toBeInTheDocument();
  await user.type(screen.getByLabelText('Your question'), 'When do I start?');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  await waitFor(() => expect(calls.some((c) => c.path === '/api/chat/generate')).toBe(true));
  expect(
    JSON.parse(String(calls.find((c) => c.path === '/api/chat/generate')!.options.body)),
  ).toEqual({ question: 'When do I start?', document_id: 12 });
  await user.click(screen.getByRole('button', { name: 'Search all my documents' }));
  expect(screen.queryByText('Searching only: My offer.txt')).not.toBeInTheDocument();
});

it('assigns personal access atomically with the original upload', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
  await user.selectOptions(screen.getByLabelText('Document access'), 'personal');
  await user.selectOptions(screen.getByLabelText('Employee'), '1');
  await user.upload(
    screen.getByLabelText('Add a document'),
    new File(['Offer terms'], 'offer.txt', { type: 'text/plain' }),
  );
  await user.click(screen.getByRole('button', { name: /Upload document/ }));
  await screen.findByRole('heading', { name: 'offer.txt' });
  const body = calls.find((c) => c.path === '/api/documents/upload')!.options.body as FormData;
  expect(JSON.parse(String(body.get('access')))).toEqual({
    visibility: 'personal',
    recipient_ids: [1],
  });
});

it('shows failed indexing and extraction notes and queues an administrator retry', async () => {
  docs = [
    {
      id: 12,
      title: 'policy.pdf',
      enterprise_id: 7,
      created_at: '2026-11-12T09:00:00Z',
      index_status: 'failed',
      index_error: 'Upload failed. Try again.',
      extraction_warnings: ['Page 2 has no extractable text.'],
    },
  ];
  customize = (path) => {
    if (path === '/api/documents/12/reindex') {
      docs = docs.map((document) => ({ ...document, index_status: 'queued' }));
      return json(docs[0], 202);
    }
    return undefined;
  };
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  expect(await screen.findByText('Upload failed. Try again.')).toBeVisible();
  await user.click(screen.getByText('Source extraction notes'));
  expect(screen.getByText('Page 2 has no extractable text.')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Uploading document…')).toBeVisible();
  expect(calls.filter((call) => call.path === '/api/documents/12/reindex')).toHaveLength(1);
});

it('shows original PDF page spans beside source citations', async () => {
  customize = (path) =>
    path === '/api/chat/generate'
      ? json({
          answer: 'Gross pay is INR 100,000 [1].',
          sources: [12],
          citations: [
            {
              document_id: 12,
              title: 'offer.pdf',
              chunk_index: 0,
              excerpt: 'Source evidence.',
              page_start: 1,
              page_end: 2,
              section: 'Compensation',
            },
          ],
        })
      : undefined;
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'What is my gross pay?');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  expect(await screen.findByText('Pages 1–2')).toBeVisible();
  expect(screen.queryByText('Source evidence.')).not.toBeInTheDocument();
});

it('groups citations by document and opens the selected reference page through the authenticated file API', async () => {
  const OriginalURL = URL;
  vi.stubGlobal(
    'URL',
    class extends OriginalURL {
      static createObjectURL() {
        return 'blob:pdf-source';
      }
      static revokeObjectURL() {}
    },
  );
  customize = (path) => {
    if (path === '/api/documents/12/file')
      return new Response('PDF preview fixture', {
        headers: { 'Content-Type': 'application/pdf' },
      });
    if (path !== '/api/chat/generate') return undefined;
    return json({
      answer: 'The role is described here [3]. Joining details are here [7].',
      sources: [12],
      citations: [
        {
          marker: 3,
          document_id: 12,
          title: 'offer.pdf',
          chunk_index: 1,
          page_start: 2,
          excerpt: 'Role excerpt.',
        },
        {
          marker: 7,
          document_id: 12,
          title: 'offer.pdf',
          chunk_index: 6,
          page_start: 8,
          excerpt: 'Joining excerpt.',
        },
      ],
    });
  };
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'Explain the role and joining details');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  await screen.findByRole('button', { name: 'View source 7: offer.pdf' });
  const sidebar = screen.getByRole('complementary', { name: 'Source documents' });
  expect(within(sidebar).getAllByRole('heading', { name: 'offer.pdf' })).toHaveLength(1);
  expect(within(sidebar).getByText('References [3], [7]')).toBeVisible();
  expect(within(sidebar).queryByText('Role excerpt.')).not.toBeInTheDocument();
  expect(within(sidebar).queryByText('Joining excerpt.')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'View source 7: offer.pdf' }));
  await user.click(within(sidebar).getByRole('button', { name: 'View document: offer.pdf' }));
  expect(await screen.findByTitle('offer.pdf')).toHaveAttribute('src', 'blob:pdf-source#page=8');
  const request = calls.find((call) => call.path === '/api/documents/12/file')!;
  expect((request.options.headers as Headers).get('Authorization')).toBe('Bearer test-session');
  await user.click(screen.getByRole('button', { name: 'View source 3: offer.pdf' }));
  await user.click(within(sidebar).getByRole('button', { name: 'View document: offer.pdf' }));
  expect(screen.getByTitle('offer.pdf')).toHaveAttribute('src', 'blob:pdf-source#page=2');
  expect(calls.filter((call) => call.path === '/api/documents/12/file')).toHaveLength(1);
});

it.each([
  ['admin', 'Moulika Devi'],
  ['employee', 'Alice Morgan'],
] as const)(
  'welcomes a named %s and keeps the organisation header on every page',
  async (accountRole, name) => {
    role = accountRole;
    customize = (path) =>
      path === '/api/users/me'
        ? json({
            id: 1,
            name,
            email: 'owner@example.com',
            role: accountRole,
            enterprise_id: 7,
            enterprise_name: 'Aster Technologies',
            is_active: true,
          })
        : undefined;
    const user = await signIn();
    expect(
      within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
        /Knowledge team|Aster Technologies|Your organisation/,
      ),
    ).toHaveTextContent('Aster Technologies');
    expect(document.title).toBe('Ask documents · Aster Technologies | Atlas');
    await user.click(screen.getByRole('button', { name: 'Atlas home' }));
    expect(screen.getByRole('heading', { name: `Welcome back, ${name}.` })).toBeVisible();
    expect(document.title).toBe('Overview · Aster Technologies | Atlas');
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    expect(
      within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
        /Knowledge team|Aster Technologies|Your organisation/,
      ),
    ).toHaveTextContent('Aster Technologies');
    expect(document.title).toBe('My documents · Aster Technologies | Atlas');
    await user.click(screen.getByRole('button', { name: 'Ask documents' }));
    expect(
      within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
        /Knowledge team|Aster Technologies|Your organisation/,
      ),
    ).toHaveTextContent('Aster Technologies');
    await user.click(screen.getByRole('button', { name: 'Account menu' }));
    if (!screen.queryByRole('menuitem', { name: 'Sign out' }))
      await user.click(screen.getByRole('button', { name: 'Account menu' }));
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    await user.click(
      within(screen.getByRole('dialog', { name: 'Sign out of Atlas?' })).getByRole('button', {
        name: 'Sign out',
      }),
    );
    expect(
      screen.queryByRole('complementary', { name: 'Organisation navigation' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(`Welcome back, ${name}.`)).not.toBeInTheDocument();
    expect(document.title).toBe('Sign in | Atlas');
  },
);

it('uses an organisation fallback instead of an internal workspace ID when a legacy profile has no name', async () => {
  customize = (path) =>
    path === '/api/users/me'
      ? json({
          id: 1,
          email: 'owner@example.com',
          role: 'admin',
          enterprise_id: 2,
          is_active: true,
        })
      : undefined;
  const user = await signIn();
  expect(
    within(screen.getByRole('complementary', { name: 'Organisation navigation' })).getByText(
      /Knowledge team|Aster Technologies|Your organisation/,
    ),
  ).toHaveTextContent('Your organisation');
  const navigation = screen.getByRole('complementary', { name: 'Organisation navigation' });
  expect(within(navigation).getByText('Your organisation')).toBeVisible();
  expect(screen.queryByText(/Workspace #\d/)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  expect(await screen.findByText('Manage sign-in accounts in your organisation.')).toBeVisible();
  expect(document.title).toBe('Members · Your organisation | Atlas');
});

it('opens the overview after sign-in with live document counts and recent files', async () => {
  docs = [
    {
      id: 12,
      title: 'handbook.pdf',
      enterprise_id: 7,
      created_at: '2026-11-13T09:00:00Z',
      index_status: 'ready',
      visibility: 'company',
    },
    {
      id: 13,
      title: 'offer.pdf',
      enterprise_id: 7,
      created_at: '2026-11-12T09:00:00Z',
      index_status: 'queued',
      visibility: 'personal',
    },
    {
      id: 14,
      title: 'needs-ocr.pdf',
      enterprise_id: 7,
      created_at: '2026-11-11T09:00:00Z',
      index_status: 'failed',
      visibility: 'company',
    },
  ];
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Overview' }));
  expect(screen.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  expect(screen.queryByText('Available documents')).not.toBeInTheDocument();
  expect(
    within(screen.getByRole('region', { name: 'Welcome back.' })).getByText('handbook.pdf'),
  ).toBeVisible();
  expect(screen.getByText(/1 personal document, alongside/)).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'View all documents ↗' }));
  expect(screen.getByRole('heading', { name: 'Your documents, together.' })).toBeVisible();
});

it('keeps the overview useful for members without administrator actions', async () => {
  role = 'employee';
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Overview' }));
  expect(screen.getByText('Start your knowledge library.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Browse my documents' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Manage members' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add your first document' })).not.toBeInTheDocument();
});

it('hides workspace creation when public registration is disabled', async () => {
  customize = (path) =>
    path === '/api/auth/config' ? json({ registration_enabled: false }) : undefined;
  render(<App />);
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Create workspace' })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole('button', { name: /Continue to workspace/ })).toBeVisible();
});

it('keeps sources beside the conversation and switches them when an older citation is selected', async () => {
  let answerNumber = 0;
  customize = (path) => {
    if (path !== '/api/chat/generate') return undefined;
    answerNumber += 1;
    const title = answerNumber === 1 ? 'first-policy.pdf' : 'second-policy.pdf';
    return json({
      answer: `Policy answer ${answerNumber} [1].`,
      sources: [answerNumber],
      citations: [
        {
          document_id: answerNumber,
          title,
          chunk_index: 0,
          excerpt: `Evidence from ${title}`,
          page_start: 1,
        },
      ],
    });
  };
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'First question');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  await screen.findByRole('button', { name: 'View source 1: first-policy.pdf' });
  await user.type(screen.getByLabelText('Your question'), 'Second question');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  await screen.findByRole('button', { name: 'View source 1: second-policy.pdf' });
  const sources = screen.getByRole('complementary', { name: 'Source documents' });
  expect(within(sources).getByText('second-policy.pdf')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'View source 1: first-policy.pdf' }));
  expect(within(sources).getByText('first-policy.pdf')).toBeVisible();
  expect(within(sources).queryByText('second-policy.pdf')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Clear conversation' }));
  expect(within(sources).getByText(/Relevant documents will appear here/)).toBeVisible();
});

it('opens the existing upload form from the document library toolbar', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  expect(screen.getByLabelText('Add a document')).not.toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Upload documents ↗' }));
  expect(screen.getByLabelText('Add a document')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Close upload' }));
  expect(screen.getByLabelText('Add a document')).not.toBeVisible();
});

it('does not show older evidence as sources for a later answer without citations', async () => {
  let requests = 0;
  customize = (path) => {
    if (path !== '/api/chat/generate') return undefined;
    requests += 1;
    return requests === 1
      ? json({
          answer: 'A supported answer [1].',
          sources: [1],
          citations: [
            { document_id: 1, title: 'earlier.pdf', chunk_index: 0, excerpt: 'Earlier evidence.' },
          ],
        })
      : json({
          answer: 'No usable excerpts were found for this question.',
          sources: [],
          citations: [],
        });
  };
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'Supported question');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  await screen.findByRole('button', { name: 'View source 1: earlier.pdf' });
  await user.type(screen.getByLabelText('Your question'), 'Unsupported question');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  const sources = screen.getByRole('complementary', { name: 'Source documents' });
  expect(
    await within(sources).findByText('No source documents were returned for this answer.'),
  ).toBeVisible();
  expect(within(sources).queryByText('earlier.pdf')).not.toBeInTheDocument();
});

it('keeps the library focused on documents and access without format/indexing columns', async () => {
  docs = [
    {
      id: 12,
      title: 'Offer.pdf',
      enterprise_id: 7,
      created_at: '2026-11-12T09:00:00Z',
      visibility: 'personal',
      index_status: 'ready',
    },
  ];
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'My documents' }));
  const library = screen.getByRole('list', { name: 'Workspace documents' });
  expect(within(library).getByRole('heading', { name: 'Offer.pdf' })).toBeVisible();
  expect(within(library).getByText('Personal')).toBeVisible();
  expect(within(library).queryByText('PDF')).not.toBeInTheDocument();
  expect(within(library).queryByText('Ready')).not.toBeInTheDocument();
  expect(screen.queryByText('Format')).not.toBeInTheDocument();
  expect(screen.queryByText('Indexing')).not.toBeInTheDocument();
});

it('distinguishes account-based replies from missing document evidence', async () => {
  customize = (path) =>
    path === '/api/chat/generate'
      ? json({
          answer: 'You are signed in as Alice Morgan.',
          answer_origin: 'account_context',
          citation_status: 'not_applicable',
          sources: [],
          citations: [],
        })
      : undefined;
  const user = await signIn();
  await user.type(screen.getByLabelText('Your question'), 'Who am I?');
  await user.click(screen.getByRole('button', { name: /Ask question/ }));
  expect(await screen.findByText('You are signed in as Alice Morgan.')).toBeVisible();
  expect(
    within(screen.getByRole('complementary', { name: 'Source documents' })).getByText(
      /This response uses your signed-in account or document assignments/,
    ),
  ).toBeVisible();
});

it('edits member names and email addresses without displaying account numbers', async () => {
  members.push({
    id: 2,
    name: 'Alice Morgan',
    email: 'alice@example.com',
    role: 'employee',
    enterprise_id: 7,
    is_active: true,
    created_at: '2026-11-12T09:00:00Z',
  });
  customize = (path, options) => {
    if (path !== '/api/users/2') return undefined;
    const values = JSON.parse(String(options.body));
    members = members.map((member) => (member.id === 2 ? { ...member, ...values } : member));
    return json(members.find((member) => member.id === 2));
  };
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Members' }));
  const heading = await screen.findByRole('heading', { name: 'Alice Morgan' });
  await user.click(within(heading.closest('li')!).getByRole('button', { name: 'Edit details' }));
  const editor = screen.getByRole('region', { name: 'Edit member details' });
  await user.clear(within(editor).getByLabelText('Full name'));
  await user.type(within(editor).getByLabelText('Full name'), 'Alice Reed');
  await user.clear(within(editor).getByLabelText('Email address'));
  await user.type(within(editor).getByLabelText('Email address'), 'alice.reed@example.com');
  await user.click(within(editor).getByRole('button', { name: 'Save details' }));
  expect(await screen.findByRole('heading', { name: 'Alice Reed' })).toBeVisible();
  expect(screen.queryByText(/Account #/)).not.toBeInTheDocument();
  expect(
    JSON.parse(String(calls.find((call) => call.path === '/api/users/2')!.options.body)),
  ).toEqual({ name: 'Alice Reed', email: 'alice.reed@example.com' });
});
