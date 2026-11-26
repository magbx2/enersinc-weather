#!/usr/bin/env bash
# Verify a fresh `docker compose up` without any manual setup step.
# Fails loudly instead of letting a half-started stack look healthy.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:${BACKEND_PORT:-8000}}"
attempts="${VERIFY_ATTEMPTS:-60}"
sleep_seconds="${VERIFY_INTERVAL:-2}"

log() { printf '%s verify %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

log "waiting for ${BASE_URL}/health/"
ready=0
for _ in $(seq 1 "${attempts}"); do
  if body="$(curl --fail --silent --show-error "${BASE_URL}/health/" 2>/dev/null)"; then
    log "health responded: ${body}"
    ready=1
    break
  fi
  sleep "${sleep_seconds}"
done

if [ "${ready}" -ne 1 ]; then
  log "ERROR: health endpoint did not become ready"
  docker compose ps || true
  exit 1
fi

log "checking the SPA shell"
shell="$(curl --fail --silent --show-error "${BASE_URL}/")"
if ! printf '%s' "${shell}" | grep -q '<div id="root">'; then
  log "ERROR: / did not return the SPA shell"
  exit 1
fi

log "checking an API route returns JSON"
api="$(curl --fail --silent --show-error "${BASE_URL}/weather/?page=1&page_size=1")"
if ! printf '%s' "${api}" | grep -q '"results"'; then
  log "ERROR: /weather/ did not return a paginated JSON payload"
  exit 1
fi

log "all startup checks passed"
