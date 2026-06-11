# Spec — local-stack-compose

> Capacidad de **stack local reproducible** vía Docker Compose. Levanta las piezas del MVP (Postgres/TimescaleDB, MinIO/S3, Keycloak, Nginx TLS 1.3) con la pieza de cola/transporte/backplane según el ganador de C-03. Su Done es: el stack arranca y responde.

## ADDED Requirements

### Requirement: Stack base del MVP arrancable por Docker Compose
El `docker-compose` SHALL levantar PostgreSQL con la extensión TimescaleDB, MinIO/S3, Keycloak y Nginx con terminación TLS 1.3 como reverse proxy, conforme a DD-11 y `08` §Seguridad.

#### Scenario: docker-compose up levanta el stack base
- **WHEN** se ejecuta `docker-compose up` en un entorno limpio
- **THEN** quedan corriendo PostgreSQL/TimescaleDB, MinIO/S3, Keycloak y Nginx (TLS 1.3), todos con healthcheck en estado healthy

#### Scenario: Nginx termina TLS 1.3 y expone healthchecks
- **WHEN** un cliente accede al endpoint del stack a través de Nginx
- **THEN** la conexión negocia TLS 1.3 y los healthchecks de las instancias FastAPI están disponibles para que Nginx saque del pool una instancia caída (DD-10)

### Requirement: Pieza de cola/transporte/backplane parametrizada por el ganador de C-03
El `docker-compose` SHALL instanciar la pieza de cola/transporte/backplane según el veredicto de C-03, sin levantar Redis ni RabbitMQ por defecto cuando la métrica de C-03 no los exija (DD-19).

#### Scenario: Se levanta solo la pieza decidida por C-03
- **WHEN** se configura el stack tras el veredicto de C-03
- **THEN** el compose instancia exactamente la cola/transporte/backplane ganador (por omisión la hipótesis A4: Postgres-cola + SSE + `LISTEN/NOTIFY`) y no añade piezas del SAD que la métrica no haya promovido
