#!/usr/bin/env bash
# dev-up.sh — Levanta el stack de desarrollo (DB + backend slim) que espeja prod.
#
# Requisitos: Docker corriendo.
# Uso (desde la raiz del repo):
#   ./scripts/dev-up.sh
#
# Esto construye y levanta Postgres + el backend slim (migra + seed de usuarios +
# uvicorn) en http://localhost:8000. Los usuarios de prueba se crean SIEMPRE:
#   Admin:      ADMIN-001  / Admin123        (admin@activeexam.local)
#   Estudiante: EST-001    / Estudiante123   (estudiante@activeexam.local)
#   Proctor:    PROC-001   / Proctor123      (proctor@activeexam.local)
#
# El FRONTEND va aparte, en otra terminal:
#   cd frontend && npm install && npm run dev   ->  http://localhost:5173
#
# Para frenar el stack:  ./scripts/dev-down.sh  (o Ctrl+C y luego docker compose down)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$REPO_ROOT/infra/docker-compose/docker-compose.dev.yml"

echo ">>> Verificando que Docker este corriendo..."
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker no responde. Arranca Docker y reintenta." >&2
  exit 1
fi

echo ">>> Levantando DB + backend slim (build + migrar + seed + uvicorn)..."
echo "    Backend:  http://localhost:8000/api/v1"
echo "    Frontend: cd frontend && npm run dev  (otra terminal)"

docker compose -f "$COMPOSE" up --build
