# First real-user release

## User and complete workflow
An administrator creates a workspace and uploads a small set of documents. Workspace members ask questions and inspect source excerpts. The administrator can delete documents and stop them being retrieved. The first public demonstration should use a curated sample workspace or invitation-based signup, rather than unrestricted upload and inference.

## Milestone 1 — backend foundation (this change)
- Reproducible dependencies and lockfile, environment examples, baseline migrations.
- Active-user and role enforcement, transaction-safe registration.
- Restricted uploads, cleanup on failures, tenant-scoped transactional embedding storage.
- Bounded cosine retrieval and retrieved excerpts; no stale FAISS content after deletion.
- Configurable local inference, request timeouts and clear provider errors.
- Isolated automated coverage and local Docker deployment configuration.

## Milestone 2 — reliable product workflow
- Replace the transitional Streamlit client with React/TypeScript/Vite and the shared Porcelain & Azure components; azure is this project's accent.
- Sign-in, workspace navigation, upload status, document deletion and a question/answer screen with expandable source excerpts and explicit busy/error/empty states.
- Ingestion jobs and persisted status with cancellation/failure recovery, resource-limited PDF parsing and bounded concurrency.
- Model-based evaluation: answerable/unanswerable questions, retrieval recall, unsupported-claim checks, citation coverage and adversarial document instructions. Report actual measured results.
- PostgreSQL/pgvector indexing once measured corpus and latency justify it; preserve tenant constraints and transactional deletion.

## Milestone 3 — deployment gate
- Verify initial and existing-schema upgrades using disposable PostgreSQL, then test backup and restore.
- Exercise actual Ollama models against known documents on the intended CPU/GPU host. Record memory, storage, latency, concurrency and timeouts. No inference measurement is currently claimed.
- Define persistent database/file storage, HTTPS origin, secrets, usage quotas, signup/invitation policy and ingress body/rate limits. Do not expose Ollama to the public internet.
- Install upload parsing and model execution in bounded worker processes. Add telemetry without logging private questions or document bodies.
- Choose hosting only after resource measurements. No paid infrastructure or public deployment is part of this backend-foundation change.

## Milestone 4 — portfolio evidence
Add the real application URL, repository link, approved screenshots, architecture, measured evaluation and a clear account of contribution/limitations. Until these checks pass, label it as in development and omit a live application badge.
