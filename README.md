# Enterprise RAG System

A workspace-scoped document assistant: register an enterprise, upload UTF-8 text or text-based PDFs, ask questions, and inspect the retrieved excerpts that support an answer. FastAPI, PostgreSQL and a configurable Ollama inference service.

This branch establishes a tested backend foundation. It is **not yet a public production release**. The active interface is a full-width React workspace in `web/`, with Overview as the landing page, My documents, Ask documents, and administrator member management. Public-production release gates still apply.

For hosting without buying a server or domain, see the [free deployment guide](deploy/FREE-DEPLOYMENT-GUIDE.md). It includes step-by-step local HTTPS sharing, private access, an optional free cloud VM, account setup, backups and troubleshooting.

## First local run

Requires Docker Compose and sufficient RAM/disk for the selected Ollama models. CPU inference is supported but may be slow. No paid API is required by this configuration.

1. Copy `.env.example` to `.env` if no `.env` exists. Replace both placeholders with independent random secrets (e.g. generate each with `python -c "import secrets; print(secrets.token_hex(32))"`). Do not overwrite an existing environment file.
2. Start the services and explicitly download the models:

```sh
docker compose -p rag-updated up -d --build
docker compose -p rag-updated exec ollama ollama pull all-minilm
docker compose -p rag-updated exec ollama ollama pull qwen2.5:3b
```

3. Open `http://127.0.0.1:8080` for the React workspace. Create a workspace, upload a document, and ask a question. Backend API docs remain at `http://localhost:8001/docs`.

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

To start the React workspace alongside the backend, follow the [React frontend setup](#react-frontend).

The active application interface is React in `web/`; see [web/README.md](web/README.md). The unused Streamlit client has been removed.

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
- Uploads are restricted by type, byte size, extracted text size and chunk count. Files receive random server-side paths. The React client queues indexing in a bounded worker; failures retain a safe status and source for retry. Synchronous integration uploads roll back and clean up on failure.
- Embeddings, model identity and document chunks are stored together. Retrieval scopes by current workspace and live documents **before ranking**. Deletion removes chunks and vectors together.
- Retrieval streams exact cosine/BM25/hybrid scoring with bounded vector memory. It does not impose the former 10,000-chunk ceiling, but still performs linear scans; evaluate an indexed backend when corpus size and measured latency require it.
- Answers include `sources` (document IDs, kept for the old client) and structured `citations` (retrieved title, chunk and excerpt). These are retrieval provenance, **not proof that every generated claim is supported**. Evaluate grounding before public release.
- HTTP provider calls have finite timeouts and sanitised errors. Importing the API never fetches model weights.

## Retrieval strategies and evaluation

Dense search remains the default. Opt-in BM25/hybrid retrieval, whole-excerpt context budgeting and a labelled synthetic evaluation runner are now available. See [the retrieval optimization guide](docs/retrieval-optimization.md) for measured fixture results, a real-model comparison command and switching strategies without re-indexing.

## Organisation-policy answer evaluation

Compare the normal five-excerpt answer with a compact two-excerpt answer using the existing Ollama models, then review factual correctness, source support and refusal. An optional cross-encoder experiment remains off by default. See [the answer evaluation guide](docs/answer-evaluation.md) for a small first run, review instructions and the separate optional model setup.

## Organisation members

Administrators can now open **Members** in the React sidebar to add, list, search and remove workspace accounts. Members and administrators are selectable roles at creation. The current account cannot remove itself, and old tokens cannot regain access when an email is re-created. Sign in again after updating; no database reset is needed. See [member-management behaviour and verification](docs/workspace-members.md).

## Answer formatting and excerpt boundaries

Answers render safe Markdown, including headings, lists, code and tables. New uploads use sentence-aware chunks with a soft size target, whole-unit overlap and conservative PDF line-wrap cleanup. See [formatting and re-indexing notes](docs/answer-format-and-chunking.md). Use **Reindex** on existing documents to apply source-aware chunking without creating duplicate copies. The source sidebar groups references into one card per document, showing cited pages and a View document action instead of extracted chunks. Citation buttons select the corresponding document and page.

## Existing data

Do not blindly run the initial migration against an existing manually created schema. Back up the database first and compare it with migration `0001`. Only if it matches, explicitly stamp `0001` and upgrade to `0002`; otherwise reconcile the schema first. No existing database has been inspected or modified by this change.

Old FAISS files are no longer read. Legacy chunks without embeddings are excluded from dense retrieval; queue **Reindex** from their stored originals. Migration `0005` preserves existing files/chunks and adds provenance and indexing state. Old chunks receive page/section metadata on reindex. Model/backend/revision changes require reindexing for dense search; lexical retrieval remains available without mixing incompatible vectors.

## Before a public deployment

See [the release roadmap](docs/release-roadmap.md). Deploy only after validating PostgreSQL migrations, real-model document-to-answer behaviour, storage backup/restore and resource sizing. Add HTTPS, proxy-level request-body limits and rate/concurrency limits before exposing registration, upload or inference endpoints publicly. Application limits are checked after multipart parsing and do not replace ingress limits. Test PDF parsing in a resource-limited ingestion worker before allowing untrusted public PDF uploads. Public anonymous/open signup is not ready for production.

### Employee document hub

Employees can browse personal letters and company/restricted documents assigned by administrators, preview/download originals, and chat across their accessible library or one document. See [employee hub setup and access rules](docs/employee-document-hub.md), including migration behaviour for existing documents and administrator access to personal files.

For financial qualifier handling and the evaluation-only claim-support reviewer, see [salary grounding and regression checks](docs/salary-grounding.md). The reviewer does not enforce or rewrite production answers.

An opt-in [bounded salary calculator](docs/salary-calculator.md) validates supported source formats and performs decimal arithmetic. It is disabled by default and can replay existing evaluation reports offline without model calls.

## Public-hosting preparation

A generic Docker/VPS profile is available in [deploy/README.md](deploy/README.md). It adds Caddy HTTPS, private internal services, disabled open signup, an operator workspace bootstrap, request limits and backup/restore verification scripts. It is separate from the local `rag-updated` project; preparing it does not publish this checkout or move local user data. Supply a real domain and server and complete the documented acceptance checks before launch.

The latest citation/source regression uses real installed Ollama models; see [the recorded evaluation](docs/answer-evaluation.md#installed-model-source-regression). Development fixtures and assistant-reviewed labels do not replace independent domain review.
