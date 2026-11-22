#!/usr/bin/env bash
#
# =============================================================================
# UMS Mart - deployment / update script
#
# Run this ON THE SERVER, from any directory, as a user that can sudo to the
# service account. It is idempotent: running it twice is safe.
#
#   sudo -u umsmart bash /home/ums_mart/deployment/scripts/deploy.sh
#
# What it does, in order:
#   1. Verifies the environment (.env present, PostgreSQL reachable)
#   2. Pulls the latest code (skipped with --no-pull)
#   3. Installs/refreshes Python dependencies inside the venv
#   4. Runs Django system checks against PRODUCTION settings
#   5. Takes a database backup before touching the schema
#   6. Applies migrations
#   7. collectstatic
#   8. Restarts Gunicorn and reloads Nginx
#   9. Verifies /health/ answers
#
# It refuses to continue - and leaves the previous release running - if any
# step fails.
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration - override with environment variables if your layout differs.
# ---------------------------------------------------------------------------
# Derive the project root from this script's own location
# (<root>/deployment/scripts/<file>) so the scripts work wherever the project
# is unpacked - /home/ums_mart on the VPS, /srv/apps/ums_mart, or anywhere else.
_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd -- "${_SCRIPT_DIR}/../.." && pwd)}"
BACKEND_DIR="${BACKEND_DIR:-${PROJECT_ROOT}/backend}"
VENV_DIR="${VENV_DIR:-/home/ums_mart/venv}"
SERVICE_NAME="${SERVICE_NAME:-ums-mart}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8001/health/}"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
MANAGE="${PYTHON} ${BACKEND_DIR}/manage.py"

DO_PULL=1
for arg in "$@"; do
    case "${arg}" in
        --no-pull) DO_PULL=0 ;;
        --help|-h)
            sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown argument: ${arg}" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="${BACKEND_DIR}/logs/deploy-${TIMESTAMP}.log"

log()  { printf '\n\033[1;34m[%s]\033[0m %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "${LOG_FILE}"; }
ok()   { printf '\033[1;32m  OK\033[0m %s\n' "$*" | tee -a "${LOG_FILE}"; }
die()  { printf '\n\033[1;31m  FAILED:\033[0m %s\n' "$*" | tee -a "${LOG_FILE}" >&2; exit 1; }

on_error() {
    local exit_code=$?
    printf '\n\033[1;31mDeployment aborted (exit %s). The previous release is still running.\033[0m\n' "${exit_code}" >&2
    printf 'Inspect %s for details.\n' "${LOG_FILE}" >&2
    exit "${exit_code}"
}
trap on_error ERR

mkdir -p "${BACKEND_DIR}/logs"

# ---------------------------------------------------------------------------
# 0. Sanity checks
# ---------------------------------------------------------------------------
log "Pre-flight checks"
[[ -d "${BACKEND_DIR}" ]]        || die "Backend directory not found: ${BACKEND_DIR}"
[[ -x "${PYTHON}" ]]             || die "Virtualenv python not found: ${PYTHON}"
[[ -f "${BACKEND_DIR}/.env" ]]   || die ".env is missing at ${BACKEND_DIR}/.env - copy .env.example and fill it in"
command -v git      >/dev/null   || die "git is not installed"
command -v psql     >/dev/null   || die "psql is not installed"
ok "Layout, virtualenv and .env look sane"

# Refuse to deploy with DEBUG on: it leaks tracebacks and settings.
if grep -qiE '^DEBUG=(True|1|yes)$' "${BACKEND_DIR}/.env"; then
    die "DEBUG is enabled in ${BACKEND_DIR}/.env. Refusing to deploy production with DEBUG on."
fi
ok "DEBUG is off"

# ---------------------------------------------------------------------------
# 1. Database reachability
# ---------------------------------------------------------------------------
log "Checking the database connection"
cd "${BACKEND_DIR}"
"${MANAGE}" check --database default >/dev/null \
    || die "Django cannot reach PostgreSQL. Check DB_* in .env and that postgresql is running."
ok "Database reachable"

# ---------------------------------------------------------------------------
# 2. Code update
# ---------------------------------------------------------------------------
if [[ "${DO_PULL}" -eq 1 && -d "${PROJECT_ROOT}/.git" ]]; then
    log "Fetching the latest code"
    PREVIOUS_REV="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
    git -C "${PROJECT_ROOT}" fetch --quiet --all
    git -C "${PROJECT_ROOT}" reset --hard --quiet "@{u}" \
        || die "git reset failed - resolve the conflict manually"
    CURRENT_REV="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
    ok "Code updated ${PREVIOUS_REV} -> ${CURRENT_REV}"
else
    log "Skipping git pull (no repository or --no-pull supplied)"
fi

# ---------------------------------------------------------------------------
# 3. Dependencies
# ---------------------------------------------------------------------------
log "Installing Python dependencies"
"${PIP}" install --quiet --upgrade pip
"${PIP}" install --quiet --upgrade -r "${BACKEND_DIR}/requirements.txt" \
    || die "pip install failed - see the output above"
ok "Dependencies installed"

# ---------------------------------------------------------------------------
# 4. Django checks against production settings
# ---------------------------------------------------------------------------
log "Running Django system checks (production settings)"
DJANGO_SETTINGS_MODULE=config.settings.production "${MANAGE}" check --deploy \
    || die "manage.py check --deploy reported problems. Fix them before deploying."
ok "System checks passed"

# ---------------------------------------------------------------------------
# 5. Pre-migration backup
# ---------------------------------------------------------------------------
log "Backing up the database before migrating"
BACKUP_SCRIPT="${PROJECT_ROOT}/deployment/scripts/backup.sh"
if [[ -x "${BACKUP_SCRIPT}" ]]; then
    bash "${BACKUP_SCRIPT}" --label "pre-deploy-${TIMESTAMP}" \
        || die "Backup failed - refusing to migrate without a safety net"
    ok "Backup written"
else
    printf '\033[1;33m  WARNING:\033[0m %s not executable; skipping the pre-deploy backup\n' "${BACKUP_SCRIPT}"
fi

# ---------------------------------------------------------------------------
# 6. Migrations
# ---------------------------------------------------------------------------
log "Applying migrations"
"${MANAGE}" migrate --noinput || die "Migrations failed - the database may be in a partial state. Restore the backup above."
ok "Migrations applied"

# ---------------------------------------------------------------------------
# 7. Static files
# ---------------------------------------------------------------------------
log "Collecting static files"
"${MANAGE}" collectstatic --noinput --clear -v 0 || die "collectstatic failed"
ok "Static files collected"

# ---------------------------------------------------------------------------
# 8. Restart services
# ---------------------------------------------------------------------------
log "Restarting ${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}" || die "systemctl restart ${SERVICE_NAME} failed"
sleep 3
sudo systemctl is-active --quiet "${SERVICE_NAME}" \
    || die "${SERVICE_NAME} is not active after restart. Check: journalctl -u ${SERVICE_NAME} -n 100"
ok "${SERVICE_NAME} is running"

log "Reloading Nginx"
sudo nginx -t >/dev/null 2>&1 || die "nginx -t failed - fix /etc/nginx before reloading"
sudo systemctl reload nginx || die "nginx reload failed"
ok "Nginx reloaded"

# ---------------------------------------------------------------------------
# 9. Smoke check
# ---------------------------------------------------------------------------
log "Verifying the health endpoint"
HEALTH_BODY="$(curl -fsS --max-time 10 "${HEALTH_URL}")" \
    || die "Health check failed: ${HEALTH_URL} did not answer 2xx. Check journalctl -u ${SERVICE_NAME} -n 100"
echo "  ${HEALTH_BODY}" | tee -a "${LOG_FILE}"
if ! grep -q '"database": *"up"' <<<"${HEALTH_BODY}"; then
    die "Health endpoint answered but reports the database is NOT up"
fi
ok "Health check passed (database up)"

printf '\n\033[1;32mDeployment complete.\033[0m Log: %s\n\n' "${LOG_FILE}"
