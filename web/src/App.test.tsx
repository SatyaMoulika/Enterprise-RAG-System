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
        return json({ id: 1, email: 'owner@example.com', role, enterprise_id: 7, is_active: true });
      if (path === '/api/users/get_all_users') return json(members);
      if (path === '/api/users/create_user') {
        const values = JSON.parse(String(options.body));
        const member: Member = {
          id: Math.max(0, ...members.map((m) => m.id)) + 1,
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
  await screen.findByRole('heading', { name: 'Ask your documents.' });
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
    expect(screen.getByText('Workspace #7')).toBeInTheDocument();
  });
  it('creates a workspace and validates its session before entering', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Create workspace' }));
    await user.type(screen.getByLabelText('Workspace name'), 'Knowledge team');
    await user.type(screen.getByLabelText('Email'), 'owner@example.com');
    await user.type(screen.getByLabelText('Password'), 'test password');
    await user.click(screen.getByRole('button', { name: /Create my workspace/ }));
    await screen.findByRole('heading', { name: 'Ask your documents.' });
    expect(
      JSON.parse(String(calls.find((c) => c.path === '/api/auth/register')?.options.body)),
    ).toMatchObject({ enterprise_name: 'Knowledge team' });
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
    await user.click(screen.getByRole('button', { name: /Documents/ }));
    const file = new File(['The office opens at nine.'], 'policy.txt', { type: 'text/plain' });
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(screen.getByLabelText('Add a document'), file);
    await user.click(screen.getByRole('button', { name: /Upload and index/ }));
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
    await user.click(screen.getByRole('button', { name: 'Documents' }));
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
    await user.click(screen.getByRole('button', { name: 'Documents' }));
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(
      screen.getByLabelText('Add a document'),
      new File(['too big'], 'policy.txt', { type: 'text/plain' }),
    );
    await user.click(screen.getByRole('button', { name: /Upload and index/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('no larger than');
    expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(0);
  });
  it('shows provider upload failures without inventing a successful document', async () => {
    customize = (path) =>
      path === '/api/documents/upload'
        ? json({ detail: 'Embedding provider unavailable. Try again later.' }, 503)
        : undefined;
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'Documents' }));
    await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
    await user.upload(
      screen.getByLabelText('Add a document'),
      new File(['text'], 'policy.txt', { type: 'text/plain' }),
    );
    await user.click(screen.getByRole('button', { name: /Upload and index/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Embedding provider unavailable');
    expect(screen.queryByRole('heading', { name: 'policy.txt' })).not.toBeInTheDocument();
  });
  it('renders answers and expandable excerpts and keeps them across navigation', async () => {
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'When does the office open?');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    expect(await screen.findByText('The office opens at nine [1].')).toBeInTheDocument();
    await user.click(screen.getByText('[1] policy.txt · excerpt 1'));
    expect(screen.getByText('The office opens at nine.')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Documents' }));
    await user.click(screen.getByRole('button', { name: 'Ask documents' }));
    expect(screen.getByText('The office opens at nine [1].')).toBeVisible();
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
    await user.click(screen.getByRole('button', { name: 'Documents' }));
    expect(screen.queryByLabelText('Add a document')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Upload and index/ })).not.toBeInTheDocument();
  });
  it('ends an expired session and clears old workspace content', async () => {
    const user = await signIn();
    await user.type(screen.getByLabelText('Your question'), 'When?');
    await user.click(screen.getByRole('button', { name: /Ask question/ }));
    await screen.findByText('The office opens at nine [1].');
    customize = (path) =>
      path === '/api/documents/list'
        ? json({ detail: 'Could not validate credentials' }, 401)
        : undefined;
    await user.click(screen.getByRole('button', { name: 'Documents' }));
    await user.click(screen.getByRole('button', { name: 'Refresh documents' }));
    await screen.findByRole('heading', { name: 'Welcome back.' });
    expect(screen.queryByText('The office opens at nine [1].')).not.toBeInTheDocument();
  });
  it('clears the workspace on explicit sign-out', async () => {
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    await screen.findByRole('heading', { name: 'Welcome back.' });
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
  await user.click(screen.getByRole('button', { name: 'Documents' }));
  await waitFor(() => expect(screen.getByLabelText('Add a document')).toBeEnabled());
  await user.upload(
    screen.getByLabelText('Add a document'),
    new File(['text'], 'policy.txt', { type: 'text/plain' }),
  );
  await user.click(screen.getByRole('button', { name: /Upload and index/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('result is uncertain');
  expect(screen.getByRole('button', { name: /Upload and index/ })).toBeDisabled();
  expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: 'Refresh documents' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Upload and index/ })).toBeEnabled(),
  );
  expect(calls.filter((c) => c.path === '/api/documents/upload')).toHaveLength(1);
});
it('pauses shared AI motion from the global control', async () => {
  const user = userEvent.setup();
  const { container } = render(<App />);
  await user.click(screen.getByRole('button', { name: 'Pause motion' }));
  expect(container.querySelector('.pa-theme')).toHaveAttribute('data-motion', 'paused');
  expect(screen.getByRole('button', { name: 'Resume motion' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});
it('honours the reduced-motion system preference', async () => {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  const { container } = render(<App />);
  expect(
    await screen.findByRole('button', { name: 'Motion off · system preference' }),
  ).toBeDisabled();
  expect(container.querySelector('.pa-theme')).toHaveAttribute('data-motion', 'paused');
});
it('blocks another delete after a gateway timeout until the list is refreshed', async () => {
  docs = [{ id: 12, title: 'policy.txt', enterprise_id: 7, created_at: '2026-11-12T09:00:00Z' }];
  customize = (path, options) =>
    path === '/api/documents/12' && options.method === 'DELETE'
      ? new Response('Gateway timeout', { status: 504 })
      : undefined;
  const user = await signIn();
  await user.click(screen.getByRole('button', { name: 'Documents' }));
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
  await user.type(screen.getByLabelText('Member email'), 'staff@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'initial password');
  await user.click(screen.getByRole('button', { name: 'Add member ↗' }));
  expect(await screen.findByRole('heading', { name: 'staff@example.com' })).toBeInTheDocument();
  expect(screen.getByLabelText('Initial password')).toHaveValue('');
  expect(calls.filter((c) => c.path === '/api/users/create_user')).toHaveLength(1);
  expect(
    JSON.parse(String(calls.find((c) => c.path === '/api/users/create_user')?.options.body)),
  ).toEqual({ email: 'staff@example.com', password: 'initial password', role: 'employee' });
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
