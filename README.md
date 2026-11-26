# Atlas — employee knowledge assistant

Atlas is a workspace-based document assistant for organisations. Administrators create a workspace, add members and upload documents; employees can ask questions about the documents available to them and open cited sources to check an answer. The application uses React and TypeScript, a FastAPI backend, PostgreSQL and local Ollama models.

## What the application does

- **Overview:** shows a welcome message, document activity and a quick question field. Administrators also see the member count and management shortcuts.
- **My documents:** browse and search accessible documents, open originals, or ask about one file. Administrators upload documents, set company, personal or restricted access, retry failed uploads and delete documents.
- **Ask documents:** ask across accessible documents or a selected file. Answers display citation markers and a source sidebar grouped by document, with page references where available. Questions are independent; previous conversation turns are not sent as context.
- **Members:** administrators create, search, edit and remove member accounts. A member cannot remove their own account from this page.
- **Account:** update your name, password and profile photo, or sign out through the profile menu. A new organisation is registered with an administrator's name, email and password confirmation.

Retrieval checks the signed-in user's workspace and document access before searching. Personal-document questions can use available account identity and document assignments. Citations show retrieved sources, but are not a guarantee that every answer is correct; open the original document to verify important details.

## Document support and limitations

The current uploader accepts UTF-8 `.txt` files and text-based `.pdf` files. It extracts text, creates overlapping sentence-aware chunks and embeddings, then stores them for retrieval. Processing runs in a separate ingestion worker; an upload that cannot be processed can be retried.

Scanned PDFs require OCR before upload. Images, charts and complex tables are not reliably interpreted as visual content. Improving extraction and answering for these formats is planned; see the [future-work checklist](docs/release-roadmap.md). Check upload limits in the application and verify answers against source documents.

## Run locally with Docker

Install Docker and the Docker Compose plugin. The selected Ollama models need enough disk space and memory; CPU inference may be slow.

1. If `.env` does not already exist, copy `.env.example` to `.env`. Set `RAG_DB_PASSWORD` and `JWT_SECRET_KEY` to two independent random values. Do not overwrite an existing `.env` or commit secrets.
2. Build and start the services, then download the models:

   ```sh
   docker compose -p rag-updated up -d --build
   docker compose -p rag-updated exec ollama ollama pull all-minilm
   docker compose -p rag-updated exec ollama ollama pull qwen2.5:3b
   ```

3. Open [http://127.0.0.1:8080](http://127.0.0.1:8080), create an organisation, upload a supported document and wait for processing before asking a question. API documentation is at [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

The Compose project includes PostgreSQL, Ollama, the API, the ingestion worker and the web interface. Database data, uploads and model files use named volumes. PostgreSQL and Ollama are not exposed as host ports in the local configuration.

Use the same project name for subsequent commands:

```sh
docker compose -p rag-updated ps
docker compose -p rag-updated logs --tail=100 api ingestion_worker web
docker compose -p rag-updated up -d --build web   # after frontend changes
docker compose -p rag-updated up -d --build       # after backend or Compose changes
docker compose -p rag-updated down                 # stops services; retains volumes
```

If port 8080 or 8001 is already allocated, check for an existing Compose project with `docker compose ls` and `docker ps`. Reuse or stop the appropriate existing project before starting another. Avoid `down --volumes` unless you intend to delete its persisted data.

## Password recovery and public hosting

The local Compose configuration enables direct password reset by email address without proving mailbox ownership. This is a **local-only development shortcut**: anyone who can reach that endpoint and knows an account email can reset its password. Do not expose this configuration to other users or the internet. For remote access, disable `LOCAL_DIRECT_PASSWORD_RESET` and configure the email-based reset flow, or disable the capability until it is configured and tested.

The [deployment guide](deploy/README.md) describes the separate Docker/VPS profile and its prerequisites. The [free deployment guide](deploy/FREE-DEPLOYMENT-GUIDE.md) discusses options when you have no server or purchased domain. These are preparation guides, not a claim that the application has been deployed or independently audited. Complete the [release checks](docs/release-roadmap.md) before a public launch.

## Develop and verify

See [backend/README.md](backend/README.md) for Python, database, migrations, worker and inference setup, and [web/README.md](web/README.md) for the frontend development server and commands. API configuration examples are in `backend/.env.example`; never commit real credentials.

```sh
# Backend, from the repository root
uv sync --directory backend --locked
uv run --directory backend --locked pytest -q

# Frontend
cd web
npm ci
npm test
npm run build
```

Automated tests use mocks or disposable test databases where configured; they do not establish production performance or answer quality. Real-model evaluation, migration and backup/restore checks should be run on the intended deployment environment. More detail is in [verification](docs/verification.md), [retrieval evaluation](docs/retrieval-optimization.md) and [answer evaluation](docs/answer-evaluation.md).

## Repository

- `web/` — React application and local Nginx configuration.
- `backend/` — API, retrieval and ingestion services, worker, database migrations and evaluation tools.
- `compose.yaml` — local services; other Compose files provide separate deployment profiles.
- `docs/` and `deploy/` — project notes and deployment guides.
