import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import type { DocumentAccess } from '../api/types';
import { DocumentAccessFields } from './DocumentAccessFields';
const member = (id: number, name: string) => ({
  id,
  name,
  email: `${name.toLowerCase()}@example.com`,
  is_active: true,
});
function Harness({
  api,
  revision = 0,
  initial = { visibility: 'restricted', recipient_ids: [] },
}: {
  api: ApiClient;
  revision?: number;
  initial?: DocumentAccess;
}) {
  const [value, setValue] = useState<DocumentAccess>(initial);
  return (
    <>
      <DocumentAccessFields
        api={api}
        value={value}
        onChange={setValue}
        membersRevision={revision}
      />
      <output aria-label="Selected account IDs">{value.recipient_ids.join(',')}</output>
    </>
  );
}
describe('document recipient picker', () => {
  it('selects multiple named members with ordinary checkbox clicks and preserves selection while searching', async () => {
    const members = vi.fn().mockResolvedValue([member(2, 'Alice'), member(3, 'Bob')]);
    const api = { members } as unknown as ApiClient;
    const user = userEvent.setup();
    render(<Harness api={api} />);
    await user.click(await screen.findByRole('checkbox', { name: 'Alice · alice@example.com' }));
    await user.click(screen.getByRole('checkbox', { name: 'Bob · bob@example.com' }));
    expect(screen.getByText('2 employees selected')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Find members by name or email'), 'Bob');
    expect(screen.queryByRole('checkbox', { name: /Alice/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Selected account IDs')).toHaveTextContent('2,3');
    await user.click(screen.getByRole('checkbox', { name: /Bob/ }));
    expect(screen.getByLabelText('Selected account IDs')).toHaveTextContent('2');
  });
  it('reloads after membership changes and removes deleted recipients without a browser refresh', async () => {
    const members = vi
      .fn()
      .mockResolvedValueOnce([member(2, 'Deleted')])
      .mockResolvedValue([member(3, 'New')]);
    const api = { members } as unknown as ApiClient;
    const { rerender } = render(
      <Harness api={api} initial={{ visibility: 'personal', recipient_ids: [2] }} />,
    );
    await screen.findByRole('option', { name: 'Deleted · deleted@example.com' });
    rerender(<Harness api={api} revision={1} />);
    await screen.findByRole('option', { name: 'New · new@example.com' });
    expect(screen.queryByRole('option', { name: /Deleted/ })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText('Selected account IDs')).toBeEmptyDOMElement(),
    );
    expect(screen.getByText(/Unavailable members were removed/)).toBeInTheDocument();
  });
});
