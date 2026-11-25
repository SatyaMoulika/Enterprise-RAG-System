import { useEffect, useId, useRef, useState, type InputHTMLAttributes } from 'react';

type PasswordFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label: string;
  hint?: string;
  error?: string;
};

export function PasswordField({
  label,
  hint,
  error,
  id,
  disabled,
  className = '',
  ...props
}: PasswordFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const helpId = `${inputId}-help`;
  const input = useRef<HTMLInputElement>(null);
  const [visible, setVisible] = useState(false);
  const action = `${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`;
  useEffect(() => {
    if (disabled) setVisible(false);
  }, [disabled]);
  useEffect(() => {
    const form = input.current?.form;
    const hide = () => setVisible(false);
    form?.addEventListener('reset', hide);
    return () => form?.removeEventListener('reset', hide);
  }, []);
  return (
    <div>
      <label htmlFor={inputId} className="mb-1.5 block text-xs font-semibold">
        {label}
      </label>
      <div className="relative">
        <input
          {...props}
          ref={input}
          id={inputId}
          type={visible ? 'text' : 'password'}
          disabled={disabled}
          aria-invalid={error ? true : props['aria-invalid']}
          aria-describedby={
            [props['aria-describedby'], hint || error ? helpId : undefined]
              .filter(Boolean)
              .join(' ') || undefined
          }
          className={`password-input w-full rounded-lg border border-line bg-canvas px-3 py-2.5 pr-12 text-sm text-ink placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azure ${className}`}
        />
        <button
          type="button"
          aria-label={action}
          title={action}
          aria-controls={inputId}
          aria-pressed={visible}
          disabled={disabled}
          onClick={() => setVisible((current) => !current)}
          className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-azure hover:bg-soft focus-visible:outline-2 focus-visible:outline-azure disabled:cursor-not-allowed disabled:opacity-45"
        >
          <svg
            aria-hidden="true"
            focusable="false"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
            <circle cx="12" cy="12" r="3" />
            {visible && <path d="m3 3 18 18" />}
          </svg>
        </button>
      </div>
      {(hint || error) && (
        <p id={helpId} className="mt-1.5 text-xs text-muted">
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
