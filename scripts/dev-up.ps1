# dev-up.ps1 — Levanta el stack de desarrollo (DB + backend slim) que espeja prod.
#
# Requisitos: Docker Desktop corriendo.
# Uso (desde la raiz del repo):
#   ./scripts/dev-up.ps1
#
# Esto construye y levanta Postgres + el backend slim (migra + seed de usuarios +
# uvicorn) en http://localhost:8000. Los usuarios de prueba se crean SIEMPRE:
#   Admin:      ADMIN-001  / Admin123        (admin@activeexam.local)
#   Estudiante: EST-001    / Estudiante123   (estudiante@activeexam.local)
#   Proctor:    PROC-001   / Proctor123      (proctor@activeexam.local)
#
# El FRONTEND va aparte, en otra terminal:
#   cd frontend; npm install; npm run dev   ->  http://localhost:5173
#
# Para frenar el stack:  ./scripts/dev-down.ps1  (o Ctrl+C y luego docker compose down)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repoRoot "infra/docker-compose/docker-compose.dev.yml"

Write-Host ">>> Verificando que Docker este corriendo..." -ForegroundColor Cyan
docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Docker no responde. Abri Docker Desktop y reintenta." -ForegroundColor Red
  exit 1
}

Write-Host ">>> Levantando DB + backend slim (build + migrar + seed + uvicorn)..." -ForegroundColor Cyan
Write-Host "    Backend:  http://localhost:8000/api/v1" -ForegroundColor DarkGray
Write-Host "    Frontend: cd frontend; npm run dev  (otra terminal)" -ForegroundColor DarkGray

docker compose -f $compose up --build
