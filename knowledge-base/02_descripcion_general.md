# Descripción General

> **Nota importante sobre dos arquitecturas en la fuente.** El discovery presenta (a) la arquitectura del SAD original (RabbitMQ + Redis + Celery, WebSockets con sticky sessions, MediaPipe acoplado) y (b) una **arquitectura recomendada** (apéndice A4) que conserva los aciertos estructurales pero simplifica la mensajería (Postgres-como-cola en el MVP), usa SSE para el panel y abstrae el motor de visión. El principio rector del documento es: *"Empezá con la arquitectura más simple que cumpla los NFR, instrumentá todo, y agregá complejidad solo cuando una métrica lo demuestre necesario."* Este archivo documenta **ambas**, marcando cuál corresponde al MVP recomendado y cuál a la fase de escala. Ver `08_arquitectura_propuesta.md` y `09_decisiones_y_supuestos.md`.

## Stack tecnológico

| Capa | Tecnologías | Notas / versión |
|------|-------------|------------------|
| Frontend | React + Vite + Zustand + Tailwind | Bundle inicial objetivo < 500 KB; Redux descartado por ceremonia |
| IA en cliente | MediaPipe (BlazeFace/Face Detection, Face Mesh 468 landmarks, Pose) sobre WebAssembly + WebGL, en Web Worker | Evaluar delegado GPU / WebGPU con fallback a WebGL/WASM; **abstraer el motor** para migrar a ONNX Runtime Web |
| Captura multimedia | getUserMedia (cámara/mic), Screen Capture API (pantalla/monitores) | — |
| Buffer cliente | IndexedDB (buffer circular de eventos, resiliente a cortes) | Reenvío ordenado con `last_event_id` |
| Reverse proxy / TLS | Nginx (TLS 1.3, HSTS+preload, OCSP stapling, balanceo, estáticos) | Sticky sessions para WS (SAD) |
| API y tiempo real | FastAPI (ASGI/uvicorn), escalado horizontal mono-hilo; REST `/api/v1` + WebSockets (+ SSE en arq. recomendada) | OpenAPI automático, validación Pydantic |
| Identidad | Keycloak (OAuth2 / OIDC / SAML), MFA | Federado con directorio institucional, JIT provisioning |
| Datos de dominio | PostgreSQL | Consistencia transaccional |
| Series temporales | TimescaleDB (extensión de Postgres) | Hypertables, compresión 10–20×, continuous aggregates |
| Caché / fan-out | Redis (caché, Pub/Sub < 50 ms, rate limiting) | En arq. recomendada: opcional, solo si el dato lo justifica |
| Mensajería crítica | RabbitMQ (quorum queues, consenso Raft) | **SAD**: tareas críticas. **Recomendado MVP**: reemplazado por Postgres-como-cola (pg-boss / SKIP LOCKED) |
| Procesamiento asíncrono | Celery workers sobre RabbitMQ | **SAD**. En MVP recomendado: worker leyendo cola en Postgres |
| Evidencia | MinIO / S3 con Object Lock (WORM), cifrado at-rest, versionado | Abstracción storage: self-hosted o cloud |
| Secretos | HashiCorp Vault (o secret manager del cloud) | Inyección en tmpfs efímero; nunca en código/imágenes |
| Observabilidad | Prometheus (métricas), Loki (logs), Tempo/OpenTelemetry (trazas), Grafana | Desde Fase 0 ("ciudadano de primera clase") |
| Migraciones | Alembic (migrations versionadas, destructivas en dos pasos) | — |
| Orquestación | Docker Compose (inicial) → Kubernetes (escala) | Código twelve-factor desde el día uno |
| CI/CD | GitLab CI o GitHub Actions | Build con tag inmutable por hash de commit; deploy manual a prod con doble aprobación |

## Arquitectura general

El sistema es **client-heavy**: toda inferencia de visión que pueda correr en el navegador, corre ahí (procesar 700 streams de video de forma centralizada costaría 10–50× más). El backend nunca ve los pixels originales salvo en momentos puntuales, y trata al cliente como **sensor no confiable**: re-analiza, re-hashea y firma la evidencia con autoridad propia. La comunicación es **event-driven**: el cliente emite eventos, el servidor publica eventos a los que los paneles se suscriben, el procesamiento intensivo se encola.

Tres planos: cliente (navegador), aplicación en tiempo real (FastAPI + WebSockets/SSE) y procesamiento asíncrono (workers), soportados por persistencia (PostgreSQL+TimescaleDB, Redis, MinIO/S3) y observabilidad transversal.

### Diagrama (arquitectura recomendada — Nivel 1 / MVP)

```
CLIENTE   React + Vite · Web Worker
          Motor de visión ABSTRAÍDO → MediaPipe (impl. inicial)
          Liveness híbrido (pasivo + reto activo) · IndexedDB · anti-cámara-virtual
              │ HTTPS / WebSocket(estudiante) / SSE(panel)
              ▼
BORDE     Nginx · TLS 1.3 · backplane de eventos (LISTEN/NOTIFY o Redis)
              ▼
APP       FastAPI ×N (stateless) ───── Keycloak (OAuth2/OIDC/SAML)
              │
              ▼
DATOS+COLA PostgreSQL + TimescaleDB
              ├─ eventos (hypertable, compresión, agregados continuos)
              ├─ COLA de trabajos (pg-boss / SKIP LOCKED) ← re-inferencia, firma
              └─ audit log inmutable (append-only, hashes encadenados)
              ▼
EVIDENCIA MinIO/S3 · Object Lock (WORM) · cifrado at-rest
OBSERV.   Prometheus · Loki · Tempo · Grafana   (desde el día uno)
```

### Diagrama (SAD original — destino de escala)

```
CLIENTES (navegador) ──HTTPS/WSS──► NGINX (TLS 1.3, sticky sessions)
   │ Estudiante: React·Vite·Zustand · MediaPipe (WASM/WebGL) · Web Worker · IndexedDB
   │ Proctor/Revisor: React (fan-out de eventos vía WSS)
   ▼
APLICACIÓN (tiempo real): FastAPI ×3 (ASGI/uvicorn) ◄──► Keycloak HA
   │ Redis Pub/Sub        │ RabbitMQ (3 nodos · quorum queues)
   ▼                      ▼
PROCESAMIENTO ASÍNCRONO: Celery workers (re-inferencia · firma · reportes · maint.)
   ▼
PERSISTENCIA: PostgreSQL+TimescaleDB · Redis (caché) · MinIO/S3 (evidencia WORM)
TRANSVERSAL: Prometheus · Loki · Tempo · Grafana
```

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| Directorio institucional (Active Directory / LDAP / IdP SAML) | Federación de identidad, autenticación de estudiantes y staff | SAML / LDAP vía Keycloak |
| LMS institucional | El estudiante rinde el examen ahí; el proctoring se integra alrededor | Embedding / LTI / flujo coordinado (Fase 2) |
| MinIO / S3 | Almacenamiento WORM de evidencia | SDK / API S3 |
| HashiCorp Vault (o secret manager cloud) | Gestión de secretos | API / agente |
| Sistema de auditoría externa | Lectura write-only de backups del audit log | Backup físicamente separado |

## API REST (resumen)

API versionada desde el día uno (`/api/v1/...`). Recursos principales: auth, exams, sessions, evidence, review, dsr (derechos del titular). Canales WebSocket por rol: estudiante, proctor, admin. Detalle completo de endpoints y eventos en `07_flujos_principales.md` y `08_arquitectura_propuesta.md`.

| Método | Ruta | Propósito |
|--------|------|-----------|
| POST | `/api/v1/auth/refresh` | Refresco de token (JWT Keycloak) |
| POST | `/api/v1/exams` | Crear examen (admin) |
| POST | `/api/v1/exams/{id}/students` | Asignar estudiantes habilitados |
| POST | `/api/v1/sessions` | Iniciar sesión de examen |
| GET | `/api/v1/sessions/{id}` | Estado de la sesión |
| POST | `/api/v1/sessions/{id}/verify` | Enviar artefactos de verificación biométrica |
| POST | `/api/v1/sessions/{id}/finish` | Finalizar sesión ordenadamente |
| POST | `/api/v1/evidence/presign` | URL firmada para subir una captura |
| GET | `/api/v1/exams/{id}/events` | Consultar eventos/agregaciones (panel) |
| GET | `/api/v1/review/queue` | Cola de revisión ordenada por score |
| POST | `/api/v1/review/{session_id}/decision` | Emitir decisión terminal de revisión |
| POST | `/api/v1/evidence/{id}/verify-chain` | Certificado de verificación de cadena de custodia |
| POST | `/api/v1/dsr/{type}` | Derechos del titular (acceso/rectificación/eliminación/portabilidad) |
