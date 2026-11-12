# Atlas document workspace

Requires Node.js 22.12+ and npm.

The active React + TypeScript + Vite interface for Enterprise RAG. White surfaces and the shared Porcelain & Azure design system; azure is the project accent.

## Run locally

Start the FastAPI backend on port 8000 using the root guide, then:

```sh
cd web
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite forwards relative `/api/*` requests to `http://127.0.0.1:8000/*`. Set server-side `RAG_API_PROXY_TARGET` to use a different development API origin. No provider key or server secret belongs in a `VITE_*` environment variable.

## Verify

```sh
npm test
npm run build
```

Tests use mocked HTTP responses to exercise the real application components, role-dependent actions, source rendering, failure handling and API boundary. They do not call inference providers or a database.

## Behaviour

- Register a new workspace or sign in to an existing account. The token is accepted only after `/users/me` succeeds.
- Session tokens, selected files and conversations stay in memory; no browser storage or cookies are used for credentials. Reload/sign-out clears the session and conversation.
- Administrators can upload supported documents and confirm deletion. Members can browse and ask questions. The API remains the authority for permissions.
- Upload rules come from authenticated `/documents/limits`; client checks improve feedback, while the API enforces actual file/content limits.
- The document list uses real server records. “Stored” is not a claim about old migrated documents being searchable; the root migration/re-indexing guidance still applies.
- Answers include expandable source excerpts. Model answers use safe Markdown (including GFM tables); raw HTML is skipped and remote images are not fetched. Source excerpts and user questions remain plain text.
- Request failure is distinct from an answer. Upload/delete network failures can leave an uncertain result: inspect the refreshed document list before manually repeating. No mutation is automatically retried.
- Session expiry returns to sign-in. In-flight requests are aborted on component teardown; browser cancellation does not guarantee cancellation of backend ingestion/inference.
- Questions currently run independently; the displayed conversation is not sent as model context.

## Shared component dependency

`@portfolio/porcelain-azure` is installed from `vendor/porcelain-azure-0.1.0.tgz`, a versioned snapshot from `SatyaMoulika/ai-portfolio`. This is the same library used in the portfolio, not a separate copy of its component source. The archive is committed so `npm ci` does not need private GitHub access or a published npm package.

To update it, build/package a new version from the source design-system repository, replace the vendor archive, update package.json, regenerate package-lock.json and run this app's tests/build. This app adds only product-specific screens, feedback and a native delete dialog; shared controls, layouts, typography, tokens and motion remain in the library.

## Local container integration

The root `docker compose up -d --build` now also builds this interface. Open `http://127.0.0.1:8080`. Nginx serves Vite's static output and proxies `/api/` to the API service on the internal network. Database and inference remain internal. Do not deploy `dist/` to an arbitrary static host without a same-origin API proxy.

The Nginx body limit is 11 MiB including multipart overhead. Change that deliberately if the API upload limit changes. This is a local-only Compose setup, not a public hosting/HTTPS configuration.
