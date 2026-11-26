# Atlas web application

The Atlas interface is built with React, TypeScript and Vite. It connects to the FastAPI application through a same-origin `/api` proxy. The workspace includes Overview, Ask documents, My documents, administrator-only Members, and a profile menu.

## Local development

Requires Node.js 22.12+ and npm. Start the backend and its dependencies as described in the [root README](../README.md), then run:

```sh
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to `http://127.0.0.1:8000` by default; set `RAG_API_PROXY_TARGET` in the Vite server environment to use another API origin. Do not put server secrets or model credentials in frontend environment variables.

```sh
npm run typecheck
npm test
npm run build
```

The frontend tests mock the API and do not prove model quality or production performance. The production build is served by Nginx in Docker, which also proxies `/api` to the API container.

## Product behaviour

- Registration creates an organisation and administrator; sign-in establishes a session only after the account is validated. A disabled public-registration setting is respected.
- Credentials and conversations are held in memory. Reloading or signing out clears the session and conversation.
- The overview offers quick questions and document activity. Administrators can also see member counts and management shortcuts.
- Members can browse documents they are allowed to access and ask questions across their library or one selected document. Administrators can upload, assign access, retry failed uploads and delete documents. The API enforces permissions.
- The conversation displays Markdown answers with citation buttons. The source sidebar groups references by document, shows available pages and opens the original document. Retrieved citations do not independently verify generated claims.
- Questions are submitted independently; the visible conversation is not sent as model context. Request errors and uncertain upload or deletion outcomes are shown separately from successful answers.
- Administrators manage member accounts from the Members page. The profile menu provides account details, password and photo changes, and sign-out confirmation.
- The sign-in page links to password recovery. Local Docker defaults to an insecure, direct email-address reset for private development only; see the [root README](../README.md#password-recovery-and-public-hosting) before exposing the application.

## Design and assets

The interface uses the shared `@portfolio/porcelain-azure` package from `vendor/porcelain-azure-0.1.0.tgz`, plus application-specific components and styles. It uses the Atlas mark, white cards, a pale-blue workspace background and azure accents. Decorative diagrams respect reduced-motion preferences.

`public/atlas-mark.svg` is the logo source. The favicon and app icons are committed assets; regenerate them after modifying the SVG with Python and Pillow:

```sh
python3 scripts/generate-icons.py
```

The manifest provides browser branding; the application does not include a service worker or offline document cache.

## Docker

From the repository root, `docker compose -p rag-updated up -d --build` starts the application at http://127.0.0.1:8080. After frontend-only changes, rebuild the web service with `docker compose -p rag-updated up -d --build web`. See the [root README](../README.md) for initial setup and the required Ollama model downloads.
