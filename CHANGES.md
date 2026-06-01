# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Proctoring** (plataforma self-hosted de supervisión asistida por IA de evaluaciones universitarias remotas).
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. **Identificá el change** por su código `C-NN` en la fase correspondiente. Respetá el orden de dependencias: no arranques un change cuyas dependencias estén en `[ ]`.
2. **Leé la KB** indicada en "Leer antes" de ese change (3-5 canónicos con su sección) ANTES de proponer.
3. **Proponé** con `/opsx:propose C-NN-<nombre>` para generar proposal + design + tasks.
4. **Implementá y archivá** con `/opsx:apply` y luego `/opsx:archive` cuando los criterios estén cumplidos.
5. **Marcá el checkbox** del change (`[ ]` → `[x]`) al archivar. Eso desbloquea los gates que dependen de él.

> **Regla de oro del proyecto (DD-19)**: "Empezá con la arquitectura más simple que cumpla los NFR, instrumentá todo, y agregá complejidad solo cuando una métrica lo demuestre." La hipótesis por defecto es la opción A4 (la más simple); promover piezas del SAD (RabbitMQ, WebSocket+sticky, Redis) requiere que **C-03 (PoC de carga)** lo exija con métricas.

---

## Gates organizacionales de Fase 0 (BLOQUEAN TODO el desarrollo)

Estos no producen software pero **son precondición dura** para el resto del roadmap (KB 09 DD-14, 10_preguntas_abiertas Alta, 13_legal, 15_roadmap Fase 0). Se modelan como changes `C-01` y `C-02` con governance CRITICO y deben cerrarse antes de tocar código de dominio.

- **C-01** — Acuerdo de Nivel de Proctoring firmado + DPIA completo + 14 ADRs aprobados (legal/patrocinador).
- **C-02** — Designación y capacitación de revisores humanos y coordinación operativa (dirección académica). **La dependencia más subestimada del proyecto (SU-03 / O-003).**

Sin C-01 y C-02 en `[x]`, el sistema no puede operar legalmente ni cumplir su propósito, aunque el código exista.

---

## Árbol de dependencias

```
C-01 acuerdo-proctoring-dpia  (gate legal — Fase 0)
C-02 designacion-revisores    (gate organizacional — Fase 0)
   │
   ▼
C-03 poc-carga-mensajeria  ★ Tier 1 · BLOQUEANTE · valida cola/transporte/backplane al PICO ~2.100/~5.000 inserts/s
   │
   ▼
C-04 foundation-setup  (monorepo, docker-compose, .env, Alembic, DB inicial, observabilidad base)
   │
   ▼
C-05 core-models  (Usuario, Examen, Sesión, Evento[hypertable], Evidencia, Audit log, Consentimiento, Embedding, Caso)
   │
   ├──► C-06 auth-rbac-keycloak  ◄── (todo recurso protegido depende de esto)
   │        │
   │        ├──► C-07 exam-config        (admin: CRUD examen, asignaciones, foto referencia)
   │        │        │
   │        │        ├──► C-08 consentimiento
   │        │        │        │
   │        │        │        └──► C-09 biometria-liveness  (verificación 1:1 + clave de sesión)
   │        │        │                 │
   │        │        │                 └──► C-10 event-ingestion-transport  (WS estudiante + validación firma + TimescaleDB)
   │        │        │                          │   [usa el ganador de C-03]
   │        │        │                          ├──► C-11 vision-engine-detectores  (motor abstraído + reglas de transición)
   │        │        │                          ├──► C-12 evidencia-cadena-custodia  (clip+firma+worker+firma maestra)
   │        │        │                          ├──► C-13 scoring-incremental        (continuous aggregates)
   │        │        │                          ├──► C-14 resiliencia-reconexion     (buffer IndexedDB + replay exactly-once)
   │        │        │                          │
   │        │        │                          └──► C-15 panel-proctor-sse  (SSE + backplane; alertas <500ms)
   │        │        │                                   │   [usa el ganador de C-03]
   │        │        │                                   └──► C-16 cola-revision-humana  (orden por score + audit de acceso + decisión)
   │        │        │
   │        │        └──► C-19 retencion-holds  (políticas automáticas + hold por caso)
   │        │
   │        └──► C-17 dsr-derechos-titular  (acceso/rectificación/eliminación/portabilidad)
   │
   └──► C-18 verificacion-cadena-apelacion  (POST verify-chain + certificado para perito) [dep C-12]
        C-20 reportes-analytics  (Fase 2) [dep C-13, C-16]
```

### Paralelismo por fase

```
GATE 0: (arranque del proyecto)
  → C-01 acuerdo-proctoring-dpia        [Legal/Patrocinador]   ← gates organizacionales, en paralelo entre sí
  → C-02 designacion-revisores          [Dirección académica]

GATE 1: C-01 ✓ y C-02 ✓                  ← desbloquea desarrollo
  → C-03 poc-carga-mensajeria           [Agente A — Tier 1, BLOQUEANTE: nada de cola/transporte/tiempo real avanza sin esto]

GATE 2: C-03 ✓                            ← decisión de arquitectura tomada (cola / transporte / backplane)
  → C-04 foundation-setup               [Agente A]

GATE 3: C-04 ✓
  → C-05 core-models                    [Agente A]

GATE 4: C-05 ✓                            ← FORK
  → C-06 auth-rbac-keycloak             [Agente A — CRITICO, todo recurso protegido depende]

GATE 5: C-06 ✓                            ← FORK
  → C-07 exam-config                    [Agente A]
  → C-17 dsr-derechos-titular           [Agente B — solo necesita core-models + auth]

GATE 6: C-07 ✓                            ← FORK
  → C-08 consentimiento                 [Agente A]
  → C-19 retencion-holds                [Agente B]

GATE 7: C-08 ✓
  → C-09 biometria-liveness             [Agente A — frontend+backend acoplados]

GATE 8: C-09 ✓
  → C-10 event-ingestion-transport      [Agente A — usa ganador de C-03]

GATE 9: C-10 ✓                            ← FORK GRANDE (rama de tiempo real desplegada)
  → C-11 vision-engine-detectores       [Agente C — frontend/Web Worker]
  → C-12 evidencia-cadena-custodia      [Agente A — backend core + worker]
  → C-13 scoring-incremental            [Agente B — backend aux]
  → C-14 resiliencia-reconexion         [Agente C — frontend transport]
  → C-15 panel-proctor-sse              [Agente B — usa ganador de C-03]

GATE 10: C-12 ✓
  → C-18 verificacion-cadena-apelacion  [Agente A]

GATE 11: C-15 ✓
  → C-16 cola-revision-humana           [Agente B]  ← cierre del ciclo MVP (cumple propósito con C-02)

GATE 12 (Fase 2): C-13 ✓ y C-16 ✓
  → C-20 reportes-analytics             [Agente C]
```

### Camino crítico (11 changes — mínimo irreducible hasta MVP operativo)

```
C-01 → C-03 → C-04 → C-05 → C-06 → C-07 → C-08 → C-09 → C-10 → C-15 → C-16*
```

> C-02 (designación de revisores) corre en paralelo a C-01 pero es **co-bloqueante**: sin él, C-16 (cola de revisión) no cumple su propósito aunque el código exista (SU-03). C-16* es el último change indispensable: cierra el ciclo extremo-a-extremo (verificación → examen → evidencia → revisión humana). C-11/C-12/C-13/C-14 son indispensables para un examen real pero salen en paralelo en GATE 9, no alargan la cadena.

### Plan óptimo con 3 agentes

| Paso | Agente A (Backend Core) | Agente B (Backend Aux) | Agente C (Frontend / Vision) |
|------|-------------------------|------------------------|------------------------------|
| 0 | C-01 / C-02 (coordinación con stakeholders — no-código) | — | — |
| 1 | C-03 poc-carga-mensajeria | — | — |
| 2 | C-04 foundation-setup | — | — |
| 3 | C-05 core-models | — | — |
| 4 | C-06 auth-rbac-keycloak | — | — |
| 5 | C-07 exam-config | C-17 dsr-derechos-titular | — |
| 6 | C-08 consentimiento | C-19 retencion-holds | — |
| 7 | C-09 biometria-liveness (backend) | — | C-09 biometria-liveness (cliente liveness) |
| 8 | C-10 event-ingestion-transport | — | — |
| 9 | C-12 evidencia-cadena-custodia | C-13 scoring-incremental + C-15 panel-proctor-sse | C-11 vision-engine + C-14 resiliencia |
| 10 | C-18 verificacion-cadena-apelacion | C-16 cola-revision-humana | — |
| 11 (F2) | — | — | C-20 reportes-analytics |

---

## FASE 0 — Fundaciones organizacionales y validación de arquitectura

> No produce software de dominio (C-01/C-02) o produce un prototipo descartable (C-03). **Bloquean todo lo demás.**

### [C-01] `acuerdo-proctoring-dpia`
- **Estado**: `[ ]` pendiente
- **Scope**: Gate organizacional, no-código.
  - Firma del **Acuerdo de Nivel de Proctoring** (nivel L2.5, DD-01) que calibra expectativas y delimita responsabilidad.
  - **DPIA** completo por el área legal/DPO antes de escribir código de dominio.
  - Aprobación formal de los **14 ADRs Tier 1** (DD-01…DD-14) + revisiones A4 (DD-15…DD-19).
  - Clasificación formal del embedding como dato sensible por defecto (IN-04 / SU-08).
  - Decisión de vía alternativa sin biometría y población menor de 18 (si aplica).
  - **Entregable**: documentos firmados; sin ellos el proyecto no sale de Fase 0.
- **Dependencias**: ninguna
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` (DPIA, base legal, checklist)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-14, §DD-01, §SU-08
  - `knowledge-base/10_preguntas_abiertas.md` §IN-04 §preguntas Alta
  - `knowledge-base/15_roadmap_y_riesgos.md` §Fase 0

### [C-02] `designacion-revisores`
- **Estado**: `[ ]` pendiente
- **Scope**: Gate organizacional, no-código. **La dependencia más subestimada del proyecto.**
  - Designación y capacitación de **revisores académicos** y **coordinación operativa** antes de Fase 1 (SU-03 / O-003).
  - Estimación temprana de carga de revisión (5–15% de sesiones) y dimensionamiento del equipo humano.
  - Plan de capacitación por rol (proctor, revisor, coordinador, on-call) y monitoreo de backlog.
  - **Entregable**: equipo humano de revisión designado, capacitado y con capacidad sostenida confirmada.
- **Dependencias**: ninguna (paralelo a C-01)
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/09_decisiones_y_supuestos.md` §SU-03
  - `knowledge-base/03_actores_y_roles.md` §RACI §revisor §coordinador
  - `knowledge-base/15_roadmap_y_riesgos.md` §O-003 §Gestión del cambio
  - `knowledge-base/07_flujos_principales.md` §Flujo 7

### [C-03] `poc-carga-mensajeria`  ★ Tier 1 · BLOQUEANTE
- **Estado**: `[ ]` pendiente
- **Scope**: PoC de carga formal que **valida la arquitectura de mensajería/transporte/backplane bajo carga**. Prototipo descartable; su salida es la **decisión de arquitectura**, no código de producción. La decisión NO es binaria SAD-vs-A4: se descompone en 3 concerns validados por separado.
  - **Concern (a) — Cola de trabajos**: Postgres-como-cola (pg-boss / SKIP LOCKED + LISTEN/NOTIFY) **vs** RabbitMQ quorum + Celery. Hipótesis por defecto = Postgres (A4, DD-15). (IN-01)
  - **Concern (b) — Transporte del panel**: SSE + backplane (sin sticky) **vs** WebSocket + sticky sessions. Hipótesis por defecto = SSE (A4, DD-16). (IN-02)
  - **Concern (c) — Backplane de eventos**: Postgres LISTEN/NOTIFY **vs** Redis Pub/Sub. Hipótesis por defecto = LISTEN/NOTIFY (A4, DD-16). ⚠️ **ESTE es el riesgo de tiempo real número uno**: `LISTEN/NOTIFY` serializa por una conexión y toma un lock global en el commit del `NOTIFY`; a fan-out de ~1.000–5.000 eventos/s entre instancias puede no sostener el p99 < 500 ms. Es el concern con mayor probabilidad de promover la pieza del SAD (Redis Pub/Sub, sub-50 ms, diseñado para fan-out). **La PoC debe atacarlo de frente.**
  - **Criterio de aceptación clavado al PICO** (NO al sostenido): **~2.100 concurrentes / ~5.000 inserts/s**, con los SLO de `14`:
    - **Tiempo real — fan-out del panel**: con **N paneles de proctor activos** (≈ 1 proctor / 50–100 estudiantes ⇒ ~20–40 paneles concurrentes) suscriptos a sus sesiones asignadas, la latencia de propagación evento-cliente→panel debe ser **p99 < 500 ms** *en sostenido al pico*, no solo en estado de reposo. Este es el criterio que decide LISTEN/NOTIFY vs Redis.
    - **Cero pérdida** de eventos confirmados / evidencia (exactly-once lógico bajo reconexión y caída de instancia).
    - Re-inferencia + firma final **< 30 s** desde la subida (camino asíncrono — no es tiempo real).
  - Generadores de carga vs capacity model (`14`); instrumentación completa (Prometheus/Tempo) para que la decisión sea por métrica.
  - **Salida**: por cada concern, decisión registrada (promover pieza del SAD **solo si** la métrica lo exige); documentada como evolución, no retrabajo. Documentar explícitamente el veredicto del backplane (LISTEN/NOTIFY sostiene el pico ✓ / se promueve Redis ✗).
  - Tests: load/estrés al pico sostenido (no burst aislado), **medición de p99 de fan-out con N paneles activos degradando LISTEN/NOTIFY hasta el punto de quiebre**, caos (caída de instancia/nodo durante el pico), exactly-once bajo reconexión.
- **Dependencias**: `C-01, C-02`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/14_observabilidad_y_devops.md` §SLIs/SLOs §Capacity model
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-15 §DD-16 §DD-19 §SU-06
  - `knowledge-base/10_preguntas_abiertas.md` §IN-01 §IN-02
  - `knowledge-base/08_arquitectura_propuesta.md` §Dimensionamiento §Patrones
  - `knowledge-base/07_flujos_principales.md` §Flujo 3 §Flujo 4 §Flujo 5

---

## FASE 1 — MVP (ciclo completo de un examen)

> Cadena lineal hasta el monitoreo en tiempo real (C-04…C-10), luego fork grande en GATE 9. Todo lo de cola/transporte usa el **ganador de C-03**.

### [C-04] `foundation-setup`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Monorepo `backend/` (Clean/Hexagonal: domain/application/infrastructure/presentation/workers/observability) + `frontend/` (features/shared/vision/proctoring/transport/pages) + `infra/`.
  - `docker-compose` inicial: PostgreSQL+TimescaleDB, MinIO/S3, Keycloak, Nginx (TLS 1.3), observabilidad base (Prometheus/Loki/Tempo/Grafana) — DD-12.
  - Alembic configurado (migraciones destructivas en dos pasos); Migración 001: extensión TimescaleDB + esquema vacío.
  - `.env` con las env vars del stack (DATABASE_URL, STORAGE_*, KEYCLOAK_*, VAULT_*, OTEL_*) gestionadas vía Vault/tmpfs.
  - FastAPI mono-hilo escalado horizontalmente (DD-10), código twelve-factor (DD-11).
  - Tests: smoke de arranque de servicios, healthchecks, conexión a DB/storage/IdP.
- **Dependencias**: `C-03`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios §Variables de entorno §Seguridad
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-10 §DD-11 §DD-12
  - `knowledge-base/14_observabilidad_y_devops.md` §Topología inicial §Tres pilares

### [C-05] `core-models`
- **Estado**: `[ ]` pendiente
- **Scope**: Entidades base que todo lo demás referencia.
  - Modelos transaccionales: `Usuario`, `Examen`, `Sesión` (enum de estado: iniciada/activa/finalizada/flaggeada/cerrada), `Asignación` (proctor↔examen), `Consentimiento` (inmutable), `Embedding` (cifrado), `Evidencia`, `Caso disciplinario`.
  - `Audit log` **append-only** con trigger que rechaza UPDATE/DELETE + hash encadenado (hash_prev).
  - `Evento` como **hypertable TimescaleDB**: índices `(session_id, timestamp)` y `(exam_id, timestamp)`; política de compresión (7d sin comprimir, >7d comprimido); continuous aggregates base.
  - Migración 002: tablas de dominio + hypertable + trigger append-only del audit log.
  - Repositorios genéricos (puertos) por dominio.
  - Tests: constraints de enum, trigger append-only rechaza mutaciones, encadenamiento de hash, creación de hypertable.
- **Dependencias**: `C-04`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` (entidades completas, ERD, cardinalidades)
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (capas, CQRS-lite)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-05 §DD-07

### [C-06] `auth-rbac-keycloak`
- **Estado**: `[ ]` pendiente
- **Scope**: Autenticación y autorización — **todo recurso protegido depende de esto**.
  - Federación con Keycloak (OAuth2/OIDC/SAML), JIT provisioning del Usuario al primer login federado.
  - Validación local de JWT contra JWKS cacheado; access 15–60 min; refresh rotativo. `POST /api/v1/auth/refresh`.
  - RBAC con permisos **contextuales** (proctor solo exámenes asignados; revisor solo su jurisdicción) — 7 roles.
  - MFA obligatorio para roles con acceso a evidencia/administración (TOTP mín., WebAuthn recomendado).
  - Validación de handshake WS/SSE con JWT + revalidación periódica.
  - Rate limiting (Keycloak + Nginx). Definición de rutas públicas (login redirect, estáticos).
  - Tests: validación JWT, expiración/refresh, aislamiento por rol contextual, MFA enforcement, rechazo de handshake sin token.
- **Dependencias**: `C-05`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC §Rutas públicas
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad (auth/authz)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-09
  - `knowledge-base/07_flujos_principales.md` §Flujo 1

### [C-07] `exam-config`
- **Estado**: `[ ]` pendiente
- **Scope**: Configuración pre-examen (US-001, FR-01).
  - Endpoints admin: CRUD `Examen` (nombre, ventana temporal, umbral de score, política de retención, detectores activos + umbrales).
  - Asignación de estudiantes habilitados (solo ellos inician); asignación proctor↔examen.
  - Carga de **foto institucional de referencia** (o marcado como precomputada) — prerrequisito de la verificación 1:1 (SU-01).
  - Calendarización visible para operaciones.
  - Tests: CRUD, RBAC admin-only, validación de parámetros, lista de habilitados.
- **Dependencias**: `C-06`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-001
  - `knowledge-base/04_modelo_de_datos.md` §Examen §Asignación
  - `knowledge-base/05_reglas_de_negocio.md` §RN-EX
  - `knowledge-base/03_actores_y_roles.md` §Admin de exámenes

### [C-08] `consentimiento`
- **Estado**: `[ ]` pendiente
- **Scope**: Consentimiento informado (US-003, FR-03).
  - Pantalla dedicada con lenguaje claro (qué/cómo/dónde/cuánto/derechos); acción afirmativa, sin casillas premarcadas.
  - Persistencia inmutable del acuse con timestamp + hash (`Consentimiento`).
  - Vía alternativa sin biometría para quien no consiente (escalación a proctor humano).
  - Tests: registro inmutable, hash, rechazo sin acción afirmativa, ruta alternativa.
- **Dependencias**: `C-07`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-003
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §Base legal §Checklist
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CO
  - `knowledge-base/07_flujos_principales.md` §Flujo 2

### [C-09] `biometria-liveness`
- **Estado**: `[ ]` pendiente
- **Scope**: Verificación biométrica de identidad (US-004, FR-04, UC-01). Frontend + backend acoplados.
  - Cliente: captura video 3–5 s, liveness **híbrido propio** (pasivo + 1–2 retos activos aleatorios), cálculo de embedding (Face Mesh), detección de cámara virtual (DD-18).
  - Comparación 1:1 por distancia coseno contra el embedding de referencia (leído cifrado de la DB).
  - Backend: emisión de **clave de sesión rotativa** (HMAC) si distancia < umbral; re-inferencia server-side del clip.
  - Hasta 2 reintentos; al 3.º fallo → evento crítico + escalación a proctor (no abort).
  - Clip + embedding persistidos con cadena de custodia inicial (cifrado at-rest, eliminado al egreso).
  - Tests: liveness, distancia coseno, emisión de clave, reintentos→escalación, cifrado del embedding.
- **Dependencias**: `C-08`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-004 §US-005
  - `knowledge-base/12_biometria_y_liveness.md` (pipeline completo de liveness/embedding)
  - `knowledge-base/04_modelo_de_datos.md` §Embedding §Sesión
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-03 §DD-18
  - `knowledge-base/07_flujos_principales.md` §Flujo 2

### [C-10] `event-ingestion-transport`
- **Estado**: `[ ]` pendiente
- **Scope**: Generación e ingesta de eventos firmados (US-007, FR-07; Flujo 3). **Usa el ganador de transporte de C-03.**
  - Canal **WebSocket del estudiante** (bidireccional): eventos/heartbeats/comandos; handshake con session_id + JWT + last_event_id.
  - Esquema de evento versionado: id, session_id, exam_id, tipo, severidad, ts_client, ts_backend, payload JSON, firma HMAC, schema_version.
  - Backend valida **firma de cada evento** antes de persistir en TimescaleDB; heartbeat firmado cada 5 s.
  - Fan-out a paneles vía backplane (ganador de C-03: LISTEN/NOTIFY o Redis Pub/Sub).
  - Eventos: `ROUND`-style del dominio proctoring (rostro ausente, múltiples rostros, mirada, postura, pestaña/foco, monitores, posible cambio de identidad, evidencia corrupta).
  - Tests: validación de firma, rechazo de evento no firmado, persistencia en hypertable, contrato de esquema versionado, fan-out.
- **Dependencias**: `C-09`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-007
  - `knowledge-base/07_flujos_principales.md` §Flujo 3
  - `knowledge-base/04_modelo_de_datos.md` §Evento
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-16 §DD-05
  - `knowledge-base/05_reglas_de_negocio.md` §RN-EV

### [C-11] `vision-engine-detectores`
- **Estado**: `[ ]` pendiente
- **Scope**: Pipeline de visión en el cliente (US-006, FR-06, UC-02). Frontend / Web Worker.
  - **Motor de visión abstraído** detrás de interfaz (MediaPipe en MVP, ruta a ONNX Runtime Web — DD-17).
  - Tres detectores: Face Detection (5–10 fps), Face Mesh (5–10 fps, mirada + embedding), Pose (2–5 fps); WASM+WebGL en Web Worker, transferencia de buffers sin copias.
  - Detector adicional: pestaña activa, foco de ventana, monitores múltiples.
  - **Reglas de transición de estado** (configurables por institución): señales continuas → eventos discretos con severidad (umbrales temporales, fotogramas consecutivos, patrones sostenidos).
  - Múltiples rostros (≥2 durante N fotogramas) → severidad alta + captura evidencia + alerta < 500 ms.
  - Degradación graceful: baja Pose → Face Mesh → escala a proctor.
  - Tests: reglas de transición, no-evento por ruido instantáneo, degradación, abstracción del motor.
- **Dependencias**: `C-10`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/11_ia_y_vision.md` (detectores, reglas, optimización, limitaciones)
  - `knowledge-base/06_funcionalidades.md` §US-006
  - `knowledge-base/05_reglas_de_negocio.md` §RN-EV
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (motor abstraído)

### [C-12] `evidencia-cadena-custodia`
- **Estado**: `[ ]` pendiente
- **Scope**: Captura y cadena de custodia (US-008/US-009, FR-08/FR-09; Flujo 4). Backend core + worker. **Usa el ganador de cola de C-03.**
  - Cliente: evento severo → clip 5–10 s → hash SHA-256 + firma HMAC de sesión → upload directo a storage por **URL firmada**.
  - Backend: valida firma, re-hashea, persiste metadata, deposita en **bucket WORM (Object Lock Compliance)**, escribe audit log.
  - Worker (cola ganadora de C-03): re-descarga, 3.ª verificación de hash, **firma maestra (RSA-2048/Ed25519)**, re-inferencia server-side firmada (4.ª etapa).
  - Discrepancia de hash → evento crítico "evidencia corrupta o manipulada".
  - SLO objetivo: re-inferencia + firma < 30 s desde la subida.
  - Tests: cadena de 4 firmas, WORM inmutable, detección de hash divergente, audit log inmutable, latencia de firma.
- **Dependencias**: `C-10`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §Flujo 4
  - `knowledge-base/06_funcionalidades.md` §US-008 §US-009
  - `knowledge-base/04_modelo_de_datos.md` §Evidencia §Audit log
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-07 §DD-06
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad (cadena de custodia)

### [C-13] `scoring-incremental`
- **Estado**: `[ ]` pendiente
- **Scope**: Cálculo de score de riesgo (US-010, FR-10; Flujo 6). Backend aux.
  - Score incremental vía **continuous aggregate de TimescaleDB** (al minuto): pondera severidad, frecuencia y persistencia; eventos correlacionados pesan más que la suma.
  - Cierre de sesión (`/sessions/{id}/finish`): tarea asíncrona consolida métricas y calcula **score final**; libera la clave de sesión.
  - Si score final > umbral institucional → sesión a cola de revisión (estado flaggeada); si no → archivada.
  - El score **prioriza**, no emite veredicto (ninguna sanción automática).
  - Tests: agregado incremental, correlación, decisión de encolado por umbral, archivado.
- **Dependencias**: `C-10`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-010
  - `knowledge-base/07_flujos_principales.md` §Flujo 6
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SC
  - `knowledge-base/04_modelo_de_datos.md` §Evento (continuous aggregates)

### [C-14] `resiliencia-reconexion`
- **Estado**: `[ ]` pendiente
- **Scope**: Resiliencia de red sin pérdida (US-015, UC-03; Flujo 5). Frontend transport.
  - Buffer **IndexedDB**: eventos persisten localmente si cae el WS.
  - Backoff exponencial + jitter; handshake de reconexión con `last_event_id`; backend reenvía eventos faltantes.
  - Drenaje del buffer en orden, **deduplicación por event_id** (exactly-once lógico).
  - Cortes < 5 min → sin pérdida; cortes > 5 min → evento crítico al reconectar.
  - Tests: replay ordenado, dedup, corte corto sin pérdida, corte largo → evento crítico.
- **Dependencias**: `C-10`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §Flujo 5
  - `knowledge-base/06_funcionalidades.md` §US-015
  - `knowledge-base/05_reglas_de_negocio.md` §RN-HB
  - `knowledge-base/08_arquitectura_propuesta.md` §frontend/transport

### [C-15] `panel-proctor-sse`
- **Estado**: `[ ]` pendiente
- **Scope**: Supervisión en vivo (US-011, FR-11). **Usa el ganador de transporte de C-03 (hipótesis: SSE + backplane).**
  - Panel del proctor vía **SSE** (unidireccional, reconecta solo) alimentado por el backplane; sin sticky sessions (DD-16).
  - Lecturas desde continuous aggregates (CQRS-lite): sesiones priorizadas por **score de riesgo**.
  - Alertas críticas en **< 500 ms** (SLO); mensajería al estudiante, registro de observaciones, **cierre forzado** de sesión.
  - Permisos contextuales (solo exámenes asignados) + MFA.
  - Tests: priorización por score, latencia de alerta < 500 ms, aislamiento por asignación, cierre forzado, reconexión SSE.
- **Dependencias**: `C-10`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-011
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-16 §DD-08
  - `knowledge-base/14_observabilidad_y_devops.md` §SLOs (propagación < 500 ms)
  - `knowledge-base/03_actores_y_roles.md` §Proctor
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (CQRS-lite)

### [C-16] `cola-revision-humana`
- **Estado**: `[ ]` pendiente
- **Scope**: Cola de revisión asíncrona (US-012, FR-12, UC-04; Flujo 7). **Cierre del ciclo MVP.** Requiere C-02 (revisores designados) para cumplir su propósito.
  - Cola ordenada por **score descendente**, filtrada por jurisdicción del revisor.
  - Apertura de sesión: **audit log con propósito declarado**; contexto completo (línea de tiempo de eventos, clips firmados vía URL 15 min, observaciones del proctor, re-inferencia, audit log de accesos previos).
  - Decisión terminal: descartar | escalar | derivar a disciplina; persistida inmutable vinculada a la evidencia.
  - El sistema **nunca sanciona automáticamente** (decisión final humana).
  - Tests: orden por score, aislamiento por jurisdicción, audit de cada apertura, persistencia inmutable de decisión.
- **Dependencias**: `C-15`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-012
  - `knowledge-base/07_flujos_principales.md` §Flujo 7
  - `knowledge-base/03_actores_y_roles.md` §Revisor §RACI
  - `knowledge-base/05_reglas_de_negocio.md` §RN-RV

### [C-17] `dsr-derechos-titular`
- **Estado**: `[ ]` pendiente
- **Scope**: Derechos del titular (US-013, FR-13, UC-05; Flujo 9). Backend aux — paraleliza tras auth.
  - `POST /api/v1/dsr/{type}`: acceso, rectificación, **eliminación** (borra binarios + embeddings, anonimiza registros dejando residual sin datos personales), portabilidad.
  - Verificación de **holds** (casos abiertos difieren la eliminación).
  - Respuesta en plazo legal; operación verificable en auditoría.
  - Tests: eliminación con/ sin holds, anonimización, portabilidad, plazo, trazabilidad en audit log.
- **Dependencias**: `C-06`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-013
  - `knowledge-base/07_flujos_principales.md` §Flujo 9
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §Derechos del titular
  - `knowledge-base/05_reglas_de_negocio.md` §RN-DSR

### [C-18] `verificacion-cadena-apelacion`
- **Estado**: `[ ]` pendiente
- **Scope**: Verificación de evidencia en apelación (UC-06; Flujo 8). Backend core.
  - `POST /api/v1/evidence/{id}/verify-chain`: genera **certificado de verificación** de la cadena de firmas (cliente → backend → worker/clave maestra → re-inferencia).
  - Un perito externo valida la cadena independientemente; cadena rota → no se sostiene, queda registrado.
  - Tests: certificado válido, detección de cadena rota, verificación independiente.
- **Dependencias**: `C-12`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` §Flujo 8
  - `knowledge-base/06_funcionalidades.md` §US-009
  - `knowledge-base/04_modelo_de_datos.md` §Evidencia §Audit log
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §SRFP §trazabilidad

### [C-19] `retencion-holds`
- **Estado**: `[ ]` pendiente
- **Scope**: Retención automática con holds (US-014, FR-14). Backend aux — paraleliza tras exam-config.
  - Aplicación automática de políticas de retención configuradas (clips, embeddings, eventos, audit log, casos); chunks TimescaleDB a Parquet + eliminación de base activa > umbral.
  - **Holds**: casos abiertos extienden la retención automáticamente.
  - Eliminación del embedding al egreso del estudiante.
  - Tests: aplicación de política, hold por caso abierto, archivado de chunks, eliminación al egreso.
- **Dependencias**: `C-07`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-014
  - `knowledge-base/04_modelo_de_datos.md` §Evento (compresión/retención) §Caso disciplinario
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §Retención
  - `knowledge-base/05_reglas_de_negocio.md` §RN-DSR-02

---

## FASE 2 — Refinamiento y analytics

> Depende de producto estable. Otras features diferidas (audio FR-16, integración LMS FR-17, liveness pasivo open-source, ONNX Runtime Web, Redis como backplane) se agregan como changes adicionales cuando el piloto las priorice.

### [C-20] `reportes-analytics`
- **Estado**: `[ ]` pendiente
- **Scope**: Reportes post-examen (US-016, FR-15). Frontend + backend.
  - Reportes por examen y por estudiante; distribución estadística para detectar outliers; métricas de calidad del detector.
  - Exports y sumario institucional.
  - Tests: agregaciones, exports, distribución estadística.
- **Dependencias**: `C-13, C-16`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-016
  - `knowledge-base/14_observabilidad_y_devops.md` §Niveles de métricas
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SC-04

---

## Refinamiento post-fundación — capa frontend/demo y decisiones de producto

> Estos changes (**C-21…C-24**) NO salen del discovery original: se agregaron **después de la fundación**, sobre la capa de presentación de demo (mock en `frontend/src/lib/api.ts`) y como decisiones de producto. Por eso no figuran en el árbol de dependencias de arriba (que es de la fundación).
>
> **Fuente de lectura doble — leé AMBAS:** este índice **y** engram. El detalle completo y el porqué de cada decisión vive en engram → proyecto `activeexam`, topic `activeexam/refinamiento-frontend-v2` (y relacionados `activeexam/fundacion`, `activeexam/frontend`). Si este índice y engram divergen, engram tiene el contexto fino; sincronizá.
>
> ⚠️ **Orden de archive**: los deltas `## MODIFIED Requirements` de C-22 y C-24 modifican specs de C-08/C-09/C-12, que están **aplicados pero NO archivados** (no existe aún el spec canónico en `openspec/specs/`). Antes de `/opsx:archive` de C-21…C-24, **archivá primero C-08/C-09/C-12** para que el MODIFIED resuelva contra la base. (No se archiva nada hasta testear.)

### [C-21] `portal-alumno-materias-inscripcion`
- **Estado**: `[ ]` propuesto (validate --strict OK — 43 tasks)
- **Scope**: Side del alumno sobre la capa de demo (sin backend). Login → **dashboard del alumno**; modela **Materia→Comisión→Examen** (hoy solo existe `catedra:string`); **inscripción** a exámenes + "Mis exámenes" (registro con estado y acción siguiente); pantalla de **perfil (shell)** con el gate `puedeRendir`. Caps NEW: student-dashboard-landing, student-portal-navigation, exam-enrollment, student-profile-shell.
- **Dependencias**: `C-07` (exámenes contra los que inscribirse); el contenido del perfil (consentimiento+biometría) lo completa `C-22`
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-21-portal-alumno-materias-inscripcion/` (proposal, design, tasks, specs)
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/06_funcionalidades.md` §US-001 §US-003

### [C-22] `perfil-biometrico-enrollment`
- **Estado**: `[ ]` propuesto (validate --strict OK — 21 tasks)
- **Scope**: **Enrollment único en el perfil** (reutilizable, con renovación): consentimiento informado (**reorden desde C-08** — se da en el perfil, no antes de rendir) + **escaneo biométrico de referencia** + imagen de referencia guardada + **escaneo DNI opcional/flaggeado** + **renovación cada 24 meses** (configurable), con la verificación silenciosa continua gatillando renovación anticipada por deriva del embedding. Caps NEW: student-profile-enrollment, biometric-reference-renewal, optional-dni-scan. **MODIFICA** (deltas dentro del change): `consent-gate`, `informed-consent-presentation` (C-08), `embedding-computation`, `biometric-custody-encryption` (C-09).
- **Dependencias**: `C-21` (perfil shell + gate), `C-08`, `C-09` (specs que modifica)
- **Governance**: ALTO
- **Pregunta abierta (legal)**: ¿se necesita acuse de consentimiento **por-examen** además del de perfil? Hipótesis: el de perfil alcanza mientras la versión de texto no cambie. Validar con legal antes de cerrar el gate. (Detalle en el design del change.)
- **Leer antes**:
  - `openspec/changes/c-22-perfil-biometrico-enrollment/` (incl. la pregunta abierta en design.md)
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/12_biometria_y_liveness.md`, `13_legal_y_cumplimiento_argentina.md`, `05_reglas_de_negocio.md` §RN-CO

### [C-23] `admin-mediapipe-test-harness`
- **Estado**: `[ ]` propuesto (validate --strict OK — 30 tasks)
- **Scope**: **Página admin diagnóstica** que corre el pipeline de visión del cliente **end-to-end como alumno de prueba** (VisionEngine/MediaPipe + visionPipeline + stateTransitionRules + EventSink) y **verifica que se registran** las detecciones y eventos. Reusa el cableado de C-11; corre con la cámara del propio admin, sin examen real ni sanción. Caps NEW: admin-detection-test-harness, detection-event-verification.
- **Dependencias**: `C-11` (vision-engine), `C-10` (event-transport)
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-23-admin-mediapipe-test-harness/`
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/11_ia_y_vision.md`

### [C-24] `evidencia-screenshots`
- **Estado**: `[ ]` propuesto (validate --strict OK — 15 tasks)
- **Scope**: ⚠️ **Decisión de arquitectura** — la evidencia pasa de **CLIPS (5–10s) a SCREENSHOTS** (captura **event-driven + heartbeat** de baja frecuencia), por costo y proporcionalidad L2.5. El DD documenta el tradeoff honesto: una foto fija **no permite re-inferencia temporal ni re-verificación de liveness/movimiento**; cadena de custodia **intacta** (hash+firma cliente → re-firma server-side → WORM). Caps NEW: screenshot-evidence-capture, evidence-capture-cadence. **MODIFICA** `evidence-capture` (C-12) y `RN-CC-01`; impacta el modelo de costo (`14`) y la re-inferencia (`11`).
- **Dependencias**: `C-12` (evidencia-cadena-custodia)
- **Governance**: ALTO
- **Leer antes**:
  - `openspec/changes/c-24-evidencia-screenshots/` (DD-24-01/02/03)
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CC, `11_ia_y_vision.md`, `14_observabilidad_y_devops.md`

### [C-25] `captura-actividad-integral`
- **Estado**: `[ ]` propuesto (validate --strict OK)
- **Scope**: ⭐ **Base funcional** — captura y registro de TODA la actividad sospechosa (**visión + navegador/entorno**) + **página de validación end-to-end** para probarlo con la propia persona. Implementa los detectores de navegador que faltan (**cambio/apertura de pestaña**, **salida de pantalla completa**, **copy/paste**), **cablea el detector de monitores múltiples** (hoy hardcodeado `false` en `Examen.tsx:77` y `AdminDetectionHarness.tsx:376`), y **extiende la página de testeo de C-23** para validar también lo de navegador, con checklist de cobertura. Reusa el pipeline existente (`stateTransitionRules` → `EventSink`); el sistema no sanciona automático, cliente = sensor no confiable. Caps NEW: browser-activity-detectors, suspicious-activity-catalog, integral-activity-validation. **MODIFICA** (deltas dentro del change): `state-transition-rules`, `browser-context-detectors` (C-11), `admin-detection-test-harness` (C-23).
- **Dependencias**: `C-10` (event-schema-contract), `C-11` (vision-engine-detectores), `C-23` (harness)
- **Governance**: ALTO
- **Leer antes**:
  - `openspec/changes/c-25-captura-actividad-integral/` (proposal, design con inventario existe/falta, tasks, specs)
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/11_ia_y_vision.md`, `05_reglas_de_negocio.md` §RN-EV

### [C-26] `acuse-consentimiento-por-examen`
- **Estado**: `[ ]` propuesto (validate --strict OK)
- **Scope**: **Consentimiento EN CAPAS** — resuelve la pregunta legal abierta de C-22. Agrega un **acuse liviano por-examen** al inscribirse a un examen concreto: muestra el examen + qué se monitorea, con una acción afirmativa que da **finalidad específica** a esa instancia de tratamiento (Ley 25.326), **referenciando** el consentimiento de perfil de C-22 (no re-pide biometría ni el texto pesado). Acuse inmutable por `(estudiante, examen)` (versión+timestamp+hash, demo). Gate de habilitación = perfil completo (C-22) **Y** acuse por-examen (código nuevo `acuse_examen_faltante`). Caps NEW: per-exam-consent-acknowledgment. **MODIFICA** (deltas dentro del change): `exam-enrollment` (C-21), `consent-gate` (C-22).
- **Dependencias**: `C-21` (inscripción), `C-22` (consentimiento de perfil + gate)
- **Governance**: ALTO
- **Leer antes**:
  - `openspec/changes/c-26-acuse-consentimiento-por-examen/`
  - **engram** `activeexam/refinamiento-frontend-v2`
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md`, `05_reglas_de_negocio.md` §RN-CO

### [C-27] `branding-utn-frm`
- **Estado**: `[ ]` propuesto (validate --strict OK — 17 tasks)
- **Scope**: **Corrección de identidad institucional** — elimina las 13 referencias hardcodeadas a "UBA" / "Universidad de Buenos Aires" y crea un **módulo central de configuración** `frontend/src/config/institution.ts` desde el cual toda la UI y los mocks leen la identidad de UTN Regional Mendoza (FRM). Reemplaza además materias de Medicina (Anatomía, Fisiología, etc.) por materias canónicas del CBU de Ingeniería UTN. Soporte de override por `VITE_INSTITUTION_*` para futura multi-tenancy. Caps NEW: `institution-config`.
- **Dependencias**: ninguna (solo strings y datos mock del frontend; independiente de todos los changes de backend)
- **Governance**: BAJO
- **Leer antes**:
  - `openspec/changes/c-27-branding-utn-frm/` (proposal, design, specs/institution-config/spec.md, tasks)
  - `knowledge-base/03_actores_y_roles.md` §Actores (institución/roles)

### [C-28] `lenguaje-claro-glosario`
- **Estado**: `[ ]` propuesto (validate --strict OK — 38 tasks)
- **Scope**: **Inteligibilidad de la UI** — la interfaz repite 19× "L2.5", 4× "embedding", y múltiples "WORM", "liveness", "cadena de custodia", "Face Mesh" sin explicación. C-28 agrega **definiciones en lenguaje claro accesibles en contexto** (tooltips + panel de glosario), SIN eliminar la terminología técnica (necesaria legal y técnicamente). Crea el diccionario central `frontend/src/config/glossary.ts` (mismo patrón que `institution.ts` de C-27) y el componente átomo `<Term>` (tooltip accesible, responsive, sin dependencias externas). Caps NEW: `glossary-config`, `term-tooltip-component`, `glossary-panel`. Cap MODIFIED (delta): `institution-config` (formaliza la convención de la carpeta `config/`).
- **Dependencias**: ninguna (100 % capa de presentación; independiente de todos los changes de backend; puede correr en cualquier momento como C-27)
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-28-lenguaje-claro-glosario/` (proposal, design, specs/, tasks)
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §embedding §dato sensible §Ley 25.326
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CO (consentimiento informado con lenguaje claro)
  - **engram** `activeexam/refinamiento-frontend-v2`

### [C-29] `ux-admin-harness-legible`
- **Estado**: `[ ]` propuesto (validate --strict OK — 30 tasks)
- **Scope**: **Densidad visual y honestidad del harness** — mejora de experiencia y claridad en las pantallas más técnicas/densas, sin cambiar funcionalidad. (1) Banner prominente en el harness de diagnóstico admin que advierte que las **señales de visión son SIMULADAS** (motor MediaPipe en stub); (2) panel de propósito del harness en lenguaje no técnico; (3) tarjetas de interpretación por señal con accordion de datos técnicos crudos colapsable; (4) descripción contextual por cada señal de entorno; (5) respiro visual en la tabla de eventos de Revisor + agrupación de eventos repetidos; (6) cadena de custodia colapsable en SessionDetail con hashes truncados; (7) **reframe del copy de Login** como portal del alumno (headline "Portal del alumno"). Caps NEW: `harness-legibility-layer`, `login-portal-reframe`. Caps MODIFIED (delta): `admin-detection-test-harness` (C-23), `glossary-config` (C-28 — 4 términos nuevos: `bounding_box`, `gaze_vector`, `pose_keypoints`, `motor_stub`).
- **Dependencias**: `C-27` (INSTITUTION), `C-28` (Term, glossary.ts). Independiente de backend.
- **Governance**: BAJO
- **Leer antes**:
  - `openspec/changes/c-29-ux-admin-harness-legible/` (proposal, design, specs/, tasks)
  - `openspec/changes/c-28-lenguaje-claro-glosario/` (patrón Term + glossary.ts)
  - `knowledge-base/11_ia_y_vision.md` §Motor abstraído §stub MediaPipe
  - **engram** `activeexam/refinamiento-frontend-v2`

### [C-30] `vision-real-harness`
- **Estado**: `[ ]` propuesto (validate --strict OK — 34 tasks)
- **Scope**: **Motor de visión MediaPipe REAL en el harness de diagnóstico** — cablea `@mediapipe/tasks-vision` Tasks API (FaceDetector + FaceLandmarker 468 landmarks/iris + PoseLandmarker) **únicamente en el harness** `/admin/detection-test`, para que el admin vea detecciones reales: múltiples rostros, gaze real, pose real. El flujo de examen sigue con señales simuladas, sin cambios. Agrega **overlay canvas** sobre el video con bounding boxes y landmarks para visualizar en tiempo real qué detecta la cámara. Los modelos `.task` se sirven **localmente** (`frontend/public/mediapipe/`) nunca desde CDN externo (soberanía de datos). Cargados con **import dinámico (lazy)** para no inflar el bundle inicial. **Actualiza el banner de C-29** haciéndolo condicional: `SIMULADO` / `CARGANDO` / `VISIÓN REAL (MediaPipe)` / `ERROR DE CARGA`. Fallback honesto: error explícito en UI si los modelos no cargan. Caps NEW: `real-vision-engine-harness`, `vision-overlay-canvas`, `harness-model-loader`. Caps MODIFIED (delta): `harness-legibility-layer` (C-29 — banner condicional), `admin-detection-test-harness` (C-23 — señales reales).
- **Dependencias**: `C-23` (harness base), `C-25` (pipeline completo con detectores de entorno), `C-29` (banner legibilidad)
- **Governance**: ALTO
- **Leer antes**:
  - `openspec/changes/c-30-vision-real-harness/` (proposal, design, specs/, tasks)
  - `openspec/changes/c-23-admin-mediapipe-test-harness/` (harness base)
  - `openspec/changes/c-29-ux-admin-harness-legible/` (banner que se modifica)
  - `knowledge-base/11_ia_y_vision.md` §Detectores §Ejecución y optimización §DD-17
  - `knowledge-base/13_legal_y_cumplimiento_argentina.md` §Soberanía de datos
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-17

### [C-31] `quick-fixes-header-login`
- **Estado**: `[x]` aplicado (9/9 tasks, tsc --noEmit 0 errores)
- **Scope**: **2 quick-fixes de presentación** — (1) Elimina el badge "Self-hosted · {institución}" del header de la shell de staff (`shells.tsx`): era jerga de infraestructura irrelevante para el usuario final; el nombre institucional ya aparece en la sidebar. (2) Elimina el link "Requisitos técnicos" del nav del login (`Login.tsx`): la ruta `/requisitos` lleva al flujo demo de EquipmentCheck, causando confusión al alumno que intenta autenticarse. Se elimina también el separador visual (`<span>` bullet) que quedaba huérfano. La ruta `#/requisitos` permanece definida en `App.tsx` para uso futuro. Caps MODIFIED (delta): `staff-shell-header`, `login-screen`.
- **Dependencias**: ninguna (solo JSX estático de presentación)
- **Governance**: BAJO
- **Leer antes**:
  - `openspec/changes/c-31-quick-fixes-header-login/` (proposal, design, specs/, tasks)
  - `frontend/src/ui/shells.tsx` (header de staff)
  - `frontend/src/screens/Login.tsx` (nav del login)

### [C-32] `harness-motor-cache-ux`
- **Estado**: `[ ]` propuesto (validate --strict OK — 29 tasks)
- **Scope**: **4 mejoras al harness `/admin/detection-test`** — (1) **Cache del motor WASM**: `harnessEngineLoader.ts` cachea la instancia de `RealMediaPipeVisionEngine` ya inicializada a nivel módulo; los ciclos Iniciar/Detener posteriores reutilizan el motor sin recargar WASM (~25–50 MB). Nuevo export `disposeRealEngine()` para limpieza explícita al navegar fuera. (2) **Spinner amigable**: el banner de estado `'loading'` reemplaza la jerga técnica ("WASM", "MediaPipe", "MB") por spinner animado + "Preparando la cámara…" para personal no técnico. (3) **Labels de umbrales en lenguaje claro**: los 5 campos de configuración (`face_absent_ms`, `multiple_faces_frames`, `gaze_deviation_threshold`, `gaze_sustained_ms`, `gaze_fixation_tolerance`) muestran nombres en español comprensible con la clave técnica como referencia secundaria. (4) **Flujo de permiso Window Management**: botón "Detectar pantallas" que solicita el permiso `window-management` con gesto del usuario, con mensajería clara para los casos `unsupported`, `denied` y `granted`. Caps NEW: `harness-engine-cache`, `harness-loading-ux`, `harness-threshold-labels`, `window-management-permission-flow`. Caps MODIFIED (delta): `harness-model-loader` (C-30), `admin-detection-test-harness` (C-23), `browser-context-detectors` (C-25).
- **Dependencias**: `C-23` (harness base), `C-25` (detectores de contexto), `C-29` (banner legibilidad), `C-30` (motor real + loader)
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-32-harness-motor-cache-ux/` (proposal, design, specs/, tasks)
  - `frontend/src/vision/harnessEngineLoader.ts` (loader actual a modificar)
  - `frontend/src/screens/AdminDetectionHarness.tsx` (harness: banner ~695, umbrales ~1158, monitor polling ~340)
  - `frontend/src/proctoring/contextDetectors.ts` (detectExtraMonitor a extender)
  - `frontend/src/ui/Term.tsx` (componente Term de C-28, reutilizable para claves técnicas)

### [C-33] `medidor-riesgo-harness`
- **Estado**: `[ ]` propuesto (validate --strict OK — 20 tasks)
- **Scope**: **Medidor de riesgo en vivo en el harness de diagnóstico** — (1) **Medidor/gauge de riesgo**: barra de progreso con color escalado (verde→amarillo→rojo) que muestra el % de riesgo acumulado en tiempo real, sumando el peso (`PESO_SCORE`) de cada evento emitido durante la sesión de diagnóstico. (2) **Botón RESET del medidor**: resetea el score acumulado a 0 sin interrumpir cámara ni motor. (3) **Umbral configurable**: input numérico (1–100 %) que, cuando es superado, muestra un banner "Superaría el umbral — priorizaría para revisión humana" (semántica L2.5 — prioriza, no sanciona). (4) **Extracción de `PESO_SCORE` a módulo compartido**: `frontend/src/proctoring/riskWeights.ts` elimina la duplicación entre `Examen.tsx` y `AdminDetectionHarness.tsx` (valores sin cambio). El acumulador de riesgo vive en estado local del componente, aislado del `store.scorePropio` del alumno real. Caps NEW: `harness-risk-meter`. Caps MODIFIED (delta): `admin-detection-test-harness` (C-23).
- **Dependencias**: `C-23` (harness base), `C-25` (pipeline de eventos y `PESO_SCORE` existente en Examen), `C-32` (estado actual del harness)
- **Governance**: BAJO
- **Leer antes**:
  - `openspec/changes/c-33-medidor-riesgo-harness/` (proposal, design, specs/, tasks)
  - `frontend/src/screens/Examen.tsx` (línea 27: `PESO_SCORE` a extraer)
  - `frontend/src/screens/AdminDetectionHarness.tsx` (sink callback, estado local, layout)
  - `frontend/src/lib/store.ts` (scorePropio — no se toca, solo referencia)

### [C-34] `biometria-perfil-funcional`
- **Estado**: `[ ]` propuesto (validate --strict OK — 37 tasks)
- **Scope**: **Captura biométrica del perfil FUNCIONAL para test** — hace que el enrollment biométrico del alumno deje de ser mock y pase a usar detección real: (1) **Retos de liveness detectados de verdad** con el motor MediaPipe real (`RealMediaPipeVisionEngine`) frame-a-frame: girar izquierda/derecha (gaze), parpadear (cierre ocular), acercarse (bounding box), sonreír (comisuras de boca). (2) **Embedding REAL** derivado con `embeddingFromLandmarks(landmarks)` (determinista, no `Math.random`). (3) **Fullscreen en móvil** al tomar la cámara: `requestFullscreen()` sobre el contenedor, con fallback CSS `fixed inset-0` para iOS Safari. (4) **Loader lazy con singleton** `enrollmentEngineLoader.ts` — mismo patrón que `harnessEngineLoader.ts` pero con ciclo de vida independiente; motor WASM sigue fuera del bundle inicial. Fallback manual (modo botón) visible solo cuando el motor no puede cargar. Cliente sigue siendo SENSOR NO CONFIABLE (RN-GLB-01); la verificación real es server-side (C-12). Caps NEW: `enrollment-liveness-detection`, `enrollment-fullscreen-mobile`. Caps MODIFIED (delta): `harness-model-loader` (C-30/C-32 — nuevo loader paralelo).
- **Dependencias**: `C-22` (paso biométrico del perfil que se hace funcional), `C-30` (motor real y helpers `embeddingFromLandmarks`, `gazeFromIris` disponibles), `C-32` (patrón de loader lazy singleton ya establecido en `harnessEngineLoader.ts`)
- **Governance**: ALTO
- **Leer antes**:
  - `openspec/changes/c-34-biometria-perfil-funcional/` (proposal, design, specs/, tasks)
  - `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` (componente a refactorizar)
  - `frontend/src/vision/liveness.ts` (lógica pura de retos a reusar)
  - `frontend/src/vision/harnessEngineLoader.ts` (patrón de singleton a replicar)
  - `knowledge-base/12_biometria_y_liveness.md` (liveness híbrido, thresholds, ISO 30107-3)

### [C-35] `fixes-deteccion-camara-mirada`
- **Estado**: `[ ]` propuesto (validate --strict OK — 18 tasks)
- **Scope**: **2 bugs del harness `/admin/detection-test`** — (1) **Bug 1 — Cámara trabada al volver a la página**: al navegar fuera y volver, el `<video>` muestra un frame congelado de la sesión anterior. Fix: en `startHarness()` limpiar `srcObject = null` + `load()` ANTES de asignar el nuevo stream; en el `useEffect` cleanup también limpiar `srcObject`. (2) **Bug 2 — Mirada sostenida floja / riesgo no sube**: `gaze_deviation_threshold: 0.6` es inalcanzable para el vector iris (rango real ~0.15–0.35) y `gaze_fixation_tolerance: 0.15` reinicia el ancla por movimiento natural. Fix: recalibrar `DEFAULT_CONFIG` a `gaze_deviation_threshold: 0.25`, `gaze_sustained_ms: 2500`, `gaze_fixation_tolerance: 0.25`; promediar ambos iris en `detectFaceMesh()`; agregar `head_yaw_deg?` en `FrameSignals` para usar head pose (PoseSignal) como señal complementaria. Caps MODIFIED (deltas): `admin-detection-test-harness`, `state-transition-rules`, `real-vision-engine-harness`.
- **Dependencias**: `C-23` (harness base), `C-25` (pipeline + FrameSignals), `C-30` (motor real + RealMediaPipeVisionEngine), `C-32` (cache motor + disposeRealEngine), `C-33` (medidor de riesgo que se beneficia del fix Bug 2)
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-35-fixes-deteccion-camara-mirada/` (proposal, design, specs/, tasks)
  - `frontend/src/screens/AdminDetectionHarness.tsx` (~502–507 startHarness cámara; ~632–663 stopHarness + cleanup)
  - `frontend/src/proctoring/stateTransitionRules.ts` (~76–82 DEFAULT_CONFIG; ~169–203 evalGaze)
  - `frontend/src/vision/RealMediaPipeVisionEngine.ts` (~243–278 detectFaceMesh + gazeFromIris)
  - `frontend/src/ui/VisionOverlay.tsx` (canvas + clearRect)

### [C-36] `c-36-verificacion-biometrica-inmersiva`
- **Estado**: `[ ]` propuesto (validate --strict OK — 36 tasks)
- **Scope**: **Componente compartido de captura biométrica inmersiva** para el examen (pre-rendición) y el perfil (enrollment). Elimina el mock de botones de `Biometria.tsx` y la duplicación de UI/loop con `EnrollmentBiometricStep.tsx`. (1) **`BiometricCapture` nuevo** (`frontend/src/ui/BiometricCapture.tsx`): encapsula cámara (getUserMedia), loop RAF real (`evaluateChallenge`, `framesMinForChallenge`), motor lazy (`loadEnrollmentEngine`/`disposeEnrollmentEngine`), UI inmersiva (`fixed inset-0 z-50`, óvalo dominante, paso actual abajo, progreso de retos), fallback manual, `requestFullscreen()` best-effort. (2) **Refactor `Biometria.tsx`**: reemplaza mock de botones por `<BiometricCapture>` en fase `capturando`; detección real de liveness; `handleComplete(landmarks)` calcula embedding y llama `verificar()`. (3) **Refactor `EnrollmentBiometricStep.tsx`**: delega la captura a `<BiometricCapture>`; elimina `startDetectionLoop`, `engineRef`, `challengeCountsRef` y UI inline de retos; mantiene encabezado contextual, nota de privacidad Ley 25.326 y callback `onCapturada`. Caps: NEW `biometric-capture-component`; MODIFIED `exam-enrollment`, `student-profile-shell`.
- **Dependencias**: `C-34` (motor lazy singleton, evaluador de retos, fallback manual, loop RAF — reutilizados sin cambio)
- **Governance**: MEDIO
- **Leer antes**:
  - `openspec/changes/c-36-verificacion-biometrica-inmersiva/` (proposal, design, specs/, tasks)
  - `frontend/src/screens/Biometria.tsx` (mock a reemplazar)
  - `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` (loop RAF + fullscreen a extraer)
  - `frontend/src/vision/enrollmentEngineLoader.ts` (reutilizar sin cambio)
  - `frontend/src/vision/enrollmentChallengeDetector.ts` (reutilizar sin cambio)
  - `frontend/src/vision/liveness.ts` (ACTIVE_CHALLENGES, pickActiveChallenges)
  - `knowledge-base/12_biometria_y_liveness.md` (liveness híbrido, thresholds, ISO 30107-3)

---

## Resumen

| Fase | Changes | Governance |
|------|---------|-----------|
| **0 — Fundaciones** | C-01, C-02, C-03 | 3× CRITICO (C-03 ★ Tier 1 BLOQUEANTE) |
| **1 — MVP** | C-04…C-19 | 6 CRITICO, 8 ALTO, 2 MEDIO |
| **2 — Refinamiento** | C-20 | 1 MEDIO |
| **Refinamiento post-fundación** | C-21, C-22, C-23, C-24, C-25, C-26, C-27, C-28, C-29, C-30, C-31, C-32, C-33, C-34, C-35, C-36 | 6 ALTO, 6 MEDIO, 4 BAJO |

- **Total**: **36 changes** — 20 de la fundación (3 fases) + 16 post-fundación (capa frontend/demo, captura de actividad, consentimiento en capas, decisiones de producto, identidad institucional, lenguaje claro/glosario, UX/legibilidad del harness, motor de visión real en el harness, quick-fixes de presentación, harness cache UX, medidor de riesgo en harness, biometría perfil funcional, fixes detección cámara/mirada, verificación biométrica inmersiva, ver sección dedicada arriba).
- **Camino crítico**: 11 changes (`C-01 → C-03 → C-04 → C-05 → C-06 → C-07 → C-08 → C-09 → C-10 → C-15 → C-16`). C-21…C-36 quedan **fuera** del camino crítico (refinamiento de demo, no MVP backend).
- **Gates de paralelismo**: 13 (GATE 0…GATE 12). Forks grandes en GATE 5, GATE 6 y GATE 9.
- **Primer change recomendado**: `C-01` (acuerdo-proctoring-dpia) — gate legal que junto a `C-02` bloquea todo el desarrollo. El primer change de **código** es `C-03` (poc-carga-mensajeria, Tier 1, BLOQUEANTE).
- **Post-fundación**: el detalle y el porqué viven también en **engram** (`activeexam/refinamiento-frontend-v2`). Orden de aplicación sugerido: **C-21 → C-22 → C-26** (perfil cuelga del portal; el acuse por-examen de C-26 cuelga de la inscripción de C-21 + el consentimiento de C-22); **C-23 → C-25** (C-25 extiende el harness y cablea los detectores de navegador); C-24 independiente; **C-27 → C-28 → C-29 → C-30 → C-32 → C-33 → C-34 → C-35 → C-36 pueden correr en secuencia** (C-28 inteligibilidad; C-29 legibilidad/banner; C-30 motor real en el harness con overlay canvas; C-32 cache + UX amigable del harness; C-33 medidor de riesgo en harness; C-34 biometría perfil funcional; C-35 fixes bugs detección cámara + mirada; C-36 verificación biométrica inmersiva con componente compartido).

Para arrancar: `/opsx:propose C-01-acuerdo-proctoring-dpia`
