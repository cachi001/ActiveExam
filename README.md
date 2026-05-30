# Proctoring — Monorepo

Plataforma self-hosted de proctoring **L2.5**. Este repo contiene la **fundacion**
(scaffolding + stack local) creada por el change **C-04 `foundation-setup`**.

> Contexto de dominio y reglas duras: ver [AGENTS.md](AGENTS.md) /
> [CLAUDE.md](CLAUDE.md) y `knowledge-base/`. Roadmap: [CHANGES.md](CHANGES.md).

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
