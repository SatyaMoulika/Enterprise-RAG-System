import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarkdownAnswer } from './MarkdownAnswer';

describe('answer Markdown', () => {
  it('renders headings, emphasis, lists, inline code and fenced code', () => {
    const { container } = render(
      <MarkdownAnswer>
        {
          '## Findings\n\n**Important** evidence with `code`.\n\n- First point\n- Second point\n\n```python\nprint("hello")\n```'
        }
      </MarkdownAnswer>,
    );
    expect(screen.getByRole('heading', { name: 'Findings' })).toBeInTheDocument();
    expect(container.querySelector('strong')).toHaveTextContent('Important');
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(container.querySelector('pre code')).toHaveTextContent('print("hello")');
  });

  it('renders a horizontally contained GFM table', () => {
    const { container } = render(
      <MarkdownAnswer>
        {'| Domain | Application |\n| --- | --- |\n| Vision | Detection |'}
      </MarkdownAnswer>,
    );
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Domain' })).toBeInTheDocument();
    expect(container.querySelector('table')?.parentElement).toHaveClass('overflow-x-auto');
  });

  it('discards raw HTML, unsafe links and remote image requests', () => {
    const { container } = render(
      <MarkdownAnswer>
        {
          'Safe answer.\n\n<script>alert(1)</script>\n\n<img src="https://example.com/tracker" onerror="alert(1)">\n\n[bad](javascript:alert%281%29)\n\n![diagram](https://example.com/remote.png)'
        }
      </MarkdownAnswer>,
    );
    expect(screen.getByText('Safe answer.')).toBeInTheDocument();
    expect(container.querySelector('script, img, iframe')).toBeNull();
    expect(screen.queryByRole('link', { name: 'bad' })).not.toBeInTheDocument();
    expect(screen.getByText('[Image: diagram]')).toBeInTheDocument();
  });

  it('opens a safe external link with isolation and retains citation markers', () => {
    render(
      <MarkdownAnswer>
        {'See [the reference](https://example.com) and supporting evidence [1].'}
      </MarkdownAnswer>,
    );
    const link = screen.getByRole('link', { name: 'the reference' });
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText(/supporting evidence \[1\]/)).toBeInTheDocument();
  });
});

it('turns valid answer markers into source buttons without modifying code or external links', async () => {
  const { vi } = await import('vitest');
  const user = (await import('@testing-library/user-event')).default.setup();
  const onCitation = vi.fn();
  render(
    <MarkdownAnswer
      citations={[
        {
          marker: 2,
          document_id: 1,
          title: 'policy.pdf',
          chunk_index: 7,
          excerpt: 'Original evidence.',
        },
      ]}
      onCitation={onCitation}
    >
      {'Supported claim [2]. Missing marker [9]. Code `[2]`. [Reference](https://example.com).'}
    </MarkdownAnswer>,
  );
  await user.click(screen.getByRole('button', { name: 'View source 2: policy.pdf' }));
  expect(onCitation).toHaveBeenCalledWith(2);
  expect(screen.getAllByRole('button')).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Reference' })).toHaveAttribute(
    'href',
    'https://example.com',
  );
  expect(document.querySelector('code')).toHaveTextContent('[2]');
});
