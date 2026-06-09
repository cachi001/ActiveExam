#!/usr/bin/env bash
# dev-down.sh — Frena el stack de desarrollo. Pasa -v para borrar la DB (volumen).
#   ./scripts/dev-down.sh        # frena contenedores, conserva datos
#   ./scripts/dev-down.sh -v     # frena y BORRA el volumen de Postgres (reset total)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$REPO_ROOT/infra/docker-compose/docker-compose.dev.yml"

docker compose -f "$COMPOSE" down "$@"
