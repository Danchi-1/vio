#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root after setting DATABASE_URL in backend/.env or env.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [ -f backend/.env ]; then
  set -a
  # shellcheck disable=SC1091
  source backend/.env
  set +a
fi

: "${DATABASE_URL:?DATABASE_URL must be set (e.g. postgresql://vio:pass@127.0.0.1:5432/vio)}"

# psql expects postgresql:// (without +asyncpg)
PSQL_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"

psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f database/seed.sql
psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f database/smoke_test.sql

if [ -x .venv/bin/vio-synopsis-seed ]; then
  .venv/bin/vio-synopsis-seed
fi
