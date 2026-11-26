import { useEffect, useRef, useState } from 'react';
import type { User } from '../api/types';
import { ApiClient } from '../api/client';
import { AccountDialog } from './AccountDialog';
import { ConfirmationDialog } from './ConfirmationDialog';
export function AccountMenu({
  user,
  api,
  onUpdated,
  onSignOut,
}: {
  user: User;
  api: ApiClient;
  onUpdated: (user: User) => void;
  onSignOut: () => void;
}) {
  const [open, setOpen] = useState(false),
    [modal, setModal] = useState<'account' | 'signout' | null>(null);
  const root = useRef<HTMLDivElement>(null),
    trigger = useRef<HTMLButtonElement>(null),
    menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  function closeModal() {
    setModal(null);
    trigger.current?.focus();
  }
  return (
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-line bg-soft text-azure"
      >
        {user.profile_photo ? (
          <img src={user.profile_photo} alt="Your profile" className="h-full w-full object-cover" />
        ) : (
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            aria-hidden="true"
          >
            <circle cx="12" cy="8" r="4" />
            <path d="M4 22v-2a8 8 0 0 1 16 0v2" />
          </svg>
        )}
      </button>
      {open && (
        <div
          ref={menu}
          role="menu"
          aria-label="Account options"
          className="absolute right-0 top-12 z-30 w-48 rounded-xl border border-line bg-surface p-2 shadow-lg"
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setOpen(false);
              trigger.current?.focus();
            }
            if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
              event.preventDefault();
              const items = Array.from(menu.current!.querySelectorAll<HTMLButtonElement>('button'));
              const index = items.indexOf(document.activeElement as HTMLButtonElement);
              items[
                event.key === 'Home'
                  ? 0
                  : event.key === 'End'
                    ? items.length - 1
                    : (index + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length
              ]?.focus();
            }
            if (event.key === 'Tab') setOpen(false);
          }}
        >
          {(
            [
              ['account', 'Account'],
              ['signout', 'Sign out'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs font-semibold text-ink hover:bg-soft focus-visible:outline-2 focus-visible:outline-azure"
              onClick={() => {
                setOpen(false);
                setModal(value);
              }}
            >
              <svg
                aria-hidden="true"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                className={value === 'account' ? 'text-azure' : 'text-muted'}
              >
                {value === 'account' ? (
                  <>
                    <circle cx="12" cy="7" r="3.5" />
                    <path d="M5 21v-2a7 7 0 0 1 14 0v2" />
                  </>
                ) : (
                  <>
                    <path d="M10 17l5-5-5-5M15 12H4" />
                    <path d="M12 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5" />
                  </>
                )}
              </svg>
              {label}
            </button>
          ))}
        </div>
      )}
      {modal === 'account' && (
        <AccountDialog
          user={user}
          api={api}
          onUpdated={onUpdated}
          onSignOut={onSignOut}
          onClose={closeModal}
        />
      )}
      {modal === 'signout' && (
        <ConfirmationDialog
          title="Sign out of Atlas?"
          confirmLabel="Sign out"
          cancelLabel="Cancel"
          busy={false}
          onCancel={closeModal}
          onConfirm={onSignOut}
        >
          You’ll return to the sign-in page. Your current conversation will be cleared.
        </ConfirmationDialog>
      )}
    </div>
  );
}
