# Public deployment on a Docker VPS

If you have no purchased server or domain, start with the [detailed free deployment guide](FREE-DEPLOYMENT-GUIDE.md). It covers a temporary HTTPS tunnel from your existing computer, private access, and a conditional free-VM route. The companion `compose.demo.yaml` disables local direct password reset and public signup before remote access.

This is a deployment configuration, not an automatic public launch. Use your own domain and server. Size CPU, RAM and disk from real-model tests on the intended host; the small local models can still be slow on CPU. There is no hardware or concurrency SLA yet.

## Provision and configure

1. Install Docker Engine and a current Compose plugin supporting `!reset` (v2.24.4+). Use a maintained Linux host with security updates.
2. Point the domain's A record at the VPS. Add an AAAA record only if IPv6 reaches it. Permit inbound SSH on your actual management port and TCP 80/443 (UDP 443 is optional for HTTP/3). Keep PostgreSQL, Ollama and API ports private.
3. Clone the project. Copy `deploy/production.env.example` to a private file outside the repository, for example `/etc/atlas/production.env`, and restrict it to the operator (`chmod 600`). Set `PUBLIC_DOMAIN` and `ACME_EMAIL`.
4. Generate two independent secrets with `openssl rand -hex 32`; use them for `RAG_DB_PASSWORD` and `JWT_SECRET_KEY`. Never deploy the example placeholders. Keep an encrypted copy of secrets separately from backups.
5. Pin tested container digests and the embedding model digest for a controlled release. The example image tags identify major runtime families but are not immutable release pins.

Every production command must use the same environment file, Compose files and project name:

```sh
docker compose --env-file /etc/atlas/production.env -p rag-production \
  -f compose.yaml -f compose.production.yaml config --quiet

docker compose --env-file /etc/atlas/production.env -p rag-production \
  -f compose.yaml -f compose.production.yaml up -d --build
```

Only Caddy publishes host ports in this profile. It obtains and renews certificates and redirects HTTP to HTTPS. Its certificate data lives in persistent volumes. The web proxy trusts forwarding headers only from private proxy networks; do not expose the web/API containers separately or attach untrusted workloads to this network. If another reverse proxy/CDN precedes Caddy, configure its trusted proxies explicitly before relying on client-IP rate limits.

## Models and first administrator

```sh
docker compose --env-file /etc/atlas/production.env -p rag-production \
  -f compose.yaml -f compose.production.yaml exec ollama ollama pull all-minilm

docker compose --env-file /etc/atlas/production.env -p rag-production \
  -f compose.yaml -f compose.production.yaml exec ollama ollama pull qwen2.5:3b

docker compose --env-file /etc/atlas/production.env -p rag-production \
  -f compose.yaml -f compose.production.yaml exec api \
  .venv/bin/python scripts/create_workspace.py --name 'Your organisation' --email admin@example.com
```

The bootstrap command prompts for a password without logging it or returning a token. Public signup is disabled by the production override. Administrators create employee accounts in Members. The login screen discovers and respects this policy. Existing local users/data are not copied into production automatically: production has its own volume namespace.

## Protection and operations

The web proxy limits request bodies, authentication traffic, chat traffic, concurrent chat connections and general API traffic. These are per-client-IP limits; tune them for shared office networks and measured capacity. They are not per-account billing quotas. Caddy adds HTTPS/security headers. The API emits request IDs, route templates, response status and duration, excluding request bodies, credentials and query strings. These operational logs are not a persistent compliance audit trail.

Use external uptime checks, monitor disk/RAM/CPU and failed indexing, and define log rotation and retention on the VPS. Set Docker daemon log rotation before sustained use. Registration limits do not replace per-workspace storage/job quotas if onboarding untrusted organisations.

## Backups and recovery

```sh
bash deploy/backup.sh /etc/atlas/production.env /srv/atlas-backups
bash deploy/verify-backup.sh /srv/atlas-backups/backup-TIMESTAMP-SUFFIX
```

The backup briefly stops API/worker writes for database/file consistency and restores their previous running state even on failure. Plan a maintenance window. It archives PostgreSQL, original uploads and a model inventory. Backup directories/files are private but **not encrypted**: encrypt them and copy them off the VPS using your organisation's storage policy. Protect the environment/secrets separately. Model weights and TLS state are not included; restore/pull the pinned models and let Caddy reissue certificates when appropriate.

Verification creates a new PostgreSQL container with no network, published ports or production volumes. It restores the database and checks upload archive integrity. It never imports into the running application. For disaster recovery, first rehearse in a separate staging project, restore database and uploads together, provide the original JWT/database secrets and pinned models, and check file access and known answers before directing DNS at the restored service. Never use `down --volumes` on production as an upgrade step.

## Release acceptance

Before allowing real employees onto the public site, verify the actual hostname/TLS, an administrator and two isolated employees, upload/reindex/replacement, a successful off-host backup and restore rehearsal, resource/concurrency behaviour, and answers on representative company documents. The included synthetic real-model report is a regression check, not proof of production correctness or security certification. OCR, complex visual table reconstruction, indexed search, SSO, account-based quotas and a persistent audit trail remain separate capabilities.
