#!/usr/bin/env bash
# Synthetic PostgreSQL only: no project DSN, vault or target database.
set -euo pipefail

IMAGE='postgres:18-alpine@sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873'
PYTHON_BIN="${ATC_C2_TEST_PYTHON:-python3}"
JASMIN_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
container="$(docker run --detach --rm --publish 127.0.0.1::5432 \
  --env POSTGRES_HOST_AUTH_METHOD=trust \
  --env POSTGRES_USER=testhub_admin --env POSTGRES_DB=testhub_c2_ci \
  "$IMAGE")"
cleanup() { docker rm --force "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

port="$(docker port "$container" 5432/tcp | sed -n 's/^127\.0\.0\.1://p')"
[[ "$port" =~ ^[0-9]+$ ]] || { echo 'disposable PostgreSQL port unavailable' >&2; exit 2; }
ready=0
for _ in {1..30}; do
  if docker exec "$container" pg_isready -U testhub_admin -d testhub_c2_ci >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo 'disposable PostgreSQL failed to start' >&2; exit 2; }

PYTHONPATH="$JASMIN_REPO${PYTHONPATH:+:$PYTHONPATH}" \
ATC_C2_ROLE_PG_DISPOSABLE=1 ATC_C2_ROLE_PG_PORT="$port" \
  "$PYTHON_BIN" tests/managers/c2_pg_role_preflight_ci.py
