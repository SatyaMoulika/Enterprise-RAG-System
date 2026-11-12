# Backend-foundation verification

Run on 12 November 2026 against the foundation branch. No production/development database, inference provider, paid service or model weights were used.

| Check | Result | Scope |
|---|---|---|
| `uv sync --directory backend --locked` | Passed | Reproducible API/test environment without optional model/UI installs |
| `uv run --directory backend --locked pytest -q` | 38 passed | Disposable SQLite; provider contracts stubbed |
| `uv run --directory backend --locked ruff check .` | Passed | Backend source, tests, migrations and smoke script |
| `uv run --directory backend --locked ruff format --check .` | Passed | Formatting |
| Guarded disposable PostgreSQL 16 smoke script | Passed | Upgrade/downgrade, metadata parity, registration, upload, JSON vectors, excerpt retrieval, tenant isolation and deletion |
| API Docker image build | Passed | Locked non-dev dependencies, nonroot `rag` runtime user |
| Container startup with disposable PostgreSQL | Passed | Automatic migrations and `GET /ready` returned 200 |

The test suite reports one upstream Starlette TestClient deprecation warning. It does not affect the passing assertions; it should be revisited when the test client dependency transition is stable.

The PostgreSQL verifier refuses existing tables and requires an explicitly confirmed local database named `rag_release_test`. It never selects a database from a developer's `.env`.

Docker checks used a task-specific PostgreSQL container and task-specific API container. Only these containers were removed afterwards; no existing database, named development volume or unrelated service was stopped.

## Still unverified / not shipped

- Actual Ollama model download, embeddings, generated answers, latency and memory under real load.
- Model grounding, answer quality, refusal and citation accuracy against an evaluation set.
- Browser acceptance testing and the planned React frontend.
- Cloud hosting, HTTPS, usage quotas, ingress limits and backup/restore operations.
- In-place upgrades of an existing manually created schema; only fresh disposable schemas were exercised.

A passing readiness endpoint confirms database schema availability, not model readiness or public-production fitness.
