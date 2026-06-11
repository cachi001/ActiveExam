#!/usr/bin/env bash
# db-reset.sh — Resetea la DB de desarrollo a la SEED BASE, EN VIVO (sin bajar el stack).
#
# Hace, contra los contenedores que YA estan corriendo (dev-up):
#   1) DROP SCHEMA public CASCADE; CREATE SCHEMA public;   (borra TODO, incl. alembic_version)
#   2) alembic -c alembic.ini upgrade slim@head            (re-crea el schema desde cero)
#   3) python scripts/seed_users.py --slim                 (re-crea ADMIN-001 / EST-001 / PROC-001)
#
# Resultado: la DB queda identica a un arranque limpio, en segundos y sin rebuild.
#
# Requisitos: el stack dev tiene que estar levantado (./scripts/dev-up.sh).
# Uso (desde la raiz del repo):
#   ./scripts/db-reset.sh          # pide confirmacion (borra datos)
#   ./scripts/db-reset.sh -y       # sin confirmacion (para scripts/CI)
#
# Para un reset TOTAL que ademas reconstruye la imagen y borra el volumen:
#   ./scripts/dev-down.sh -v && ./scripts/dev-up.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$REPO_ROOT/infra/docker-compose/docker-compose.dev.yml"

FORCE=0
if [[ "${1:-}" == "-y" || "${1:-}" == "--yes" ]]; then FORCE=1; fi

# El stack tiene que estar corriendo: necesitamos los contenedores postgres + backend vivos.
echo ">>> Verificando que el stack dev este corriendo..."
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker no responde. Arranca Docker y reintenta." >&2
  exit 1
fi
RUNNING="$(docker compose -f "$COMPOSE" ps --services --status running)"
if ! grep -qx "postgres" <<<"$RUNNING" || ! grep -qx "backend" <<<"$RUNNING"; then
  echo "ERROR: el stack no esta levantado. Corre primero:  ./scripts/dev-up.sh" >&2
  exit 1
fi

if [[ "$FORCE" -ne 1 ]]; then
  echo ""
  echo "  Esto BORRA todos los datos de la DB de desarrollo (proctoring)"
  echo "  y la deja en la seed base (ADMIN-001 / EST-001 / PROC-001)."
  read -r -p "  Escribi 'reset' para continuar: " resp
  if [[ "$resp" != "reset" ]]; then
    echo ">>> Cancelado. No se toco nada."
    exit 0
  fi
fi

echo ">>> [1/3] DROP + CREATE SCHEMA public (borra todo, incl. alembic_version)..."
docker compose -f "$COMPOSE" exec -T postgres \
  psql -U proctoring -d proctoring -v ON_ERROR_STOP=1 \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo ">>> [2/3] migrando DB (alembic slim@head)..."
docker compose -f "$COMPOSE" exec -T backend alembic -c alembic.ini upgrade slim@head

echo ">>> [3/3] seed de usuarios (idempotente)..."
docker compose -f "$COMPOSE" exec -T backend python scripts/seed_users.py --slim

echo ""
echo ">>> DB reseteada a la seed base. Usuarios listos:"
echo "    Admin:      ADMIN-001  / Admin123"
echo "    Estudiante: EST-001    / Estudiante123"
echo "    Proctor:    PROC-001   / Proctor123"
