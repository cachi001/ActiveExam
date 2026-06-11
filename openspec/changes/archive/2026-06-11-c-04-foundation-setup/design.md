# Design — C-04 `foundation-setup`

> Design técnico de la **fundación de infraestructura**: estructura por capas, stack local en Compose, andamiaje de migraciones/config y observabilidad base. Establece convenciones que C-05…C-16 heredan. No implementa dominio.

## Context

Stack del proyecto (de la KB): React + FastAPI (ASGI/uvicorn, Pydantic, SQLAlchemy) + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3 + Vault + observabilidad (Prometheus/Loki/Tempo/Grafana). Arquitectura backend **Clean/Hexagonal pragmática** (`08` §Patrones) y **twelve-factor** (DD-11). NFR de capacidad endurecido (SU-06, `14`): **1.000 concurrentes sostenido / ~2.100 pico / ~5.000 inserts/s** — este change no lo prueba (eso fue C-03), pero la fundación debe soportar escalado horizontal (DD-10) para alcanzarlo.

**Constraints**:
- La estructura de directorios y las env vars son **inferidas** (SU-07): este change las **fija como convención** del repo.
- La pieza de cola/transporte/backplane **NO está decidida por este change**: la levanta el compose según **el ganador de C-03** (hipótesis A4 = Postgres-cola + SSE + `LISTEN/NOTIFY`, pero no se asume).
- **Secretos por Vault/tmpfs** (`08` §Gestión de secretos): nunca hardcodeados en imágenes Docker.
- **TLS 1.3 en todo**, incluida la comunicación interna entre componentes (`08` §Seguridad).
- FastAPI **mono-hilo** (DD-10): un proceso uvicorn de un hilo asíncrono por instancia, NO multi-worker dentro de la instancia.

## Goals / Non-Goals

**Goals:**
- Fijar el árbol del monorepo por capas (cierra SU-07) con el dominio puro aislado de la infraestructura.
- Levantar un stack local reproducible (Postgres/TimescaleDB, MinIO/S3, Keycloak, Nginx TLS 1.3) vía Docker Compose (DD-11).
- Montar la observabilidad base (Prometheus/Loki/Tempo/Grafana) desde Fase 0 (DD-12).
- Configurar Alembic con la convención destructiva-en-dos-pasos y dejar la migración 001 (extensión TimescaleDB + esquema vacío).
- Cargar config twelve-factor por entorno con secretos vía Vault/tmpfs.
- Verificar arranque y conectividad (smoke tests, healthchecks) contra DB, storage e IdP.

**Non-Goals:**
- NO crear entidades de dominio ni tablas de negocio (eso es C-05).
- NO implementar auth/RBAC (eso es C-06) — solo dejar Keycloak corriendo y el contrato de env vars `KEYCLOAK_*`.
- NO decidir la pieza de cola/transporte/backplane (la decidió C-03); aquí solo se parametriza.
- NO dimensionar producción ni K8s (Compose primero, K8s es evolución operacional, DD-11/`14`).
- NO implementar la cadena de custodia, el bucket WORM ni la firma de evidencia (changes de dominio posteriores).

## Decisions

### D1 — Estructura por capas Clean/Hexagonal pragmática, dominio puro aislado
**Decisión**: `backend/app/` se parte en `domain` (entidades, reglas, scoring — puro, sin imports de framework), `application` (casos de uso), `infrastructure` (adaptadores: `persistence`, `messaging`, `storage`, `auth`), `presentation` (routers FastAPI + handlers WS/SSE), `workers` y `observability`. Frontend por `features` + `shared/vision/proctoring/transport/pages`.
**Por qué**: testabilidad del dominio y **sustituibilidad de infraestructura** (Postgres, storage, IdP, cola) por puertos/adaptadores (`08` §Patrones). Permite que C-03 cambie la pieza de mensajería sin tocar dominio.
**Alternativa considerada**: estructura por tipo técnico (controllers/services/models) → acopla dominio a framework, no escala a Hexagonal.

### D2 — La pieza de cola/transporte/backplane la decide C-03, no este change
**Decisión**: el `docker-compose` parametriza la pieza de mensajería; el adaptador en `infrastructure/messaging` se selecciona por config según **el ganador de C-03**. Por omisión la hipótesis es A4 (Postgres-cola), pero no se hardcodea Redis/RabbitMQ.
**Por qué**: DD-19 — no agregar complejidad sin métrica. Levantar Redis/RabbitMQ "por las dudas" violaría el principio rector y el gate de C-03.
**Alternativa considerada**: levantar todo el stack del SAD original → over-provisioning prohibido por DD-19.

### D3 — Docker Compose primero, twelve-factor para migración trivial a K8s
**Decisión**: arrancar con Docker Compose (DD-11), código twelve-factor desde el día uno (config por entorno, logs a stdout, sin estado local).
**Por qué**: time-to-market del piloto; la migración a Kubernetes es evolución operacional, no rediseño (`14` §Topología). FastAPI mono-hilo (DD-10) ⇒ 1 instancia ≈ 1 pod.
**Alternativa considerada**: K8s desde el inicio → sobrecarga prematura (DD-11).

### D4 — Migración 001 = extensión TimescaleDB + esquema vacío; destructivas en dos pasos
**Decisión**: la migración 001 solo habilita `CREATE EXTENSION timescaledb` y deja el esquema sin tablas de dominio. La convención de migraciones es **expand/contract (destructivas en dos pasos)** desde el inicio.
**Por qué**: C-05 crea la hypertable de eventos, que requiere la extensión ya presente. La convención de dos pasos evita downtime y pérdida en cambios destructivos futuros.
**Alternativa considerada**: crear tablas de dominio aquí → invade el scope de C-05 y acopla migraciones a entidades aún no diseñadas.

### D5 — Secretos por Vault/tmpfs, TLS 1.3 incluso interno
**Decisión**: las env vars sensibles (`DATABASE_URL`, `STORAGE_*KEY`, `VAULT_*`, claves) se inyectan vía Vault en tmpfs efímero; las no sensibles van por `.env`. Nginx termina TLS 1.3 y la comunicación interna entre componentes usa TLS.
**Por qué**: `08` §Seguridad — secretos nunca en imágenes; defensa en profundidad; cumplimiento de la cadena de custodia futura depende de no filtrar claves.
**Alternativa considerada**: secretos en `.env` plano en la imagen → riesgo inaceptable de filtración.

### D6 — Observabilidad montada ANTES de que exista dominio (DD-12)
**Decisión**: Prometheus, Loki, Tempo y Grafana se levantan en el compose desde este change, con scraping de los healthchecks de FastAPI y exportador OTLP (`OTEL_EXPORTER_OTLP_ENDPOINT`) configurado.
**Por qué**: "una función no observable no está lista" (DD-12). Cada change posterior instrumenta sobre esta base, no la inventa.
**Alternativa considerada**: observabilidad como fase posterior → contradice DD-12 y deja Fase 1 ciega.

## Arquitectura de la fundación

```
proctoring/
├── backend/app/
│   ├── domain/          # puro (sin tablas todavía)
│   ├── application/      # casos de uso (vacío)
│   ├── infrastructure/  # persistence | messaging(←ganador C-03) | storage | auth
│   ├── presentation/     # routers FastAPI + healthchecks
│   ├── workers/          # andamio (vacío)
│   └── observability/    # exporters Prometheus/OTLP
│   ├── migrations/       # Alembic: 001 = extensión TimescaleDB + esquema vacío
│   └── tests/            # smoke de arranque + conectividad
├── frontend/src/         # features|shared|vision|proctoring|transport|pages (andamio)
└── infra/
    ├── docker-compose/   # Postgres/TimescaleDB, MinIO/S3, Keycloak, Nginx TLS 1.3, observabilidad
    ├── nginx/            # terminación TLS 1.3 + healthchecks
    └── observability/    # Prometheus, Loki, Tempo, Grafana
```

## Variables de entorno (contrato fijado aquí)

| Variable | Origen del valor | Sensible |
|----------|------------------|----------|
| `DATABASE_URL` | Vault/tmpfs | Y |
| `STORAGE_ENDPOINT` / `STORAGE_BUCKET_*` | `.env` | N |
| `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | Vault/tmpfs | Y |
| `KEYCLOAK_ISSUER` / `KEYCLOAK_JWKS_URL` / `JWT_AUDIENCE` | `.env` | N |
| `VAULT_ADDR` / `VAULT_TOKEN` | inyección de arranque | Y |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `.env` | N |

> El contrato completo vive en `08` §Variables de entorno. Auth-específicas (`KEYCLOAK_*` operativas) las consume C-06.

## Risks / Trade-offs

- **[Parametrizar mal la pieza de C-03 / levantar Redis o RabbitMQ por defecto]** → Mitigación: D2 — la pieza se selecciona por el veredicto explícito de C-03; por omisión A4 (Postgres-cola), sin over-provisioning (DD-19).
- **[Acoplar el dominio a la infraestructura desde el scaffolding]** → Mitigación: D1 — dominio puro sin imports de framework; adaptadores detrás de puertos.
- **[Secretos filtrados en imágenes]** → Mitigación: D5 — Vault/tmpfs, nunca hardcode.
- **[Migración 001 invadiendo el scope de C-05]** → Mitigación: D4 — 001 solo habilita la extensión y deja el esquema vacío.
- **Trade-off aceptado**: Compose en vez de K8s implica operación manual inicial; aceptable por time-to-market (DD-11) y reversible sin reescritura (twelve-factor).

## Migration Plan

1. Scaffolding del árbol del monorepo (cierra SU-07).
2. `docker-compose` con Postgres/TimescaleDB, MinIO/S3, Keycloak, Nginx TLS 1.3 y observabilidad base.
3. Alembic + migración 001 (extensión TimescaleDB + esquema vacío).
4. Carga de config twelve-factor + Vault/tmpfs; FastAPI mono-hilo con healthchecks.
5. Smoke tests: arranque, healthchecks, conectividad DB/storage/IdP.
6. **Criterio de salida**: stack arrancable, observable y verificado ⇒ desbloquea C-05.

**Rollback**: `docker-compose down`; la migración 001 es reversible (drop de la extensión sobre esquema vacío). No hay datos de producción que perder.

## Open Questions

- ¿Qué adaptador exacto de `messaging` se instancia? → lo fija **el veredicto de C-03** (no se resuelve aquí).
- Detalle del realm/clientes de Keycloak (seed) → se completa en C-06; aquí solo corre el contenedor.
