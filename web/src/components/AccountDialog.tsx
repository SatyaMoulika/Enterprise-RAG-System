import { useEffect, useRef, useState } from 'react';
import { Button, InputField } from '@portfolio/porcelain-azure';
import type { User } from '../api/types';
import { ApiClient, errorMessage } from '../api/client';
import { PasswordField } from './PasswordField';
import { Feedback } from './Feedback';
export function AccountDialog({
  user,
  api,
  onUpdated,
  onSignOut,
  onClose,
}: {
  user: User;
  api: ApiClient;
  onUpdated: (user: User) => void;
  onSignOut: () => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [password, setPassword] = useState(false),
    [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState<string | null>(user.profile_photo || null),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    return () => {
      if (element.open) element.close();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="account-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      className="m-auto max-h-[85vh] w-[calc(100%_-_2rem)] max-w-lg overflow-auto rounded-xl border border-line bg-surface p-6 text-ink shadow-xl"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="account-dialog-title" className="text-xl font-bold">
          Your account
        </h2>
        <Button variant="ghost" disabled={busy} onClick={onClose}>
          Close
        </Button>
      </div>
      <p className="mt-2 break-all text-xs text-muted">{user.email}</p>
      <form
        className="mt-4 space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          if (busy) return;
          const data = new FormData(event.currentTarget);
          setBusy(true);
          setError('');
          setMessage('');
          try {
            onUpdated(
              await api.updateProfile({
                name: String(data.get('name')).trim(),
                profile_photo: photo,
              }),
            );
            setMessage('Account details saved.');
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <InputField
          label="Full name"
          name="name"
          required
          maxLength={120}
          defaultValue={user.name || ''}
          disabled={busy}
        />
        {photo && (
          <img
            src={photo}
            alt="Profile photo preview"
            className="h-16 w-16 rounded-full object-cover"
          />
        )}
        <label className="block text-xs font-semibold">
          Profile photo
          <input
            className="mt-2 block w-full text-xs"
            type="file"
            accept="image/png,image/jpeg"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (file.size > 280000 || !['image/png', 'image/jpeg'].includes(file.type)) {
                setError('Choose a PNG or JPEG photo smaller than 280 KB.');
                return;
              }
              const reader = new FileReader();
              reader.onload = () => {
                setError('');
                setPhoto(String(reader.result));
              };
              reader.onerror = () => setError('The photo could not be read. Choose another file.');
              reader.readAsDataURL(file);
            }}
          />
        </label>
        <p className="text-xs text-muted">
          PNG or JPEG, up to 280 KB. Save your account details to apply the photo.
        </p>
        {photo && (
          <Button variant="ghost" disabled={busy} onClick={() => setPhoto(null)}>
            Remove photo
          </Button>
        )}
        <Button type="submit" loading={busy}>
          Save account details
        </Button>
      </form>
      <Button
        variant="ghost"
        className="mt-4"
        disabled={busy}
        onClick={() => {
          setError('');
          setMessage('');
          setPassword(!password);
        }}
      >
        Change password
      </Button>
      {password && (
        <form
          className="mt-3 space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy) return;
            const data = new FormData(event.currentTarget);
            if (data.get('password') !== data.get('confirmation')) {
              setError('The passwords do not match.');
              return;
            }
            setBusy(true);
            setError('');
            try {
              await api.changePassword({
                current_password: String(data.get('current_password')),
                password: String(data.get('password')),
              });
              onSignOut();
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <PasswordField
            label="Current password"
            maxLength={128}
            name="current_password"
            autoComplete="current-password"
            required
            disabled={busy}
          />
          <PasswordField
            label="New password"
            name="password"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
            disabled={busy}
          />
          <PasswordField
            label="Confirm new password"
            name="confirmation"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
            disabled={busy}
          />
          <p className="text-xs text-muted">
            Changing your password signs you out of existing sessions.
          </p>
          <Button type="submit" loading={busy}>
            Update password
          </Button>
        </form>
      )}
      {error && <Feedback error>{error}</Feedback>}
      {message && <Feedback>{message}</Feedback>}
    </dialog>
  );
}
