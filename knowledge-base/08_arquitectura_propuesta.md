# Arquitectura Propuesta

> El discovery recomienda explícitamente (apéndice A4) **empezar por la arquitectura más simple que cumpla los NFR e incrementar complejidad solo cuando una métrica lo demuestre**. Por eso este documento prioriza la **arquitectura recomendada Nivel 1 (MVP)** como base de desarrollo y documenta el SAD original como destino de escala. Las decisiones formales están en `09_decisiones_y_supuestos.md` (ADR-0001…0014 + revisiones A4).

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|--------|--------------|---------|
| Client-heavy / edge computing | IA de visión corre en el navegador | Centralizar inferencia de 700 streams sería 10–50× más caro |
| Backend como verificador (zero trust del cliente) | Re-inferencia, re-hash, firma maestra server-side | El cliente es sensor no confiable; la versión confiable es la del servidor |
| Event-driven / desacoplamiento | Eventos estructurados versionados; fan-out a paneles; encolado de tareas | Escalabilidad horizontal, resiliencia, evolución independiente |
| Arquitectura por capas (Clean/Hexagonal pragmática) | Backend: dominio puro, aplicación (casos de uso), infraestructura (puertos), presentación delgada | Testabilidad, sustituibilidad de infraestructura (Postgres, Redis, RabbitMQ, MinIO) |
| Puertos y adaptadores | Storage (MinIO/S3), identidad (Keycloak), **motor de visión abstraído** | Portabilidad self-hosted/cloud; migrar MediaPipe → ONNX Runtime Web sin reescribir |
| CQRS-lite vía continuous aggregates | Lecturas de paneles desde agregados materializados de TimescaleDB | Reduce latencia de paneles en órdenes de magnitud |
| Twelve-factor | Todos los componentes (config por entorno, logs a stdout, sin estado local) | Migración trivial a Kubernetes |
| Sidecar de observabilidad | Prometheus/Loti/Tempo/Grafana desde Fase 0 | "Una función no observable no está lista" |
| WORM / inmutabilidad | Bucket de evidencia (Object Lock Compliance) + audit log append-only | Cadena de custodia defendible |
| Saga/outbox implícito (cola en DB) | Postgres-como-cola (pg-boss / SKIP LOCKED) en MVP | Durabilidad transaccional sin broker externo |

## Estructura de directorios

**Suposición** (el discovery describe la arquitectura por capas pero no fija el árbol de carpetas; estructura inferida coherente con Clean/Hexagonal + monorepo):

```
proctoring/
├── backend/
│   └── app/
│       ├── domain/              # entidades, reglas de transición de eventos, scoring (puro)
│       ├── application/         # casos de uso (verificar identidad, encolar revisión, firmar evidencia)
│       ├── infrastructure/      # adaptadores: postgres, timescale, redis, storage(minio/s3), keycloak, cola
│       │   ├── persistence/
│       │   ├── messaging/       # cola en Postgres (MVP) | rabbitmq+celery (escala)
│       │   ├── storage/
│       │   └── auth/
│       ├── presentation/        # routers FastAPI REST /api/v1 + WebSocket/SSE handlers
│       ├── workers/             # re-inferencia, firma de evidencia, reportes, mantenimiento
│       └── observability/       # métricas, trazas, logging estructurado
│   ├── migrations/              # Alembic (destructivas en dos pasos)
│   └── tests/                   # unit / integration / contract / e2e / load
├── frontend/
│   └── src/
│       ├── features/            # examen, biometría, consentimiento, panel-proctor, cola-revision
│       ├── shared/              # ui, hooks, store (Zustand)
│       ├── vision/              # motor de visión ABSTRAÍDO (impl. MediaPipe), Web Worker
│       ├── proctoring/          # detectores de pestaña/foco/monitores, liveness, anti-tampering
│       ├── transport/           # WS estudiante, SSE panel, upload por URL firmada, buffer IndexedDB
│       └── pages/
├── infra/
│   ├── docker-compose/          # despliegue inicial
│   ├── k8s/                     # manifests/operators (escala)
│   ├── nginx/                   # TLS 1.3, sticky sessions, health checks
│   └── observability/           # Prometheus, Loki, Tempo, Grafana, Alertmanager
├── docs/                        # discovery, ADRs, runbooks
└── knowledge-base/              # esta KB
```

## Seguridad

- **Autenticación**: delegada a Keycloak (OAuth2/OIDC/SAML), federada con el directorio institucional vía JIT provisioning. JWT validado localmente contra clave pública (JWKS cacheado). Access tokens 15–60 min; refresh tokens rotativos.
- **Autorización**: RBAC con permisos **contextuales** (un proctor ve solo exámenes asignados; un revisor solo su jurisdicción). MFA obligatorio para roles con acceso a evidencia/administración (TOTP mín., WebAuthn recomendado). Descarga de capturas vía URL firmada (expira 15 min) con propósito declarado en audit log.
- **Validación de input**: Pydantic (FastAPI), SQLAlchemy parametrizado (anti-SQLi), escape de React + DOMPurify (anti-XSS), JWT + SameSite + tokens dedicados (anti-CSRF), rate limiting en Keycloak y Nginx (anti fuerza bruta).
- **Cifrado en tránsito**: TLS 1.3 en todo, **incluida la comunicación interna** entre componentes (Postgres/Redis/RabbitMQ/MinIO con TLS). HSTS con preload, OCSP stapling.
- **Cifrado at-rest**: KMS para evidencia y embeddings; versionado y logging activados en el bucket.
- **Cadena de custodia**: 4 etapas criptográficas acumulativas (cliente HMAC → backend re-hash → worker firma maestra RSA-2048/Ed25519 → re-inferencia firmada). Audit log append-only con hashes encadenados, backups físicamente separados write-only. Bucket WORM (Object Lock modo Compliance).
- **Gestión de secretos**: HashiCorp Vault (o secret manager del cloud); inyección en tmpfs efímero; nunca en código/imágenes. Rotación: passwords trimestral, claves API anual, clave maestra de firma anual (con archivo seguro de claves previas).
- **Gestión de vulnerabilidades**: Dependabot, escaneo de imágenes con Trivy/Grype (no se despliega con críticas sin resolver), penetration testing ≥ anual, canal de responsible disclosure.
- **Threat model de seguridad** (distinto del de proctoring): cuatro actores — estudiante adversario, atacante externo, insider malicioso, error humano. Defensa en profundidad, mínimo privilegio, separación de responsabilidades, trazabilidad.

## Variables de entorno

**Suposición** (el discovery no lista env vars explícitas; las siguientes se infieren del stack y se marcan como tales):

| Variable | Descripción | Ejemplo | Sensible |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Conexión PostgreSQL/TimescaleDB | `postgresql://app@db:5432/proctoring` | Y |
| `REDIS_URL` | Conexión Redis (caché/Pub-Sub) | `rediss://redis:6379/0` | Y |
| `RABBITMQ_URL` | Broker de tareas críticas (solo arq. de escala) | `amqps://mq:5671/` | Y |
| `STORAGE_ENDPOINT` | Endpoint MinIO/S3 | `https://minio:9000` | N |
| `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | Credenciales de object storage | — | Y |
| `STORAGE_BUCKET_EVIDENCE` | Bucket WORM de evidencia | `evidence` | N |
| `KEYCLOAK_ISSUER` | Issuer/realm de Keycloak | `https://idp/realms/inst` | N |
| `KEYCLOAK_JWKS_URL` | Endpoint de claves públicas | `https://idp/realms/inst/protocol/openid-connect/certs` | N |
| `JWT_AUDIENCE` | Audience esperado del JWT | `proctoring-api` | N |
| `EVIDENCE_MASTER_PRIVATE_KEY` | Clave maestra de firma (RSA-2048/Ed25519) | (vía Vault) | Y |
| `HMAC_SESSION_KEY_*` | Claves de sesión rotativas | (vía Vault/emisión) | Y |
| `VAULT_ADDR` / `VAULT_TOKEN` | Acceso al secret manager | — | Y |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Colector de trazas | `http://tempo:4317` | N |
| `PRESIGNED_URL_TTL` | TTL de URL firmada de descarga | `900` (15 min) | N |
| `RETENTION_POLICY_DEFAULT` | Política de retención por defecto | `2y` | N |
| `SCORE_THRESHOLD_DEFAULT` | Umbral de score para encolar revisión | (configurable por examen) | N |

> Todos los secretos se gestionan vía Vault e inyección en tmpfs; las env vars sensibles no deben hardcodearse en imágenes Docker (ver `09_decisiones_y_supuestos.md`).

## Dimensionamiento recomendado (escala objetivo)

> **Atención**: los conteos de instancia siguientes se calcularon sobre el supuesto original de **700 concurrentes**. El NFR operacional se elevó a **1.000 sostenido / ~2.100 pico** (ver `SU-06` en `09` y el capacity model en `14`). Estas cifras son un **piso a revalidar en la PoC de carga**, no un dimensionamiento final. En particular, el cálculo de conexiones WS por instancia y el número de réplicas FastAPI suben con el sostenido a 1.000.

- 3 instancias FastAPI (4 vCPU / 8 GB), mono-hilo, escaladas horizontalmente (1 instancia ≈ 1 pod).
- 2 workers críticos + 2 livianos (en SAD; en MVP: workers leyendo cola en Postgres).
- PostgreSQL primario (8 vCPU / 32 GB / SSD con IOPS provisionados) + réplica streaming.
- Redis liviano (4 vCPU / 8 GB) — opcional en MVP.
- RabbitMQ 3 nodos (2 vCPU / 4 GB c/u) — solo arq. de escala.
- Keycloak en 2 instancias (HA).
- 1 servidor dedicado de observabilidad.
- ~200–250 conexiones WebSocket por instancia (sticky sessions con monitoreo de distribución).
