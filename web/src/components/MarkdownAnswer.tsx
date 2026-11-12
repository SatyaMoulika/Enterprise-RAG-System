import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function MarkdownAnswer({ children }: { children: string }) {
  return (
    <div className="answer-markdown mt-3 min-w-0 text-sm leading-7">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => {
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
