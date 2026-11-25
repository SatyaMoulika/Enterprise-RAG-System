# Workspace member management

## Where to find it

Sign in as an administrator and choose **Members** in the React sidebar. Ordinary members do not see this navigation item. The API independently enforces administrator access on listing, creating and removing accounts.

The page uses the shared Porcelain & Azure controls and shows only real accounts from the signed-in administrator's workspace. It supports email search, role/status labels, account creation with a Member or Administrator role, explicit removal confirmation and manual refresh. The signed-in account is labelled **You** and cannot remove itself.

## Account creation

Organisation signup asks for the organisation name, the initial administrator's full name, email and password, plus confirmation that the person is registering as administrator. The initial account remains an administrator of its newly created organisation; employees join through an administrator-created account. The administrator name is saved on the account, and `/users/me` returns both the person's name and their organisation's name from the database. Overview shows “Welcome back, [name].” for named administrators and employees, and the global header shows the organisation name for everyone in that organisation. Existing unnamed accounts receive “Welcome back.”; names are not inferred from email addresses. Existing accounts, organisation names, documents and permissions are preserved, with no new migration required. Older API clients may omit the administrator name for compatibility; the current signup form requires it.

The operator bootstrap supports `--admin-name 'Full Name'` and prompts for the administrator name if that argument is omitted. Its existing `--name` argument continues to mean the organisation name.

Administrators enter an email and initial password (8–128 characters). This creates a sign-in account immediately; it is not an email invitation workflow. Share the initial password through a secure channel. Password input is cleared after every submitted request, never shown in the account list and never persisted in browser storage. Accounts currently belong to one workspace and email addresses are globally unique.

Role assignment happens when an account is created. Existing-role editing and email invitations are separate future features; this page does not show nonfunctional controls for them. Members can recover their own passwords from the sign-in or signup screen, as described below. An uncertain creation result requires refreshing the member list before manually trying again. No account mutation is automatically retried.

## Removal and administrator protection

Removal is scoped to the current workspace and confirmed in a native dialog shared with document deletion. It deletes the account, not the workspace documents. Self-removal is rejected by both UI and API. Membership writes lock the workspace row and re-read the acting administrator before making changes. Under the configured PostgreSQL READ COMMITTED isolation, two administrators attempting to remove each other cannot remove both accounts: the later request finds its actor removed and is denied. The service also retains an explicit active-administrator guard.

A removed account fails subsequent authenticated requests; already-running requests can finish. Existing page content already delivered to a browser cannot be remotely erased.

## Token identity fix

Email alone is not a stable account identity. New sign-in/registration tokens include the user ID and a keyed account stamp derived from the stored salted password hash. Protected endpoints validate these against the live account. Removing and re-creating an email therefore does not reactivate its old tokens, even if an integer ID is reused. Password-hash changes invalidate previous tokens as well. Neither the stored password hash nor a password verifier is returned in token claims or user responses.

Pre-upgrade email-only tokens are rejected. Sign in again after rebuilding the API; existing accounts/passwords and document indexes are preserved. No schema migration is needed.

## Verification

- **64 backend tests passed**, including admin permissions, workspace scoping, duplicate-email handling, validation, self-removal, removed-token rejection, email/ID reuse and inactive status.
- **40 frontend tests passed**, including page visibility, API-backed creation/listing/removal, cancellation, self-removal controls, role selection, search, duplicate/uncertain creation and password clearing. Existing document confirmation tests also pass after extracting the shared dialog.
- TypeScript/Vite, Prettier and backend Ruff checks passed.
- The guarded disposable PostgreSQL smoke script passed migrations/schema parity, existing document workflow and simultaneous administrator removals in two independent database sessions. Exactly one administrator survived; the removed account's token was rejected. Inference was mocked.

Visual browser acceptance and real inference are not claimed for this member-management change. No existing/development database, model configuration or paid service was changed.

## Apply

After merging the PR:

```sh
git switch main
git pull
docker compose -p rag-updated up -d --build api web
```

Refresh the frontend, sign in again as an administrator and open **Members**. New members can then sign in with the account credentials you assigned. Do not reset the database or remove Docker volumes.

## Password recovery

For the current local setup, **Forgot password?** opens an email, new-password and confirmation form and updates the active account directly, without SMTP. Local Compose enables `LOCAL_DIRECT_PASSWORD_RESET` by default; for a backend run outside Docker, set it to `true` explicitly. This shortcut verifies no mailbox ownership: anyone with access to the app and an account email can change that password. Use it only on your private local machine. The backend requires a loopback HTTP `PUBLIC_APP_URL`, and the public-hosting Compose profile forces the flag to `false`. Set the flag to `false` and rebuild the API to return to emailed recovery. Direct changes invalidate existing sessions just like emailed resets.

### Emailed recovery

**Forgot password?** is available on both sign-in and signup and opens `/reset-password` directly. The initial page requests the account email; the emailed link opens the same page with a new-password/confirmation form. Reset links expire after 15 minutes, are consumed by the password change, cannot authenticate as login tokens, and invalidate all existing sessions when used. Requests return the same generic message for unknown, inactive and active accounts. Mail requests have a persisted per-account cooldown and the proxy's authentication rate limit.

Configure `PUBLIC_APP_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_FROM`, `SMTP_USERNAME` and `SMTP_PASSWORD` in the deployment environment. Use `starttls` (default, usually port 587) or `ssl` (usually port 465); `plain` is only for an explicitly trusted local test server. Use a verified sender address. The production Compose override derives `PUBLIC_APP_URL` from the configured HTTPS domain. Without sender/SMTP configuration the API returns an explicit configuration error; no recovery email is sent. Delivery failures are logged without account addresses, credentials or tokens. Failed mail requests can be retried after the cooldown.

The token is delivered in a URL fragment so it is not included in server request logs, then removed from the browser URL after the page reads it. Never share reset links or log email contents. Migration `0006` adds only a nullable reset-request timestamp, preserving existing accounts. Rebuild `api`, `ingestion_worker` and `web` to apply the migration and updated account model. Email delivery was tested with a mock SMTP transport; configure and verify your actual sender before relying on recovery in production.


## Account menu and member editing

The global header contains the Atlas logo and an account icon; the organisation name remains in the sidebar. The account icon opens account details, name editing, profile-photo upload/removal, password change and sign-out. Photos accept PNG/JPEG up to 280 KB and are saved with the account, including across sign-ins. Password changes require the current password and matching new-password confirmation, and invalidate existing sessions. The account menu does not provide forgotten-password recovery.

Administrators can use Edit details on each member to change their name and email. These changes are restricted to the signed-in administrator's organisation; duplicate email addresses are rejected. Roles are displayed but are not editable in this form. Changing an email invalidates the old-email session, so that member signs in again with the new address. Internal account numbers are no longer displayed.

Migration 0007 adds a nullable profile-photo field and preserves existing accounts. Rebuild API, worker and web together to apply this update. The home page no longer includes numerical KPI cards. Document upload errors appear in a dismissible notification, completed documents have no reindex control, and failed documents offer Try again. Uncertain upload results require refreshing the list before retrying, to avoid duplicate uploads. Delete uses a red bin icon and retains confirmation.


The profile icon now opens a two-item menu: Account and Sign out. Account opens a modal for name, photo and password changes; closing it discards unsaved form changes. Sign out opens a separate confirmation modal, with Cancel preserving the session and conversation. The sidebar displays the organisation and role without a document count. The active React interface is the only supported client; the unused Streamlit source and legacy-ui dependency extra have been removed.
