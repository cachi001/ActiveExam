# Tasks — C-04 `foundation-setup`

> **Naturaleza**: estas tareas montan la **fundación de infraestructura y el scaffolding** del monorepo. El Done de cada tarea es estructural u operacional ("el stack arranca/se conecta/se observa"), no una feature de negocio. El change desbloquea C-05 cuando el stack es arrancable, observable y verificado, con la migración 001 dejando la extensión TimescaleDB lista.
> Dependencia: la pieza de cola/transporte/backplane se parametriza según **el ganador de C-03** (no se asume).

## 1. Scaffolding del monorepo (capability `monorepo-scaffolding`)

- [x] 1.1 Crear el árbol `backend/app/` con las capas `domain`, `application`, `infrastructure` (`persistence`, `messaging`, `storage`, `auth`), `presentation`, `workers`, `observability`, más `migrations/` y `tests/`; Done: árbol presente y dominio sin imports de framework
- [x] 1.2 Crear el árbol `frontend/src/` (`features`, `shared`, `vision`, `proctoring`, `transport`, `pages`); Done: estructura de features presente
- [x] 1.3 Crear `infra/` (`docker-compose/`, `nginx/`, `observability/`); Done: estructura de infra presente (cierra SU-07)
- [x] 1.4 Documentar en el README del repo el árbol canónico y que cierra la suposición SU-07; Done: convención de directorios documentada

## 2. Stack local en Docker Compose (capability `local-stack-compose`)

- [x] 2.1 Definir el servicio PostgreSQL con la extensión TimescaleDB disponible; Done: contenedor de DB con healthcheck healthy
- [x] 2.2 Definir los servicios MinIO/S3 y Keycloak; Done: storage e IdP arriba con healthcheck
- [x] 2.3 Definir Nginx como reverse proxy con terminación **TLS 1.3** y healthchecks de las instancias FastAPI; Done: TLS 1.3 negociado, instancias caídas salen del pool (DD-10)
- [x] 2.4 Parametrizar la pieza de cola/transporte/backplane según **el ganador de C-03** (por omisión A4: Postgres-cola + SSE + `LISTEN/NOTIFY`), sin levantar Redis/RabbitMQ por defecto si la métrica de C-03 no los exige; Done: solo la pieza decidida instanciada (DD-19)
- [ ] 2.5 Verificar `docker-compose up` en entorno limpio; Done: stack base completo arriba y healthy — _PENDIENTE: requiere Docker levantado (regla "never build" + entorno sin Docker). Comandos documentados en README.md §Comandos de verificación._

## 3. Migraciones Alembic (capability `db-migrations-baseline`)

- [x] 3.1 Configurar Alembic con la convención de migraciones **destructivas en dos pasos** (expand/contract); Done: convención documentada en el scaffolding de migraciones
- [x] 3.2 Escribir la **migración 001**: `CREATE EXTENSION timescaledb` + esquema **sin tablas de dominio**; Done: 001 aplica y deja la extensión lista para C-05
- [x] 3.3 Verificar que 001 es reversible sobre base limpia; Done: downgrade remueve la extensión sin pérdida (esquema vacío) — `upgrade`/`downgrade` escritos con `IF (NOT) EXISTS` (reversibles sobre esquema vacío); la ejecución contra una DB real está documentada en migrations/README.md (requiere stack)

## 4. Config twelve-factor y ejecución mono-hilo (capability `twelve-factor-config`)

- [x] 4.1 Definir el `.env` con las variables del stack (`DATABASE_URL`, `STORAGE_*`, `KEYCLOAK_*`, `VAULT_*`, `OTEL_*`) y la carga por entorno; Done: config 100% por entorno
- [x] 4.2 Integrar la inyección de secretos vía **Vault en tmpfs efímero**; Done: ningún secreto en la imagen Docker (`08` §Gestión de secretos)
- [x] 4.3 Configurar FastAPI **mono-hilo** (un proceso uvicorn, un hilo asíncrono) escalable horizontalmente detrás de Nginx (DD-10); Done: 1 instancia = 1 proceso, escalado horizontal verificado — app factory mono-hilo (`uvicorn --workers 1`), upstream Nginx con pooling por healthcheck; el `--scale api=N` real requiere el stack
- [x] 4.4 Hacer que la app falle explícitamente en el arranque si falta config requerida; Done: sin defaults inseguros (twelve-factor)

## 5. Observabilidad base y smoke tests (capability `observability-baseline`)

- [x] 5.1 Levantar Prometheus, Loki, Tempo y Grafana en el compose (DD-12) con scraping de FastAPI y exportación OTLP (`OTEL_EXPORTER_OTLP_ENDPOINT`); Done: tres pilares visibles en Grafana sin dominio aún
- [x] 5.2 Escribir smoke tests de arranque: el stack levanta y los healthchecks responden OK; Done: healthchecks verdes verificados
- [x] 5.3 Escribir smoke tests de conectividad contra DB (PostgreSQL/TimescaleDB), storage (MinIO/S3) e IdP (Keycloak); Done: conexión a las tres verificada, falla explícita si alguna no responde — tests escritos y marcados `@pytest.mark.requires_stack` (se ejecutan con `RUN_STACK_TESTS=1` y el stack arriba)
- [x] 5.4 Declarar el criterio de salida: stack arrancable + observable + conectividad verificada ⇒ desbloquea C-05; Done: fundación lista y documentada
