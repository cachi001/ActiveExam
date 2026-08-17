#!/usr/bin/env bash
# Sincroniza app/ y tests/ al contenedor backend (sin mount) y corre pytest
# contra una base de test SEPARADA (proctoring_test), NUNCA contra la base de la
# app (proctoring). Esto evita que los teardowns de los tests (DROP/TRUNCATE/DELETE)
# corrompan los datos sembrados del runtime. Uso:
#   bash scripts/run_tests_in_container.sh [args de pytest...]
set -euo pipefail
C=activeexam-dev-backend-1
HERE="$(cd "$(dirname "$0")/.." && pwd)"

# Base de test dedicada (aislada de la base de la app).
TEST_DB="proctoring_test"
TEST_URL="postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/${TEST_DB}"

docker cp "$HERE/app" "$C:/app/" >/dev/null
docker cp "$HERE/tests" "$C:/app/" >/dev/null
docker cp "$HERE/migrations" "$C:/app/" >/dev/null

# Self-healing: crea la base de test si no existe y la migra al head (siembra todo
# vía migraciones). Idempotente — si ya existe, el CREATE falla en silencio y el
# upgrade es no-op.
docker exec "$C" sh -c "PGPASSWORD=dev-only-change-me psql -h postgres -U proctoring -d proctoring -tc \"SELECT 1 FROM pg_database WHERE datname='${TEST_DB}'\" | grep -q 1 || PGPASSWORD=dev-only-change-me psql -h postgres -U proctoring -d proctoring -c \"CREATE DATABASE ${TEST_DB}\"" 2>/dev/null || true
docker exec -e DATABASE_URL="$TEST_URL" "$C" sh -c "cd /app && alembic -c alembic.ini upgrade activeexam@head" >/dev/null 2>&1 || true

docker exec \
  -e ENVIRONMENT=local \
  -e DATABASE_URL="$TEST_URL" \
  "$C" sh -c "cd /app && python -m pytest $*"
