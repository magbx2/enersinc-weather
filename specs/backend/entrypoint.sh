#!/usr/bin/env bash
# Single entrypoint for every backend-role container (web, worker, beat, tests).
# It is idempotent: migrations and static collection may run on every start.
set -euo pipefail

log() { printf '%s entrypoint %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

log "applying migrations"
python manage.py migrate --noinput

# Static collection only matters for the web role; worker/beat and one-off
# commands (tests, shell) skip it and do not require a built SPA.
if [ "${1:-}" = "daphne" ] || [ "$#" -eq 0 ]; then
  if [ ! -f /app/spa_dist/.build-complete ]; then
    log "ERROR: SPA build marker /app/spa_dist/.build-complete is missing."
    log "The frontend service must finish before the backend starts."
    exit 1
  fi
  log "collecting static assets"
  python manage.py collectstatic --noinput --clear
fi

log "starting: ${*:-daphne}"
exec "$@"
