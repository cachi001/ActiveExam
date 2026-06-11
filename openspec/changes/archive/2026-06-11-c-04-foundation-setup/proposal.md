# Proposal — C-04 `foundation-setup`

> **Naturaleza del change**: bootstrap de infraestructura y scaffolding del monorepo, governance **MEDIO**. Es el **primer código de producción** del proyecto: el esqueleto sobre el que se levantan todos los changes de dominio (C-05…C-16). NO implementa lógica de negocio — establece la estructura por capas, el stack local reproducible y el andamiaje de migraciones, config y observabilidad. **Depende del veredicto de C-03**: la pieza de cola/transporte/backplane que levante el `docker-compose` es la que C-03 haya decidido por métrica, no una asumida.

## Why

El proyecto Proctoring (React + FastAPI/ASGI + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3 + Vault + Prometheus/Loki/Tempo/Grafana) no tiene todavía un esqueleto de repositorio ni un entorno local arrancable. Antes de escribir una sola entidad de dominio (C-05), un endpoint de auth (C-06) o cualquier feature, hace falta una **fundación coherente**:

- Una estructura por capas **Clean/Hexagonal pragmática** (DD — `08` §Patrones) que haga testeable el dominio y sustituible la infraestructura (Postgres, storage, IdP, cola). Sin esta separación desde el día uno, el dominio se contamina de detalles de framework y la deuda es irreversible.
- Un stack local **reproducible** vía Docker Compose (DD-11) que levante exactamente las piezas del MVP, para que cualquier integrante arranque el sistema sin "en mi máquina funciona".
- **Observabilidad de primera clase desde Fase 0** (DD-12): "una función no observable no está lista". La instrumentación se monta **antes** de que exista qué observar, no como fase posterior.
- Config **twelve-factor** (DD-11): toda configuración por entorno, secretos por Vault/tmpfs, logs a stdout, sin estado local — para que la migración a Kubernetes sea evolución operacional y no rediseño.
- Migraciones **Alembic** con la convención de **destructivas en dos pasos** desde la migración 001, para que el esquema evolucione sin downtime ni pérdida.

Este change transforma "tenemos un stack decidido" en "tenemos un repo arrancable e instrumentado donde C-05…C-16 se construyen". Es el andamio; sin él, todo lo demás flota.

## What Changes

- **Monorepo scaffolding**: árbol `backend/` (`app/domain`, `app/application`, `app/infrastructure` — con `persistence/messaging/storage/auth` —, `app/presentation`, `app/workers`, `app/observability`, `migrations/`, `tests/`), `frontend/src/` (`features/shared/vision/proctoring/transport/pages`) e `infra/` (`docker-compose/`, `nginx/`, `observability/`), siguiendo `08` §Estructura de directorios (SU-07: el árbol es inferido y se fija aquí como convención).
- **docker-compose inicial** que levanta: **PostgreSQL + extensión TimescaleDB**, **MinIO/S3**, **Keycloak**, **Nginx con TLS 1.3** como reverse proxy/terminación TLS, y la **base de observabilidad** (Prometheus, Loki, Tempo, Grafana — DD-12). La pieza de **cola/transporte/backplane se parametriza según el ganador de C-03** (no se hardcodea Redis ni RabbitMQ por defecto).
- **Alembic** configurado con la convención de **migraciones destructivas en dos pasos** (expand/contract). **Migración 001**: habilita la extensión TimescaleDB y deja el esquema vacío (sin tablas de dominio — esas llegan en C-05).
- **Config twelve-factor**: `.env` con las variables del stack (`DATABASE_URL`, `STORAGE_*`, `KEYCLOAK_*`, `VAULT_*`, `OTEL_*` — ver `08` §Variables de entorno) cargadas por entorno; **secretos inyectados vía Vault en tmpfs efímero**, nunca hardcodeados en imágenes (DD — `08` §Seguridad §Gestión de secretos).
- **FastAPI mono-hilo escalado horizontalmente** (DD-10): una instancia = un proceso uvicorn de un hilo asíncrono, escalable detrás de Nginx (1 instancia ≈ 1 pod). Healthchecks expuestos para que Nginx saque instancias caídas del pool.
- **Smoke tests de arranque**: el stack levanta, los healthchecks responden, y hay conectividad verificada contra DB, storage e IdP.

## Capabilities

> Estas capabilities modelan la **fundación de infraestructura y scaffolding**: estructura del repo, stack local reproducible, andamiaje de migraciones/config y observabilidad base. Su Done es "el stack arranca, se conecta y se observa", no una feature de negocio.

### New Capabilities

- `monorepo-scaffolding`: el árbol del repositorio por capas (backend Clean/Hexagonal, frontend por features, infra) que hace testeable el dominio y sustituible la infraestructura.
- `local-stack-compose`: el `docker-compose` que levanta el stack del MVP (Postgres/TimescaleDB, MinIO/S3, Keycloak, Nginx TLS 1.3) con la pieza de cola/transporte/backplane según el ganador de C-03.
- `db-migrations-baseline`: Alembic con la convención destructiva-en-dos-pasos y la migración 001 (extensión TimescaleDB + esquema vacío).
- `twelve-factor-config`: la carga de configuración por entorno y la inyección de secretos vía Vault/tmpfs, con FastAPI mono-hilo escalado horizontal (DD-10/DD-11).
- `observability-baseline`: la base de observabilidad (Prometheus/Loki/Tempo/Grafana) montada desde Fase 0 (DD-12), con healthchecks y smoke tests de arranque/conectividad.

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. -->

(Ninguna — este change crea la fundación; no modifica requisitos de capacidades existentes.)

## Impact

- **Dependencias entrantes**: **C-03** (el veredicto por concern decide qué cola/transporte/backplane levanta el compose). Hasta que C-03 cierre su gate, este change no sabe qué pieza de mensajería instanciar.
- **Bloquea**: **C-05** (modelos base — necesita el repo, Alembic y la extensión TimescaleDB ya habilitada para crear la hypertable y las tablas) y, por transitividad, todo lo de dominio (C-06 auth, C-10 ingesta, etc.).
- **Decisiones que consume** (de C-03): qué cola implementa la capa `infrastructure/messaging`, qué transporte expone `presentation`, qué backplane usan los workers/fan-out.
- **Decisiones que produce** (consumidas downstream): la estructura de carpetas canónica (cierra SU-07), la convención de migraciones, el contrato de variables de entorno y el baseline de observabilidad que todo change instrumenta.
- **Actores/sistemas afectados**: equipo de desarrollo (arranca el stack local), administrador del sistema (opera el compose, los healthchecks y la observabilidad). No afecta usuarios finales: no hay dominio todavía.
- **Riesgo principal**: parametrizar mal la pieza de C-03 (levantar Redis/RabbitMQ "por las dudas" violando DD-19) o acoplar el dominio a la infraestructura desde el scaffolding. Mitigado por la separación por capas y por consumir el veredicto de C-03 explícitamente.
