#!/usr/bin/env bash
# Consistent backup: pauses API/worker writes and resumes their previous running state.
set -euo pipefail
umask 077
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${1:?Usage: backup.sh /absolute/path/production.env /backup/directory}"
backup_root="${2:?Provide a private backup directory}"
compose=(docker compose --env-file "$env_file" -p rag-production -f "$project_root/compose.yaml" -f "$project_root/compose.production.yaml")
mkdir -p -- "$backup_root"
chmod 700 -- "$backup_root"
destination="$(mktemp -d "$backup_root/backup-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
mapfile -t running < <("${compose[@]}" ps --status running --services api ingestion_worker)
resume() {
    status=$?
    trap - EXIT
    if ((${#running[@]})); then
        "${compose[@]}" start "${running[@]}" >/dev/null || status=1
    fi
    exit "$status"
}
trap resume EXIT
if ((${#running[@]})); then
    "${compose[@]}" stop "${running[@]}" >/dev/null
fi
"${compose[@]}" exec -T postgres pg_dump -U rag -Fc rag > "$destination/database.dump"
"${compose[@]}" run --rm --no-deps --entrypoint tar api -C /app/uploads -czf - . > "$destination/uploads.tar.gz"
"${compose[@]}" exec -T ollama ollama list > "$destination/models.txt"
"${compose[@]}" exec -T postgres pg_restore --list < "$destination/database.dump" >/dev/null
(cd -- "$destination" && sha256sum database.dump uploads.tar.gz models.txt > SHA256SUMS)
printf 'Complete backup, UTC %s\n' "$(date -u +%FT%TZ)" > "$destination/COMPLETED"
printf 'Backup written to %s. Encrypt and copy it off the VPS.\n' "$destination"
