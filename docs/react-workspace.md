# React workspace milestone

## Complete workflow
Register/sign in → administrator uploads a text/PDF document → indexing succeeds → ask a question → expand retrieved excerpts → confirm deletion. Members can browse documents and ask questions but do not see administrator mutation controls. The API's existing role and tenant checks remain authoritative.

## Architecture
- `web/src/api/`: typed DTOs and one relative-origin fetch client; bounded timeouts, bearer headers, structured errors, no automatic mutation retry.
- `web/src/components/`: sign-in/registration, document lifecycle, chat/source excerpts and native delete confirmation.
- `web/src/App.tsx`: ephemeral session boundary and workspace navigation. Panels remain mounted during sidebar navigation so the conversation is retained; sign-out unmounts both.
- `web/vendor/`: versioned shared component package from the portfolio repository.
- `web/nginx.conf`: static serving and same-origin `/api/` proxy for local Compose.

The only backend contract addition is authenticated `GET /documents/limits`. It exposes supported suffixes and configured upload bytes, not provider credentials or server filesystem paths. No database migration is required for this milestone.

## Privacy and error behaviour
No token or conversation is written to browser storage. Protected 401 responses clear the workspace. Password forms and raw validation inputs are not logged. Model answers use safe Markdown with raw HTML disabled; document excerpts remain plain React text nodes. See `docs/answer-format-and-chunking.md` for the rendering and sentence-aware indexing contracts. Upload/delete transport failures are shown as uncertain results, without automatically issuing another mutation.

The current backend has expiring bearer tokens and no refresh session. Reload requires sign-in again. A future persistent session should be designed with secure server-side refresh cookies and CSRF protection, rather than storing a long-lived token in localStorage.

## Release limits
Real Ollama inference, quality evaluation, ingestion worker isolation and public traffic limits remain release gates. Local container checks and DOM interaction tests do not substitute for full browser acceptance or actual model evaluation. No live URL should be added to the portfolio until hosting and the complete real-model workflow have been verified.

## Verification on this branch

- **27 frontend tests passed**: account entry, multipart upload, dynamic limits, confirmation/cancellation, source excerpts, role-dependent controls, safe text rendering, session expiry, uncertain mutations, duplicate-submit prevention and motion preferences.
- **39 backend tests passed**, including the new authenticated upload-limit contract.
- TypeScript, Vite production build, Prettier and backend Ruff checks passed.
- Both API and web Docker images built. The container web build produced the same application asset hashes as the local build.
- An isolated Nginx → FastAPI → PostgreSQL stack passed static asset serving, same-origin API forwarding, registration, upload/index, source excerpt retrieval, tenant isolation and deletion. Inference used a deterministic HTTP test double, not Ollama weights.
- No public deployment, paid inference, model-quality result or full browser visual acceptance is claimed. The next gate is real-model testing on an adequately sized host.

During container verification this environment ran out of temporary build space. The web image was simplified to remove node_modules and the npm cache within the build step. Unused build cache was cleared; application source, data volumes and unrelated running services were not removed.
