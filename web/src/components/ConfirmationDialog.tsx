import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button } from '@portfolio/porcelain-azure';
import { Feedback } from './Feedback';
export function ConfirmationDialog({
  title,
  children,
  confirmLabel,
  cancelLabel,
  busyLabel = 'Working…',
  busy,
  uncertain = false,
  error,
  onCancel,
  onConfirm,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  busyLabel?: string;
  busy: boolean;
  uncertain?: boolean;
  error?: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-description`}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      className="m-auto w-[calc(100%_-_2rem)] max-w-md rounded-xl border border-line bg-surface p-6 text-ink shadow-xl"
    >
      <h2 id={`${id}-title`} className="text-xl font-bold">
        {title}
      </h2>
      <div id={`${id}-description`} className="my-4 break-words text-sm leading-6 text-muted">
        {children}
      </div>
      {error && <Feedback error>{error}</Feedback>}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" disabled={busy} onClick={onCancel} autoFocus>
          {uncertain ? 'Close and refresh' : cancelLabel}
        </Button>
        <Button loading={busy} disabled={uncertain} onClick={onConfirm}>
          {busy ? busyLabel : confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
