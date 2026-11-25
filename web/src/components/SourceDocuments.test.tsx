import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { SourceDocuments } from './SourceDocuments';

const citations = [
  {
    marker: 1,
    document_id: 1,
    title: 'policy.pdf',
    chunk_index: 27,
    page_start: 3,
    page_end: 4,
    section: 'Leave',
    excerpt: 'Employees receive twenty days of leave.\n\nManager approval is required.',
  },
  {
    marker: 2,
    document_id: 2,
    title: 'other.pdf',
    chunk_index: 98,
    excerpt: 'A different document.',
  },
];

it('shows cited document cards without rendering chunks or extracted text', async () => {
  const user = userEvent.setup();
  render(
    <SourceDocuments
      citations={citations}
      answer="Leave requires approval [1]."
      onOpenSource={vi.fn()}
    />,
  );
  expect(screen.getByRole('heading', { name: 'policy.pdf' })).toBeVisible();
  expect(screen.getByText('Pages 3–4')).toBeVisible();
  expect(screen.getByText('Reference [1]')).toBeVisible();
  expect(screen.queryByText(/Employees receive twenty/)).not.toBeInTheDocument();
  expect(screen.queryByText('Leave')).not.toBeInTheDocument();
  expect(document.querySelector('blockquote')).toBeNull();
  const extra = screen.getByText('Other retrieved documents (1)').closest('details')!;
  expect(extra).not.toHaveAttribute('open');
  await user.click(within(extra).getByText('Other retrieved documents (1)'));
  expect(within(extra).getByRole('heading', { name: 'other.pdf' })).toBeVisible();
  expect(screen.queryByText('A different document.')).not.toBeInTheDocument();
});

it('combines references to one file into one card and uses only cited page ranges', () => {
  render(
    <SourceDocuments
      citations={[
        citations[0],
        { ...citations[0], marker: 3, chunk_index: 28, page_start: 5, page_end: 5 },
        { ...citations[0], marker: 4, chunk_index: 29, page_start: 9, page_end: 10 },
        { ...citations[0], marker: 5, chunk_index: 30, page_start: 20, page_end: 20 },
      ]}
      answer="Leave terms [1]. Another condition [3]. A separate rule [4]."
      onOpenSource={vi.fn()}
    />,
  );
  expect(screen.getAllByRole('heading', { name: 'policy.pdf' })).toHaveLength(1);
  expect(screen.getByText('Pages 3–5, 9–10')).toBeVisible();
  expect(screen.getByText('References [1], [3], [4]')).toBeVisible();
  expect(screen.queryByText(/retrieved documents/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/20/)).not.toBeInTheDocument();
});

it('keeps distinct files with identical names separate', () => {
  render(
    <SourceDocuments
      citations={[citations[0], { ...citations[0], marker: 3, document_id: 9 }]}
      answer="First document [1]. Second document [3]."
      onOpenSource={vi.fn()}
    />,
  );
  expect(screen.getAllByRole('heading', { name: 'policy.pdf' })).toHaveLength(2);
  expect(screen.getAllByRole('button', { name: 'View document: policy.pdf' })).toHaveLength(2);
});

it('focuses the selected document and opens the original at the selected reference page', async () => {
  const user = userEvent.setup();
  const onOpenSource = vi.fn();
  const sources = [citations[0], { ...citations[0], marker: 7, page_start: 8, page_end: 8 }];
  const { rerender } = render(
    <SourceDocuments citations={sources} answer="Terms [1] [7]." onOpenSource={onOpenSource} />,
  );
  rerender(
    <SourceDocuments
      citations={sources}
      answer="Terms [1] [7]."
      activeMarker={7}
      activation={{}}
      onOpenSource={onOpenSource}
    />,
  );
  expect(screen.getByRole('article', { name: 'Source document: policy.pdf' })).toHaveFocus();
  await user.click(screen.getByRole('button', { name: 'View document: policy.pdf' }));
  expect(onOpenSource).toHaveBeenCalledWith(
    expect.objectContaining({ document_id: 1, marker: 7, page_start: 8 }),
  );
});

it('uses legacy marker positions without renumbering references after grouping', async () => {
  const user = userEvent.setup();
  const onOpenSource = vi.fn();
  render(
    <SourceDocuments
      citations={citations.map(({ marker: _marker, ...source }) => source)}
      answer="Supported by the second file [2]."
      activeMarker={2}
      onOpenSource={onOpenSource}
    />,
  );
  expect(screen.getByText('Reference [2]')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'View document: other.pdf' }));
  expect(onOpenSource).toHaveBeenCalledWith(expect.objectContaining({ document_id: 2, marker: 2 }));
});

it('keeps uncited retrieval separate when an answer contains no source references', async () => {
  const user = userEvent.setup();
  render(
    <SourceDocuments
      citations={citations}
      answer="I could not verify the generated answer."
      onOpenSource={vi.fn()}
    />,
  );
  const extra = screen.getByText('Retrieved documents (2)').closest('details')!;
  expect(extra).not.toHaveAttribute('open');
  expect(screen.getByRole('heading', { name: 'policy.pdf' })).not.toBeVisible();
  await user.click(within(extra).getByText('Retrieved documents (2)'));
  expect(within(extra).getAllByRole('article')).toHaveLength(2);
  expect(screen.queryByText('Reference [1]')).not.toBeInTheDocument();
});
