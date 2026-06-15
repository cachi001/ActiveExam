#!/usr/bin/env bash
# Sincroniza app/ y tests/ al contenedor backend (sin mount) y corre pytest
# contra el Postgres real del compose (postgres:5432). Uso:
#   bash scripts/run_tests_in_container.sh [args de pytest...]
set -euo pipefail
C=activeexam-dev-backend-1
HERE="$(cd "$(dirname "$0")/.." && pwd)"
docker cp "$HERE/app" "$C:/app/" >/dev/null
docker cp "$HERE/tests" "$C:/app/" >/dev/null
docker cp "$HERE/migrations" "$C:/app/" >/dev/null
docker exec \
  -e ENVIRONMENT=local \
  -e DATABASE_URL="postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring" \
  "$C" sh -c "cd /app && python -m pytest $*"
