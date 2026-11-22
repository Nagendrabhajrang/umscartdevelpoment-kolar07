#!/usr/bin/env bash
#
# =============================================================================
# UMS Mart - PostgreSQL backup script
#
#   bash deployment/scripts/backup.sh                 # normal backup
#   bash deployment/scripts/backup.sh --label pre-x   # tag the archive
#   bash deployment/scripts/backup.sh --keep 30       # keep 30 days (default 14)
#
# Reads DB_NAME / DB_USER / DB_HOST / DB_PORT / DB_PASSWORD from
# ${BACKEND_DIR}/.env so there is exactly one source of credentials.
#
# Produces, in ${BACKUP_DIR}:
#   ums_mart_<timestamp>[_<label>].dump   compressed pg_dump custom format
#   ums_mart_<timestamp>[_<label>].sha256   checksum for integrity checks
#   ums_mart_<timestamp>[_<label>].log      what happened
#
# Restore with:
#   pg_restore --clean --if-exists --no-owner -d ums_mart_db <backup>.dump
#
# Schedule it with cron (see deployment/README.md):
#   15 2 * * * /bin/bash /home/ums_mart/deployment/scripts/backup.sh >> /var/log/ums_mart_backup.log 2>&1
# =============================================================================
set -Eeuo pipefail

# Derive the project root from this script's own location
# (<root>/deployment/scripts/<file>) so the scripts work wherever the project
# is unpacked - /home/ums_mart on the VPS, /srv/apps/ums_mart, or anywhere else.
_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd -- "${_SCRIPT_DIR}/../.." && pwd)}"
BACKEND_DIR="${BACKEND_DIR:-${PROJECT_ROOT}/backend}"
BACKUP_DIR="${BACKUP_DIR:-/home/ums_mart/backups}"
ENV_FILE="${BACKEND_DIR}/.env"

KEEP_DAYS="${KEEP_DAYS:-14}"
LABEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --label) LABEL="_${2:-}"; shift 2 ;;
        --keep)  KEEP_DAYS="${2:-14}"; shift 2 ;;
        --out)   BACKUP_DIR="${2}"; shift 2 ;;
        --help|-h) sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; exit 1; }

[[ -f "${ENV_FILE}" ]] || die "Missing ${ENV_FILE} - cannot read database credentials"
command -v pg_dump >/dev/null || die "pg_dump not found. Install postgresql-client."

# ---------------------------------------------------------------------------
# Read credentials from .env without sourcing it (values may contain spaces).
# ---------------------------------------------------------------------------
env_value() {
    local key="$1"
    local raw
    raw="$(grep -E "^[[:space:]]*${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true)"
    # strip surrounding quotes and trailing CR (files edited on Windows)
    raw="${raw%$'\r'}"
    raw="${raw%\"}"; raw="${raw#\"}"
    raw="${raw%\'}"; raw="${raw#\'}"
    printf '%s' "${raw}"
}

DB_NAME="$(env_value DB_NAME)"
DB_USER="$(env_value DB_USER)"
DB_HOST="$(env_value DB_HOST)"
DB_PORT="$(env_value DB_PORT)"
DB_PASSWORD="$(env_value DB_PASSWORD)"

[[ -n "${DB_NAME}" && -n "${DB_USER}" ]] || die "DB_NAME / DB_USER are empty in ${ENV_FILE}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

mkdir -p "${BACKUP_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASENAME="ums_mart_${TIMESTAMP}${LABEL}"
DUMP_FILE="${BACKUP_DIR}/${BASENAME}.dump"
LOG_FILE="${BACKUP_DIR}/${BASENAME}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

log "Starting backup of '${DB_NAME}' on ${DB_HOST}:${DB_PORT}"
log "Destination: ${DUMP_FILE}"

# ---------------------------------------------------------------------------
# Dump. PGPASSWORD is exported only for the lifetime of this process.
# -Fc  custom format: compressed, supports selective restore with pg_restore
# ---------------------------------------------------------------------------
export PGPASSWORD="${DB_PASSWORD}"
pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --no-privileges \
    --verbose \
    --file="${DUMP_FILE}" \
    || die "pg_dump failed"
unset PGPASSWORD

[[ -s "${DUMP_FILE}" ]] || die "pg_dump produced an empty file"

SIZE="$(du -h "${DUMP_FILE}" | cut -f1)"
log "Dump written (${SIZE})"

# ---------------------------------------------------------------------------
# Integrity manifest
# ---------------------------------------------------------------------------
sha256sum "${DUMP_FILE}" > "${DUMP_FILE}.sha256"
log "Checksum: $(cut -d' ' -f1 "${DUMP_FILE}.sha256")"

# Verify the archive is readable - a corrupt dump is worse than none.
pg_restore --list "${DUMP_FILE}" > /dev/null 2>&1 \
    || die "Backup archive is not readable by pg_restore - something went wrong"
log "Archive verified with pg_restore --list"

# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------
if [[ "${KEEP_DAYS}" =~ ^[0-9]+$ && "${KEEP_DAYS}" -gt 0 ]]; then
    DELETED="$(find "${BACKUP_DIR}" -maxdepth 1 -type f \
        \( -name 'ums_mart_*.dump' -o -name 'ums_mart_*.dump.sha256' -o -name 'ums_mart_*.log' \) \
        -mtime "+${KEEP_DAYS}" -print -delete | wc -l)"
    log "Retention: removed ${DELETED} file(s) older than ${KEEP_DAYS} day(s)"
else
    log "Retention: disabled (KEEP_DAYS=${KEEP_DAYS})"
fi

log "Backup complete: ${DUMP_FILE}"
