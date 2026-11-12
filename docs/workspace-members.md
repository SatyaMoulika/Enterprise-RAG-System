# Workspace member management

## Where to find it

Sign in as an administrator and choose **Members** in the React sidebar. Ordinary members do not see this navigation item. The API independently enforces administrator access on listing, creating and removing accounts.

The page uses the shared Porcelain & Azure controls and shows only real accounts from the signed-in administrator's workspace. It supports email search, role/status labels, account creation with a Member or Administrator role, explicit removal confirmation and manual refresh. The signed-in account is labelled **You** and cannot remove itself.

## Account creation

Administrators enter an email and initial password (8–128 characters). This creates a sign-in account immediately; it is not an email invitation workflow. Share the initial password through a secure channel. Password input is cleared after every submitted request, never shown in the account list and never persisted in browser storage. Accounts currently belong to one workspace and email addresses are globally unique.

Role assignment happens when an account is created. Existing-role editing, password resets and email invitations are separate future features; this page does not show nonfunctional controls for them. An uncertain creation result requires refreshing the member list before manually trying again. No account mutation is automatically retried.

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
