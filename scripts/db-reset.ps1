# db-reset.ps1 — Resetea la DB de desarrollo a la SEED BASE, EN VIVO (sin bajar el stack).
#
# Hace, contra los contenedores que YA estan corriendo (dev-up):
#   1) DROP SCHEMA public CASCADE; CREATE SCHEMA public;   (borra TODO, incl. alembic_version)
#   2) alembic -c alembic.ini upgrade slim@head            (re-crea el schema desde cero)
#   3) python scripts/seed_users.py --slim                 (re-crea ADMIN-001 / EST-001 / PROC-001)
#
# Resultado: la DB queda identica a un arranque limpio, en segundos y sin rebuild.
#
# Requisitos: el stack dev tiene que estar levantado (./scripts/dev-up.ps1).
# Uso (desde la raiz del repo):
#   ./scripts/db-reset.ps1           # pide confirmacion (borra datos)
#   ./scripts/db-reset.ps1 -Force    # sin confirmacion (para scripts/CI)
#
# Para un reset TOTAL que ademas reconstruye la imagen y borra el volumen:
#   ./scripts/dev-down.ps1 -v ; ./scripts/dev-up.ps1
param([switch]$Force)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repoRoot "infra/docker-compose/docker-compose.dev.yml"

# El stack tiene que estar corriendo: necesitamos los contenedores postgres + backend vivos.
Write-Host ">>> Verificando que el stack dev este corriendo..." -ForegroundColor Cyan
$running = docker compose -f $compose ps --services --status running
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Docker no responde. Abri Docker Desktop y reintenta." -ForegroundColor Red
  exit 1
}
if (($running -notcontains "postgres") -or ($running -notcontains "backend")) {
  Write-Host "ERROR: el stack no esta levantado. Corre primero:  ./scripts/dev-up.ps1" -ForegroundColor Red
  exit 1
}

if (-not $Force) {
  Write-Host ""
  Write-Host "  Esto BORRA todos los datos de la DB de desarrollo (proctoring)" -ForegroundColor Yellow
  Write-Host "  y la deja en la seed base (ADMIN-001 / EST-001 / PROC-001)." -ForegroundColor Yellow
  $resp = Read-Host "  Escribi 'reset' para continuar"
  if ($resp -ne "reset") {
    Write-Host ">>> Cancelado. No se toco nada." -ForegroundColor DarkGray
    exit 0
  }
}

Write-Host ">>> [1/3] DROP + CREATE SCHEMA public (borra todo, incl. alembic_version)..." -ForegroundColor Cyan
docker compose -f $compose exec -T postgres `
  psql -U proctoring -d proctoring -v ON_ERROR_STOP=1 `
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

Write-Host ">>> [2/3] migrando DB (alembic slim@head)..." -ForegroundColor Cyan
docker compose -f $compose exec -T backend alembic -c alembic.ini upgrade slim@head

Write-Host ">>> [3/3] seed de usuarios (idempotente)..." -ForegroundColor Cyan
docker compose -f $compose exec -T backend python scripts/seed_users.py --slim

Write-Host ""
Write-Host ">>> DB reseteada a la seed base. Usuarios listos:" -ForegroundColor Green
Write-Host "    Admin:      ADMIN-001  / Admin123" -ForegroundColor DarkGray
Write-Host "    Estudiante: EST-001    / Estudiante123" -ForegroundColor DarkGray
Write-Host "    Proctor:    PROC-001   / Proctor123" -ForegroundColor DarkGray
