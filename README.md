# Enterprise RAG System

A workspace-scoped document assistant: register an enterprise, upload UTF-8 text or text-based PDFs, ask questions, and inspect the retrieved excerpts that support an answer. FastAPI, PostgreSQL and a configurable Ollama inference service.

This branch establishes a tested backend foundation. It is **not yet a public production release**. The active interface is now a Porcelain & Azure React workspace in `web/`. The original Streamlit client remains as a transitional reference. Public-production release gates still apply.

## First local run

Requires Docker Compose and sufficient RAM/disk for the selected Ollama models. CPU inference is supported but may be slow. No paid API is required by this configuration.

1. Copy `.env.example` to `.env` if no `.env` exists. Replace both placeholders with independent random secrets (e.g. generate each with `python -c "import secrets; print(secrets.token_hex(32))"`). Do not overwrite an existing environment file.
2. Start the services and explicitly download the models:

```sh
docker compose up -d --build
docker compose exec ollama ollama pull all-minilm
docker compose exec ollama ollama pull qwen2.5:3b
```

3. Open `http://127.0.0.1:8080` for the React workspace. Create a workspace, upload a document, and ask a question. Backend API docs remain at `http://localhost:8000/docs`.

The API is bound to localhost. Database and inference ports are not exposed. The API image build and startup were verified against disposable PostgreSQL. Actual model inference must still be verified on the deployment host; the unit/integration tests substitute provider responses and never download weights.

`GET /health` checks process liveness. `GET /ready` checks the database schema; inference availability is checked when an upload/question is attempted. Missing models return 503, not a fabricated answer.

## Develop without Docker

Install Python 3.12+ and uv. From the repository root:

```sh
uv sync --directory backend --locked
# Configure backend/.env using backend/.env.example and an existing local PostgreSQL instance.
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn main:app --reload
```

The existing Streamlit client remains under `frontend/`. Install its optional dependencies and start it with:

```sh
uv run --directory backend --extra legacy-ui streamlit run ../frontend/app.py
```

Set `RAG_API_BASE_URL` for a nondefault API origin. Its requests have finite timeouts. For the active React interface, see [web/README.md](web/README.md). Deployment-wide request throttling remains follow-up work.

## Verify

```sh
uv sync --directory backend --locked
uv run --directory backend --locked pytest -q
uv run --directory backend --locked ruff check .
uv run --directory backend --locked ruff format --check .
```

Tests use fresh disposable SQLite databases and fake inference outputs. They do not open a development database, call a paid provider, or load model weights. A separate disposable PostgreSQL smoke check and container startup also passed; see [verification details](docs/verification.md). Real inference and deployment-host verification remain release gates.

## React frontend

```sh
cd web
npm ci
npm run dev
# In a separate terminal, start the backend as above.
```

Open `http://127.0.0.1:5173`. The Vite proxy keeps API requests on the same browser origin. Run `npm test` and `npm run build` from `web/` for frontend verification. See [the React architecture notes](docs/react-workspace.md) for session, component and error contracts.

## Key behaviour

- Each registration creates a new workspace and its administrator in one transaction; duplicate workspace names do not grant membership.
- Administrators manage uploads and users. Active members can list their workspace documents and ask questions. Deactivated users cannot continue using old tokens.
- Uploads are restricted by type, byte size, extracted text size and chunk count. Files receive random server-side paths; failures clean up files and roll back records.
- Embeddings, model identity and document chunks are stored together. Retrieval scopes by current workspace and live documents **before ranking**. Deletion removes chunks and vectors together.
- Retrieval uses cosine similarity over a bounded set of persisted vectors. This small-corpus implementation trades FAISS speed for transactional correctness; use PostgreSQL/pgvector before increasing scale. A workspace beyond the configured bound returns an explicit capacity error.
- Answers include `sources` (document IDs, kept for the old client) and structured `citations` (retrieved title, chunk and excerpt). These are retrieval provenance, **not proof that every generated claim is supported**. Evaluate grounding before public release.
- HTTP provider calls have finite timeouts and sanitised errors. Importing the API never fetches model weights.

## Answer formatting and excerpt boundaries

Answers render safe Markdown, including headings, lists, code and tables. New uploads use sentence-aware chunks with a soft size target, whole-unit overlap and conservative PDF line-wrap cleanup. See [formatting and re-indexing notes](docs/answer-format-and-chunking.md). Re-upload affected documents and remove old copies to replace already-stored character slices.

## Existing data

Do not blindly run the initial migration against an existing manually created schema. Back up the database first and compare it with migration `0001`. Only if it matches, explicitly stamp `0001` and upgrade to `0002`; otherwise reconcile the schema first. No existing database has been inspected or modified by this change.

Old FAISS files are no longer read. Existing chunks have null embeddings after migration and are excluded from retrieval. Re-upload the original documents after upgrading; confirm replacement documents answer correctly before deleting old records. Changing embedding model/backend requires re-indexing; vectors from different model identities are never mixed.

## Before a public deployment

See [the release roadmap](docs/release-roadmap.md). Deploy only after validating PostgreSQL migrations, real-model document-to-answer behaviour, storage backup/restore and resource sizing. Add HTTPS, proxy-level request-body limits and rate/concurrency limits before exposing registration, upload or inference endpoints publicly. Application limits are checked after multipart parsing and do not replace ingress limits. Test PDF parsing in a resource-limited ingestion worker before allowing untrusted public PDF uploads. Public anonymous/open signup is not ready for production.
