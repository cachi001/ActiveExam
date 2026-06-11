# observability-baseline Specification

## Purpose
TBD - created by archiving change c-04-foundation-setup. Update Purpose after archive.
## Requirements
### Requirement: Base de observabilidad montada desde Fase 0
El stack SHALL incluir Prometheus, Loki, Tempo y Grafana corriendo desde este change (DD-12), con scraping de las instancias FastAPI y exportación OTLP configurada (`OTEL_EXPORTER_OTLP_ENDPOINT`), de modo que cada change posterior instrumente sobre esta base.

#### Scenario: Los tres pilares disponibles al arrancar
- **WHEN** se levanta el stack
- **THEN** Prometheus scrapea las instancias, Loki recibe logs JSON estructurados y Tempo recibe trazas vía OTLP, todo visible en Grafana (DD-12)

#### Scenario: Una función no observable no se considera lista
- **WHEN** se agrega instrumentación en un change posterior
- **THEN** reutiliza esta base (Prometheus/Loki/Tempo/Grafana) en lugar de montar observabilidad ad-hoc

### Requirement: Smoke tests de arranque y conectividad
El change SHALL incluir smoke tests que verifiquen que el stack arranca, que los healthchecks responden, y que hay conectividad contra DB (PostgreSQL/TimescaleDB), storage (MinIO/S3) e IdP (Keycloak).

#### Scenario: Healthchecks responden al arrancar
- **WHEN** el stack termina de levantar
- **THEN** los smoke tests confirman que los healthchecks de las instancias FastAPI responden OK

#### Scenario: Conectividad verificada contra DB, storage e IdP
- **WHEN** se ejecutan los smoke tests de conectividad
- **THEN** se confirma conexión exitosa a PostgreSQL/TimescaleDB, a MinIO/S3 y a Keycloak, fallando explícitamente si alguna no responde

