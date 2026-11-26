# Atlas backend

The FastAPI backend manages organisation accounts, document access, ingestion, retrieval and sourced answers. PostgreSQL stores application data, chunks and embeddings; original uploads are stored on disk. The local Docker setup runs ingestion in a separate worker and uses Ollama for embeddings and answer generation.

## Local development

Requires Python 3.12+, `uv`, PostgreSQL and an Ollama instance with the configured models. From the repository root:

```sh
uv sync --directory backend --locked
# Copy backend/.env.example to backend/.env and configure your local services.
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn main:app --reload
```

For queued ingestion, run the worker separately:

```sh
uv run --directory backend python scripts/ingestion_worker.py --recover-stale-minutes 30
```

See the [root README](../README.md) for the Docker setup, model downloads and frontend. Configuration comes from environment variables or `backend/.env`. Startup requires a database URL and a JWT secret of at least 32 characters. Do not commit credentials.

```sh
uv run --directory backend --locked pytest -q
uv run --directory backend --locked ruff check .
uv run --directory backend --locked ruff format --check .
```

Tests use disposable databases and mocked providers where configured; they do not replace real-model evaluation or production-host testing. Back up existing data and check the migration history before upgrading an existing database.

## Ingestion and retrieval

The upload API accepts UTF-8 text files and text-based PDFs, subject to configured limits. Text is extracted, divided into sentence-aware overlapping chunks and embedded by the ingestion worker. Status and source data allow failed processing to be retried. Scanned PDFs need OCR before upload; visual understanding of images, charts and complex tables is future work.

Access is scoped to the current organisation and the user's document permissions before retrieval. The default retrieval strategy is dense similarity; optional lexical and hybrid strategies and a reranker can be configured for evaluation. Answers include citation metadata, including document and page details where available. Citations are source provenance, not proof of factual accuracy.

Default Ollama models are `all-minilm` for embeddings and `qwen2.5:3b` for generation. The optional SentenceTransformers backend requires its extra dependencies and compatible model/dimension settings. Embeddings from different models or revisions should not be mixed; changes may require reprocessing existing documents.

## Password recovery

`LOCAL_DIRECT_PASSWORD_RESET=true` enables a local development shortcut that allows a password to be reset using an email address without mailbox verification. Never expose this mode remotely. Disable it and configure the SMTP-based reset flow for a remote deployment, or leave recovery unavailable until configured and tested. See `backend/.env.example` and the [deployment guide](../deploy/README.md).

`GET /health` reports process liveness and `GET /ready` checks database readiness. Model availability is checked when inference is requested. See [retrieval](../docs/retrieval-optimization.md), [answer evaluation](../docs/answer-evaluation.md) and [verification](../docs/verification.md) for further details.
