import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { OverviewPanel } from './OverviewPanel';
const person = {
  id: 1,
  email: 'a@example.com',
  role: 'admin' as const,
  enterprise_id: 1,
  is_active: true,
  name: 'Alice',
};
const docs = [
  {
    id: 1,
    title: 'Policy.pdf',
    enterprise_id: 1,
    created_at: '2026-11-25',
    index_status: 'ready' as const,
  },
  {
    id: 2,
    title: 'Failed.pdf',
    enterprise_id: 1,
    created_at: '2026-11-24',
    index_status: 'failed' as const,
  },
];
it('shows accurate administrator metrics and sends the question to chat', async () => {
  const user = userEvent.setup(),
    ask = vi.fn();
  render(
    <OverviewPanel
      user={person}
      documents={docs}
      error=""
      membersCount={3}
      onQuickAsk={ask}
      onOpenDocuments={vi.fn()}
      onAsk={vi.fn()}
      onMembers={vi.fn()}
      onChat={vi.fn()}
    />,
  );
  expect(
    within(screen.getByText('Total members').parentElement!.parentElement!).getByText('3'),
  ).toBeVisible();
  expect(
    within(screen.getByText('Total documents').parentElement!.parentElement!).getByText('2'),
  ).toBeVisible();
  expect(
    within(screen.getByText('Failed uploads').parentElement!.parentElement!).getByText('1'),
  ).toBeVisible();
  expect(screen.getByText('Policy.pdf')).toBeVisible();
  await user.type(screen.getByLabelText('Your question for Atlas'), 'What is the policy?');
  await user.click(screen.getByRole('button', { name: 'Ask question' }));
  expect(ask).toHaveBeenCalledWith('What is the policy?');
});
it('hides member totals from employees and labels the accessible document count', () => {
  render(
    <OverviewPanel
      user={{ ...person, role: 'employee' }}
      documents={docs}
      error=""
      membersCount={null}
      onQuickAsk={vi.fn()}
      onOpenDocuments={vi.fn()}
      onAsk={vi.fn()}
      onMembers={vi.fn()}
      onChat={vi.fn()}
    />,
  );
  expect(screen.queryByText('Total members')).not.toBeInTheDocument();
  expect(screen.getByText('Your documents')).toBeVisible();
  expect(screen.queryByText('Sources needing OCR')).not.toBeInTheDocument();
});
it('shows unknown values on unavailable data rather than inventing counts', () => {
  render(
    <OverviewPanel
      user={person}
      documents={null}
      error="Unavailable"
      membersCount={null}
      onQuickAsk={vi.fn()}
      onOpenDocuments={vi.fn()}
      onAsk={vi.fn()}
      onMembers={vi.fn()}
      onChat={vi.fn()}
    />,
  );
  expect(
    within(screen.getByText('Total documents').parentElement!.parentElement!).getByText('—'),
  ).toBeVisible();
  expect(
    within(screen.getByText('Failed uploads').parentElement!.parentElement!).getByText('—'),
  ).toBeVisible();
});
