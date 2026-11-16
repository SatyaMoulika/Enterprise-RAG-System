import { useEffect, useId, useState } from 'react';
import type { ApiClient } from '../api/client';
import { errorMessage, isCancelled } from '../api/client';
import type { DocumentAccess, Member } from '../api/types';
import { Feedback } from './Feedback';
export function DocumentAccessFields({
  api,
  value,
  onChange,
  disabled,
}: {
  api: ApiClient;
  value: DocumentAccess;
  onChange: (value: DocumentAccess) => void;
  disabled?: boolean;
}) {
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState('');
  const id = useId();
  useEffect(() => {
    const controller = new AbortController();
    void api
      .members(controller.signal)
      .then(setMembers)
      .catch((e) => {
        if (!isCancelled(e)) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [api]);
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
        onChange={(e) =>
          onChange({
            visibility: e.target.value as DocumentAccess['visibility'],
            recipient_ids: [],
          })
        }
      >
        <option value="company">Company · everyone in this workspace</option>
        <option value="personal">Personal · one employee</option>
        <option value="restricted">Restricted · selected employees</option>
      </select>
      {value.visibility !== 'company' && (
        <>
          <label className="block text-xs" htmlFor={`${id}-recipients`}>
            {value.visibility === 'personal' ? 'Employee' : 'Employees (select one or more)'}
          </label>
          <select
            id={`${id}-recipients`}
            required
            multiple={value.visibility === 'restricted'}
            value={
              value.visibility === 'personal'
                ? String(value.recipient_ids[0] || '')
                : value.recipient_ids.map(String)
            }
            onChange={(e) =>
              onChange({
                ...value,
                recipient_ids: Array.from(e.target.selectedOptions)
                  .map((o) => Number(o.value))
                  .filter(Boolean),
              })
            }
            className="w-full rounded-lg border border-line bg-surface p-3 text-sm"
          >
            {value.visibility === 'personal' && <option value="">Choose an employee</option>}
            {members
              .filter((m) => m.is_active)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.email}
                </option>
              ))}
          </select>
        </>
      )}
      <p className="text-xs text-muted">
        Administrators can access and manage all workspace documents. Use personal access for offer
        and appointment letters.
      </p>
      {error && <Feedback error>{error}</Feedback>}
    </fieldset>
  );
}
