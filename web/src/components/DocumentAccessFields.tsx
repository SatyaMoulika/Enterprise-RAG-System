import { useEffect, useId, useState } from 'react';
import { Button } from '@portfolio/porcelain-azure';
import type { ApiClient } from '../api/client';
import { errorMessage, isCancelled } from '../api/client';
import type { DocumentAccess, Member } from '../api/types';
import { Feedback } from './Feedback';
export function DocumentAccessFields({
  api,
  value,
  onChange,
  disabled,
  membersRevision = 0,
}: {
  api: ApiClient;
  value: DocumentAccess;
  onChange: (value: DocumentAccess) => void;
  disabled?: boolean;
  membersRevision?: number;
}) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState('');
  const id = useId();
  useEffect(() => {
    const focused = () => setRefresh((n) => n + 1);
    window.addEventListener('focus', focused);
    return () => window.removeEventListener('focus', focused);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setMembers(null);
    setError('');
    void api
      .members(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setMembers(result.filter((m) => m.is_active));
      })
      .catch((e) => {
        if (!isCancelled(e) && !controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [api, membersRevision, refresh]);
  useEffect(() => {
    if (!members) return;
    const available = new Set(members.map((m) => m.id));
    const ids = value.recipient_ids.filter((id) => available.has(id));
    if (ids.length !== value.recipient_ids.length) {
      onChange({ ...value, recipient_ids: ids });
      setNotice(
        'Unavailable members were removed from your selection. Review access before saving.',
      );
    }
  }, [members, value, onChange]);
  const filtered =
    members?.filter((m) =>
      `${m.name || ''} ${m.email}`.toLowerCase().includes(search.trim().toLowerCase()),
    ) || [];
  const label = (m: Member) => (m.name ? `${m.name} · ${m.email}` : m.email);
  return (
    <fieldset disabled={disabled} className="my-4 space-y-3 rounded-lg border border-line p-4">
      <legend className="px-2 text-xs font-bold">Who can access this document?</legend>
      <label className="block text-xs" htmlFor={`${id}-visibility`}>
        Document access
      </label>
      <select
        id={`${id}-visibility`}
        className="w-full rounded-lg border border-line bg-surface p-3 text-sm"
        value={value.visibility}
        onChange={(e) => {
          onChange({
            visibility: e.target.value as DocumentAccess['visibility'],
            recipient_ids: [],
          });
          setNotice('');
        }}
      >
        <option value="company">Company · everyone in this workspace</option>
        <option value="personal">Personal · one employee</option>
        <option value="restricted">Restricted · selected employees</option>
      </select>
      {value.visibility !== 'company' && (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold">
              {value.visibility === 'personal'
                ? 'Choose one employee'
                : 'Tick each employee who should have access. No keyboard shortcuts needed.'}
            </p>
            <Button
              variant="ghost"
              disabled={!members && !error}
              onClick={() => setRefresh((n) => n + 1)}
            >
              Refresh members
            </Button>
          </div>
          {!members && !error && (
            <p role="status" className="text-xs text-muted">
              Loading current members…
            </p>
          )}
          {members && value.visibility === 'personal' && (
            <>
              <label className="block text-xs" htmlFor={`${id}-recipients`}>
                Employee
              </label>
              <select
                id={`${id}-recipients`}
                required
                value={String(value.recipient_ids[0] || '')}
                onChange={(e) =>
                  onChange({
                    ...value,
                    recipient_ids: e.target.value ? [Number(e.target.value)] : [],
                  })
                }
                className="w-full rounded-lg border border-line bg-surface p-3 text-sm"
              >
                <option value="">Choose an employee</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {label(m)}
                  </option>
                ))}
              </select>
            </>
          )}
          {members && value.visibility === 'restricted' && (
            <>
              <label className="block text-xs" htmlFor={`${id}-search`}>
                Find members by name or email
              </label>
              <input
                id={`${id}-search`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface p-3 text-sm"
              />
              <div
                role="group"
                aria-label="Employees with restricted access"
                className="max-h-60 overflow-auto rounded-lg border border-line bg-surface p-2"
              >
                {filtered.map((m, index) => (
                  <label
                    key={m.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg p-3 text-sm hover:bg-soft"
                  >
                    <input
                      type="checkbox"
                      checked={value.recipient_ids.includes(m.id)}
                      required={!value.recipient_ids.length && index === 0}
                      onChange={(e) =>
                        onChange({
                          ...value,
                          recipient_ids: e.target.checked
                            ? [...value.recipient_ids, m.id]
                            : value.recipient_ids.filter((id) => id !== m.id),
                        })
                      }
                    />
                    <span className="break-all">{label(m)}</span>
                  </label>
                ))}
                {!filtered.length && (
                  <p className="p-3 text-xs text-muted">
                    No active members match. Clear the search or add a member first.
                  </p>
                )}
              </div>
              <p role="status" className="text-xs text-azure">
                {value.recipient_ids.length} employee{value.recipient_ids.length === 1 ? '' : 's'}{' '}
                selected
              </p>
            </>
          )}
        </>
      )}
      <p className="text-xs text-muted">
        Administrators can access and manage all workspace documents. Use personal access for offer
        and appointment letters.
      </p>
      {notice && <Feedback>{notice}</Feedback>}
      {error && <Feedback error>{error} Use Refresh members to retry.</Feedback>}
    </fieldset>
  );
}
