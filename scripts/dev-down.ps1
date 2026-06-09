# dev-down.ps1 — Frena el stack de desarrollo. Agrega -v para borrar la DB (volumen).
#   ./scripts/dev-down.ps1        # frena contenedores, conserva datos
#   ./scripts/dev-down.ps1 -v     # frena y BORRA el volumen de Postgres (reset total)
param([switch]$v)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repoRoot "infra/docker-compose/docker-compose.dev.yml"

if ($v) {
  docker compose -f $compose down -v
} else {
  docker compose -f $compose down
}
