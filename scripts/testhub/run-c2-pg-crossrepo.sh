#!/usr/bin/env bash
# AIR-1353: disposable, socket-only PG18 contract with api-gateway #455.
set -euo pipefail

JASMIN_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
API_REPO="${1:?pass the isolated api-gateway #455 worktree path}"
PYTHON_BIN="${ATC_C2_TEST_PYTHON:-python3.12}"
EXPECTED_API_HEAD='ae7cb0e7e3f98d7d5685353bf3a1b2fbb541ec52'

[[ "$API_REPO" == /private/tmp/atc-* ]] || {
  echo 'api-gateway input must be an isolated /private/tmp/atc-* worktree' >&2
  exit 2
}
[[ "$(git -C "$API_REPO" rev-parse HEAD)" == "$EXPECTED_API_HEAD" ]] || {
  echo 'api-gateway input is not the reviewed #455 head' >&2
  exit 2
}
command -v postgres >/dev/null
command -v initdb >/dev/null
command -v pg_ctl >/dev/null
command -v psql >/dev/null
"$PYTHON_BIN" -c 'import psycopg' >/dev/null

BASE="$(mktemp -d /private/tmp/atc-testhub-c2-crossrepo.XXXXXX)"
DATA="$BASE/data"
SOCKET="$BASE/socket"
mkdir -m 700 "$SOCKET"

cleanup() {
  if [[ -f "$DATA/postmaster.pid" ]]; then
    pg_ctl -D "$DATA" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  rm -rf -- "$BASE"
}
trap cleanup EXIT

initdb -D "$DATA" -U testhub_admin --auth=trust -E UTF8 >/dev/null
pg_ctl -D "$DATA" -o "-c listen_addresses='' -k '$SOCKET'" \
  -l "$BASE/postgres.log" -w start >/dev/null
psql -h "$SOCKET" -U testhub_admin -d postgres -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE ROLE testhub_c2_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE testhub_c2_provisioner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE testhub_route_operator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE testhub_c2_crossrepo;
SQL
psql -h "$SOCKET" -U testhub_admin -d testhub_c2_crossrepo -v ON_ERROR_STOP=1 \
  -f "$API_REPO/migrations/100_testhub_schema.sql" >/dev/null
psql -h "$SOCKET" -U testhub_admin -d testhub_c2_crossrepo -v ON_ERROR_STOP=1 \
  -f "$API_REPO/migrations/101_testhub_c2_authority.sql" >/dev/null
psql -h "$SOCKET" -U testhub_admin -d testhub_c2_crossrepo -v ON_ERROR_STOP=1 \
  -f "$API_REPO/scripts/audit/air-1353/testhub-c2-authority-fixture.sql" >/dev/null
psql -h "$SOCKET" -U testhub_admin -d testhub_c2_crossrepo -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
GRANT CONNECT ON DATABASE testhub_c2_crossrepo TO
  testhub_c2_reader, testhub_c2_provisioner, testhub_route_operator;
GRANT USAGE ON SCHEMA testhub TO
  testhub_c2_reader, testhub_c2_provisioner, testhub_route_operator;
GRANT SELECT ON testhub.c2_principals, testhub.c2_leases,
  testhub.airtime_connectors TO testhub_c2_reader;
GRANT EXECUTE ON FUNCTION testhub.issue_c2_lease(TEXT, UUID, INTEGER)
  TO testhub_c2_provisioner;
GRANT SELECT, UPDATE(status) ON testhub.routes TO testhub_route_operator;
SQL

cd "$JASMIN_REPO"
PYTHONPATH="$JASMIN_REPO" "$PYTHON_BIN" \
  tests/managers/c2_pg_crossrepo.py live "$SOCKET"
pg_ctl -D "$DATA" -m fast -w stop >/dev/null
PYTHONPATH="$JASMIN_REPO" "$PYTHON_BIN" \
  tests/managers/c2_pg_crossrepo.py outage "$SOCKET"
