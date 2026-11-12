import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Badge, Button, Card, Eyebrow, InputField, SelectField } from '@portfolio/porcelain-azure';
import { ApiClient, ApiError, errorMessage, isCancelled } from '../api/client';
import type { Member, User } from '../api/types';
import { Feedback } from './Feedback';
import { ConfirmationDialog } from './ConfirmationDialog';

export function MembersPanel({ api, currentUser }: { api: ApiClient; currentUser: User }) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const [selected, setSelected] = useState<Member | null>(null);
  const [removeError, setRemoveError] = useState('');
  const [removing, setRemoving] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const pending = useRef(false);
  const loader = useRef<AbortController | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    loader.current?.abort();
    const controller = new AbortController();
    loader.current = controller;
    setLoading(true);
    try {
      const result = await api.members(controller.signal);
      if (controller.signal.aborted) return;
      setMembers(result);
      setError('');
      setUncertain(false);
    } catch (error) {
      if (!isCancelled(error)) {
        setError(errorMessage(error));
        if (error instanceof ApiError && error.status === 403) setMembers(null);
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [api]);
  useEffect(() => {
    lifetime.current = new AbortController();
    void load();
    return () => {
      loader.current?.abort();
      lifetime.current?.abort();
    };
  }, [load]);
  function clearPassword() {
    const field = form.current?.elements.namedItem('password');
    if (field instanceof HTMLInputElement) field.value = '';
  }
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || uncertain) return;
    const values = new FormData(event.currentTarget);
    const email = String(values.get('email') || '').trim();
    const password = String(values.get('password') || '');
    const role = values.get('role') === 'admin' ? 'admin' : 'employee';
    pending.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api.createMember({ email, password, role }, lifetime.current?.signal);
      form.current?.reset();
      setNotice(`${result.email} can now sign in. Share the initial password securely.`);
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setError(errorMessage(error));
        setUncertain(error instanceof ApiError && error.uncertain);
      }
    } finally {
      clearPassword();
      pending.current = false;
      if (!lifetime.current?.signal.aborted) setBusy(false);
    }
  }
  async function remove() {
    if (!selected || pending.current || uncertain) return;
    pending.current = true;
    setRemoving(true);
    setRemoveError('');
    setNotice('');
    try {
      await api.removeMember(selected.id, lifetime.current?.signal);
      setNotice(`${selected.email} has been removed from the workspace.`);
      setSelected(null);
      await load();
    } catch (error) {
      if (!isCancelled(error)) {
        setRemoveError(errorMessage(error));
        setUncertain(error instanceof ApiError && error.uncertain);
      }
    } finally {
      pending.current = false;
      if (!lifetime.current?.signal.aborted) setRemoving(false);
    }
  }
  const filtered = members?.filter((member) =>
    member.email.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <section aria-labelledby="members-heading">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow>Members / Organisation access</Eyebrow>
          <h1 id="members-heading" className="mt-2 text-3xl font-bold tracking-tight">
            Your workspace team.
          </h1>
          <p className="mt-2 text-xs text-muted">
            Manage sign-in accounts in Workspace #{currentUser.enterprise_id}.
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={loading || busy || removing}
          onClick={() => void load()}
        >
          {loading ? 'Refreshing…' : 'Refresh members'}
        </Button>
      </div>
      <Card className="mb-6 bg-soft/35 p-5">
        <h2 className="text-lg font-bold">Add a member</h2>
        <p className="mb-5 mt-2 text-xs leading-6 text-muted">
          Creates an account immediately. Members can read documents and ask questions;
          administrators also manage documents and accounts. Share the initial password securely.
        </p>
        <form ref={form} onSubmit={add} aria-label="Add member" className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <InputField
              label="Member email"
              name="email"
              type="email"
              required
              autoComplete="off"
              disabled={busy || removing || uncertain}
            />
            <InputField
              label="Initial password"
              name="password"
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              hint="8–128 characters. This field clears after every submission."
              disabled={busy || removing || uncertain}
            />
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-48 flex-1">
              <SelectField
                label="Account role"
                name="role"
                defaultValue="employee"
                disabled={busy || removing || uncertain}
              >
                <option value="employee">Member</option>
                <option value="admin">Administrator</option>
              </SelectField>
            </div>
            <Button type="submit" loading={busy} disabled={removing || uncertain}>
              {busy ? 'Creating account…' : 'Add member ↗'}
            </Button>
          </div>
        </form>
      </Card>
      <div className="mb-5 space-y-3">
        {error && <Feedback error>{error}</Feedback>}
        {uncertain && (
          <Feedback>
            The result is uncertain. Refresh the member list before repeating an account change.
          </Feedback>
        )}
        {notice && <Feedback>{notice}</Feedback>}
      </div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Workspace accounts</h2>
          <p className="mt-1 text-[11px] text-muted">
            {members === null
              ? 'Account list not loaded'
              : `${members.length} account${members.length === 1 ? '' : 's'}`}{' '}
            · Your own account cannot be removed here.
          </p>
        </div>
        <div className="w-full sm:w-64">
          <InputField
            label="Find a member"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by email"
          />
        </div>
      </div>
      {members === null ? (
        <p role="status" className="py-8 text-sm text-muted">
          {loading
            ? 'Loading workspace members…'
            : 'Member list is unavailable. Use Refresh members to try again.'}
        </p>
      ) : filtered?.length === 0 ? (
        <Card className="p-6">
          <p className="text-sm text-muted">
            {search ? 'No members match this email.' : 'No accounts are available.'}
          </p>
        </Card>
      ) : (
        <ul aria-label="Workspace members" className="space-y-3">
          {filtered?.map((member) => (
            <li key={member.id}>
              <Card className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="break-all text-sm font-bold">{member.email}</h3>
                    {member.id === currentUser.id && <Badge>You</Badge>}
                  </div>
                  <p className="mt-2 text-[11px] text-muted">
                    Added {new Date(member.created_at).toLocaleDateString()} · Account #{member.id}
                  </p>
                </div>
                <Badge>{member.role === 'admin' ? 'Administrator' : 'Member'}</Badge>
                <Badge tone={member.is_active ? 'teal' : 'violet'}>
                  {member.is_active ? 'Active' : 'Inactive'}
                </Badge>
                <Button
                  variant="ghost"
                  aria-label={`Remove ${member.email}`}
                  title={
                    member.id === currentUser.id ? 'You cannot remove your own account' : undefined
                  }
                  disabled={member.id === currentUser.id || busy || removing || uncertain}
                  onClick={() => {
                    setSelected(member);
                    setRemoveError('');
                  }}
                >
                  Remove
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <ConfirmationDialog
          title="Remove this member?"
          confirmLabel="Remove member"
          cancelLabel="Keep member"
          busyLabel="Removing…"
          busy={removing}
          error={removeError}
          uncertain={uncertain}
          onCancel={() => {
            if (!removing) {
              setSelected(null);
              if (uncertain) void load();
            }
          }}
          onConfirm={() => void remove()}
        >
          <p>
            <strong>{selected.email}</strong> will lose access to this workspace. Already-running
            requests may finish; future authenticated requests will be denied.
          </p>
        </ConfirmationDialog>
      )}
    </section>
  );
}
