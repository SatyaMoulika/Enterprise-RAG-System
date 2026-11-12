import type { ReactNode } from 'react';
export function Feedback({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <p
      role={error ? 'alert' : 'status'}
      className={
        error
          ? 'rounded-lg border border-[#E5C5C5] bg-[#FFF5F5] px-4 py-3 text-xs leading-relaxed text-[#883C3C]'
          : 'rounded-lg border border-line bg-soft px-4 py-3 text-xs leading-relaxed text-muted'
      }
    >
      {children}
    </p>
  );
}
