#!/usr/bin/env bash
# Restores only into a new network-isolated container with no production volumes.
set -euo pipefail
backup="${1:?Usage: verify-backup.sh /path/to/completed-backup}"
backup="$(cd -- "$backup" && pwd)"
[[ -f "$backup/COMPLETED" ]] || { printf 'Backup is incomplete\n' >&2; exit 1; }
(cd -- "$backup" && sha256sum --check SHA256SUMS)
tar -tzf "$backup/uploads.tar.gz" >/dev/null
container="$(docker run --detach --rm --network none --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=rag_restore_test postgres:16-alpine)"
cleanup() { docker stop "$container" >/dev/null; }
trap cleanup EXIT
for attempt in {1..60}; do
    if docker exec "$container" pg_isready -U postgres -d rag_restore_test >/dev/null 2>&1; then break; fi
    sleep 1
done
docker exec -i "$container" pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d rag_restore_test < "$backup/database.dump"
docker exec "$container" psql -v ON_ERROR_STOP=1 -U postgres -d rag_restore_test -c 'SELECT (SELECT count(*) FROM documents) AS documents, (SELECT count(*) FROM document_chunks) AS chunks;'
printf 'Database restore and upload archive integrity passed in an isolated test container.\n'
