# Proctoring — Monorepo

Plataforma self-hosted de proctoring **L2.5**. Este repo contiene la **fundacion**
(scaffolding + stack local) creada por el change **C-04 `foundation-setup`**.

> Contexto de dominio y reglas duras: ver [AGENTS.md](AGENTS.md) /
> [CLAUDE.md](CLAUDE.md) y `knowledge-base/`. Roadmap: [CHANGES.md](CHANGES.md).

## Quickstart — clonar y testear como en producción

Espeja el deploy real (Railway = backend slim + Postgres; Vercel = frontend), con
**login JWT real (sin modo demo)** y los usuarios de prueba creados **siempre**.

**Requisitos:** Docker Desktop corriendo + Node 18+.

```bash
# 1. Backend + DB (build + migra + seed + uvicorn en http://localhost:8000)
./scripts/dev-up.ps1          # Windows (PowerShell)
./scripts/dev-up.sh           # macOS / Linux

# 2. Frontend (otra terminal) -> http://localhost:5173
cd frontend && npm install && npm run dev
```

El frontend usa `frontend/.env.development` (commiteado): apunta a
`http://localhost:8000/api/v1`, con `VITE_AUTH_PROVIDER=jwt` y demo/bypass
apagados. Para frenar: `./scripts/dev-down.ps1` (agregá `-v` para resetear la DB).

**Usuarios de prueba (seed idempotente, estilo producción):**

| Rol | Usuario o email | Password |
|---|---|---|
| Administrador | `ADMIN-001` · `admin@activeexam.local` | `Admin123` |
| Estudiante | `EST-001` · `estudiante@activeexam.local` | `Estudiante123` |
| Proctor | `PROC-001` · `proctor@activeexam.local` | `Proctor123` |

> Las credenciales y secretos de `docker-compose.dev.yml` son **dev-only** (DB
> local, JWT y Fernet de juguete). En producción se inyectan por el dashboard de
> Railway. No son secretos reales.

## Arbol canonico del repositorio (cierra la suposicion SU-07)

C-04 fija esta estructura como **convencion del proyecto** (Clean/Hexagonal
pragmatica en backend, por features en frontend, infra aparte):

```
proctoring/
├── backend/
│   ├── app/
│   │   ├── domain/            # entidades/reglas/scoring — PURO (sin framework)
│   │   ├── application/       # casos de uso
│   │   ├── infrastructure/    # adaptadores detras de puertos
│   │   │   ├── persistence/   #   PostgreSQL/TimescaleDB (SQLAlchemy)
│   │   │   ├── messaging/     #   cola/transporte — pieza decidida por C-03 (default A4)
│   │   │   ├── storage/       #   MinIO/S3
│   │   │   └── auth/          #   Keycloak (auth real en C-06)
│   │   ├── presentation/      # routers FastAPI /api/v1 + WS/SSE + healthchecks
│   │   ├── workers/           # re-inferencia, firma, reportes (andamio)
│   │   ├── observability/     # logging JSON + OTel + metricas Prometheus
│   │   ├── config.py          # carga twelve-factor de config
│   │   └── main.py            # app factory (FastAPI mono-hilo)
│   ├── migrations/            # Alembic (destructivas en dos pasos); 001 = TimescaleDB
│   ├── tests/                 # smoke de arranque + config + conectividad
│   ├── Dockerfile            # imagen mono-hilo (sin secretos)
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/
│   └── src/                   # features|shared|vision|proctoring|transport|pages
├── infra/
│   ├── docker-compose/        # stack local (Postgres/TimescaleDB, MinIO, Keycloak, Nginx, observabilidad)
│   ├── nginx/                 # terminacion TLS 1.3 + pooling por healthcheck
│   └── observability/         # Prometheus, Loki, Tempo, Grafana
├── .env.example              # contrato de env vars (secretos via Vault/tmpfs en prod)
├── docs/  ·  knowledge-base/  ·  openspec/
```

### Convenciones fijadas aqui

- **Dominio puro**: `backend/app/domain/` NO importa FastAPI/SQLAlchemy ni
  adaptadores de `infrastructure`. Lo verifica `tests/test_architecture.py`.
- **Mensajeria swappable (C-03)**: el adaptador vive detras del puerto
  `infrastructure/messaging/port.py`. Default = Postgres-como-cola (A4, DD-19).
  No se levanta Redis/RabbitMQ por defecto en el compose.
- **Twelve-factor**: toda la config por entorno (`config.py`); secretos via
  Vault/tmpfs, nunca en la imagen. La app falla explicito si falta config.
- **FastAPI mono-hilo** (DD-10): 1 instancia = 1 proceso uvicorn; escalado
  horizontal detras de Nginx.
- **Migraciones**: destructivas en dos pasos (expand/contract). Ver
  `backend/migrations/README.md`.

## Auth provider JWT propio (C-55)

### Providers disponibles

El auth se selecciona con `VITE_AUTH_PROVIDER` (frontend) y `AUTH_PROVIDER` (backend):

| `VITE_AUTH_PROVIDER` | Comportamiento |
|---|---|
| `jwt` (default) | Formulario de login propio; llama `POST /api/v1/auth/login` |
| `keycloak` | Redirect OIDC PKCE a Keycloak (C-06, conservado) |
| `demo` | Selector de rol sin red (Vercel demo) |

### Seed de usuarios de prueba (local/staging)

```bash
cd backend
pip install ".[dev]"                       # incluye passlib[bcrypt]

# Exportar las vars requeridas (ejemplo local)
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/proctoring
export JWT_OWN_SECRET=un-secreto-largo-de-256-bits-o-mas
export JWT_AUDIENCE=proctoring-api
export KEYCLOAK_ISSUER=http://localhost:8080/realms/proctoring
export KEYCLOAK_JWKS_URL=http://localhost:8080/realms/proctoring/protocol/openid-connect/certs
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export STORAGE_ENDPOINT=http://localhost:9000
export STORAGE_ACCESS_KEY=minioadmin
export STORAGE_SECRET_KEY=minioadmin
export STORAGE_BUCKET_EVIDENCE=evidence

# Passwords para los usuarios seed (min 8 chars)
export SEED_ESTUDIANTE_PASSWORD=Estudiante123
export SEED_PROCTOR_PASSWORD=Proctor123
export SEED_ADMIN_PASSWORD=Admin1234

# Aplicar migración C-55 primero
alembic upgrade head

# Correr el seed (idempotente)
python scripts/seed_users.py
```

**Credenciales seed para probar el login:**

| Rol | username / email | password (env) |
|---|---|---|
| `estudiante` | `EST-001` o `estudiante@activeexam.local` | `$SEED_ESTUDIANTE_PASSWORD` |
| `proctor` | `PROC-001` o `proctor@activeexam.local` | `$SEED_PROCTOR_PASSWORD` |
| `admin_sistema` | `ADMIN-001` o `admin@activeexam.local` | `$SEED_ADMIN_PASSWORD` |

**Endpoint de login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ADMIN-001","password":"Admin123"}'
```

### Nota de deuda técnica — MFA (proctor/admin_sistema)

El provider JWT propio emite `mfa_satisfecho=false` para todos los roles (no hay
TOTP en este change). Los roles `proctor` y `admin_sistema` **no son bloqueados**
en MVP — el frontend muestra un warning visible. La implementación de MFA propio
(TOTP) es un **change futuro documentado** en el design.md de C-55.

## Criterio de salida de C-04 (desbloquea C-05)

La fundacion esta lista cuando el stack es **arrancable + observable + con
conectividad verificada**:

1. `docker compose up` levanta Postgres/TimescaleDB, MinIO, Keycloak, Nginx
   (TLS 1.3) y la observabilidad (Prometheus/Loki/Tempo/Grafana), todos healthy.
2. La migracion 001 deja la extension TimescaleDB lista (esquema vacio).
3. Los smoke tests pasan: arranque + healthchecks (sin stack) y conectividad
   DB/storage/IdP (con stack).

## Comandos de verificacion (NO ejecutados por el agente — "never build")

> Estos comandos corren en Docker/Linux. El scaffolding queda coherente; el
> usuario los ejecuta cuando quiera levantar el stack.

```bash
# 1. Preparar config local
cp .env.example .env                       # editar placeholders si hace falta
# generar cert TLS local (ver infra/nginx/tls/README.md)

# 2. Tests que NO requieren stack (config, app factory, arquitectura, smoke)
cd backend
pip install ".[dev]"
pytest                                     # corre todo MENOS los requires_stack

# 3. Levantar el stack
cd ../infra/docker-compose
docker compose up -d                       # Postgres, MinIO, Keycloak, Nginx, observabilidad
docker compose ps                          # todos healthy

# 4. Migracion 001 (extension TimescaleDB)
cd ../../backend
alembic upgrade head                       # habilita TimescaleDB
alembic downgrade base                     # verifica reversibilidad (esquema vacio)
alembic upgrade head

# 5. Tests de conectividad (requieren el stack arriba)
RUN_STACK_TESTS=1 pytest tests/test_connectivity.py

# 6. Observabilidad
# Grafana: http://localhost:3000  (Prometheus + Loki + Tempo ya provisionados)
```
