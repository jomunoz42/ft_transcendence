#!/usr/bin/env bash
# Runnable check for ticket 01 (Postgres container).
# Fails before docker-compose.yml defines a persisted postgres service, passes after.
#
# Checks, in order:
#   1. psql connects using the .env credentials
#   2. a row written to the database is readable back
#   3. that row is still present after `down` + `up` (no -v) -> the named volume works
set -euo pipefail

cd "$(dirname "$0")/.."

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# docker compose v2 (plugin) or docker-compose v1 (standalone), whichever exists
if docker compose version >/dev/null 2>&1; then
  compose() { docker compose "$@"; }
elif command -v docker-compose >/dev/null 2>&1; then
  compose() { docker-compose "$@"; }
else
  fail "neither 'docker compose' nor 'docker-compose' is available"
fi

docker info >/dev/null 2>&1 || fail "cannot reach the docker daemon (add your user to the 'docker' group, then re-login)"
[ -f docker-compose.yml ] || fail "docker-compose.yml is missing"
[ -f .env ] || fail ".env is missing (copy .env.example to .env and fill it)"

set -a; . ./.env; set +a
: "${POSTGRES_USER:?POSTGRES_USER is not set in .env}"
: "${POSTGRES_DB:?POSTGRES_DB is not set in .env}"

psql_do() {
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1"
}

wait_ready() {
  for _ in $(seq 1 30); do
    if compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  fail "postgres did not become ready within 30s"
}

echo "1/3 starting postgres and connecting with the .env credentials"
compose up -d postgres >/dev/null 2>&1 || fail "'compose up -d postgres' failed"
wait_ready
psql_do "SELECT 1;" >/dev/null || fail "psql could not connect with the .env credentials"

echo "2/3 writing a row and reading it back"
MARKER="ticket-01-$(date +%s)"
psql_do "CREATE TABLE IF NOT EXISTS persistence_check (marker text primary key);" >/dev/null
psql_do "INSERT INTO persistence_check (marker) VALUES ('$MARKER');" >/dev/null
[ "$(psql_do "SELECT marker FROM persistence_check WHERE marker = '$MARKER';")" = "$MARKER" ] \
  || fail "the row was not readable back"

echo "3/3 restarting the stack and checking the row survived"
compose down >/dev/null 2>&1 || fail "'compose down' failed"
compose up -d postgres >/dev/null 2>&1 || fail "'compose up -d postgres' failed after down"
wait_ready
[ "$(psql_do "SELECT marker FROM persistence_check WHERE marker = '$MARKER';")" = "$MARKER" ] \
  || fail "the row did not survive down/up - the named volume is not persisting data"

psql_do "DROP TABLE persistence_check;" >/dev/null
echo "PASS: postgres connects with the .env credentials and persists data across a restart"
