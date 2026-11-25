import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Citation } from '../api/types';

interface MarkdownNode {
  type: string;
  value?: string;
  url?: string;
  children?: MarkdownNode[];
}

function citationPlugin(markers: Set<number>) {
  return () => (tree: MarkdownNode) => {
    function visit(node: MarkdownNode) {
      if (!node.children || ['link', 'image', 'code', 'inlineCode', 'html'].includes(node.type))
        return;
      node.children = node.children.flatMap((child) => {
        if (child.type !== 'text' || !child.value) {
          visit(child);
          return [child];
        }
        const result: MarkdownNode[] = [];
        let start = 0;
        for (const match of child.value.matchAll(/\[(\d+)\]/g)) {
          if (!markers.has(Number(match[1]))) continue;
          result.push(
            { type: 'text', value: child.value.slice(start, match.index) },
            {
              type: 'link',
              url: `#citation-${match[1]}`,
              children: [{ type: 'text', value: match[0] }],
            },
          );
          start = match.index! + match[0].length;
        }
        return result.length
          ? [...result, { type: 'text', value: child.value.slice(start) }]
          : [child];
      });
    }
    visit(tree);
  };
}

export function MarkdownAnswer({
  children,
  citations = [],
  onCitation,
}: {
  children: string;
  citations?: Citation[];
  onCitation?: (marker: number) => void;
}) {
  const markers = new Set(citations.map((source, index) => source.marker ?? index + 1));
  return (
    <div className="answer-markdown mt-3 min-w-0 text-sm leading-7">
      <ReactMarkdown
        remarkPlugins={onCitation ? [remarkGfm, citationPlugin(markers)] : [remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => {
            const match = href?.match(/^#citation-(\d+)$/);
            if (match && onCitation && markers.has(Number(match[1]))) {
              const marker = Number(match[1]);
              const source = citations.find((item, index) => (item.marker ?? index + 1) === marker);
              return (
                <button
                  type="button"
                  className="citation-reference"
                  aria-label={`View source ${marker}: ${source?.title}`}
                  onClick={() => onCitation(marker)}
                >
                  {children}
                </button>
              );
            }
            const safe = defaultUrlTransform(href || '');
            if (!/^(https?:\/\/|mailto:|#)/i.test(safe)) return <span>{children}</span>;
            return (
              <a
                href={safe}
                target={safe.startsWith('#') ? undefined : '_blank'}
                rel="noopener noreferrer"
              >
                {children}
              </a>
            );
          },
          img: ({ alt }) => (
            <span className="text-muted">{alt ? `[Image: ${alt}]` : '[Image omitted]'}</span>
          ),
          table: ({ children }) => (
            <div className="my-4 max-w-full overflow-x-auto rounded-lg border border-line">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
