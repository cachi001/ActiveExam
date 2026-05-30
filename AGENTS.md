# Proctoring — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` (16 archivos) y `CHANGES.md` (20 changes). No editar a mano sin re-sincronizar ambos archivos.
>
> **Proyecto**: Plataforma propia **self-hosted** de proctoring **nivel L2.5** (análisis en navegador + verificación biométrica + anti-tampering pasivo) para supervisar evaluaciones universitarias remotas a escala, con **soberanía de datos** completa, **evidencia con cadena de custodia criptográfica** y **decisión disciplinaria siempre humana**.

---

## Stack Tecnológico

> Copiado de [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) §Stack tecnológico. **OJO**: la fuente describe DOS arquitecturas — el SAD original (RabbitMQ+Redis+Celery, WebSocket+sticky) y la recomendada A4 (Postgres-como-cola, SSE, motor abstraído). El MVP sigue A4; promover piezas del SAD requiere que **C-03 (PoC de carga)** lo exija con métricas. Ver regla dura de dominio #4.

| Capa | Tecnologías | Notas |
|------|-------------|-------|
| Frontend | React + Vite + Zustand + Tailwind | Bundle inicial objetivo < 500 KB |
| IA en cliente | MediaPipe (Face Detection, Face Mesh 468 landmarks, Pose) sobre WASM + WebGL, en Web Worker | Motor **abstraído** detrás de interfaz; ruta a ONNX Runtime Web (DD-17) |
| Captura multimedia | getUserMedia, Screen Capture API | — |
| Buffer cliente | IndexedDB (buffer circular, reenvío ordenado con `last_event_id`) | — |
| Reverse proxy / TLS | Nginx (TLS 1.3, HSTS+preload, OCSP stapling) | — |
| API y tiempo real | FastAPI (ASGI/uvicorn), REST `/api/v1` + WebSocket (estudiante) + SSE (panel) | OpenAPI auto, validación Pydantic |
| Identidad | Keycloak (OAuth2 / OIDC / SAML), MFA | Federado con directorio institucional, JIT provisioning |
| Datos de dominio | PostgreSQL | Consistencia transaccional |
| Series temporales | TimescaleDB (extensión Postgres) | Hypertables, compresión, continuous aggregates |
| Caché / fan-out | Redis (caché, Pub/Sub) | En A4: opcional, solo si el dato lo justifica |
| Cola de trabajos (MVP) | **Postgres-como-cola** (pg-boss / SKIP LOCKED + LISTEN/NOTIFY) | Hipótesis default A4. RabbitMQ+Celery (SAD) **solo si C-03 lo exige** |
| Mensajería crítica (escala) | RabbitMQ (quorum queues) + Celery | SAD — destino de escala, NO asumir antes de C-03 |
| Evidencia | MinIO / S3 con Object Lock (WORM), cifrado at-rest, versionado | Abstracción storage |
| Secretos | HashiCorp Vault (o secret manager cloud) | Inyección en tmpfs efímero; nunca en código/imágenes |
| Observabilidad | Prometheus, Loki, Tempo/OpenTelemetry, Grafana | Desde el día uno ("ciudadano de primera clase") |
| Migraciones | Alembic (destructivas en dos pasos) | — |
| Orquestación | Docker Compose (inicial) → Kubernetes (escala) | Código twelve-factor |
| CI/CD | GitLab CI o GitHub Actions | Tag inmutable por hash de commit; deploy a prod con doble aprobación |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) · [knowledge-base/08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md)

---

## Base de Conocimiento (Mapa de Navegación)

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.** Índice completo en [knowledge-base/README.md](knowledge-base/README.md).

### Canónicos (obligatorios)

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0 |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura (SAD vs A4), integraciones, API |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC contextual, 7 roles, rutas públicas |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, hypertable de eventos, audit log |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas (RN-AU, RN-BIO, RN-EV, RN-SC, RN-CC, RN-RV, RN-DSR…) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica (FR-01…FR-18, UC-01…UC-06) |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E con diagramas de secuencia |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Patrones, estructura de directorios, seguridad, env vars, dimensionamiento |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | ADR-0001…0014 + revisiones A4 (DD-15…DD-19), supuestos |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Inconsistencias SAD vs A4 + preguntas abiertas a resolver ANTES de codear |

### Extras (complementan, no reemplazan)

| Archivo | Cuándo leerlo |
|---------|---------------|
| [11_ia_y_vision.md](knowledge-base/11_ia_y_vision.md) | Detectores MediaPipe, eventos discretos, re-inferencia, ONNX |
| [12_biometria_y_liveness.md](knowledge-base/12_biometria_y_liveness.md) | Verificación 1:1, liveness híbrido, ISO 30107-3, deepfakes/inyección |
| [13_legal_y_cumplimiento_argentina.md](knowledge-base/13_legal_y_cumplimiento_argentina.md) | Ley 25.326, AAIP, embeddings sensibles, DPIA, caso SRFP |
| [14_observabilidad_y_devops.md](knowledge-base/14_observabilidad_y_devops.md) | Tres pilares, SLI/SLO, runbooks, capacity model, CI/CD, backups/DR |
| [15_roadmap_y_riesgos.md](knowledge-base/15_roadmap_y_riesgos.md) | Roadmap por fases, registro de riesgos, gestión del cambio |

> ⚠️ **Antes de arrancar el primer change**, resolvé las preguntas de prioridad **Alta** de [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md): firma del acuerdo+DPIA, mensajería del MVP (post-PoC), designación de revisores, foto de referencia institucional y lista canónica de rutas públicas.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 20 changes en 3 fases (Fundaciones / MVP / Refinamiento).
- **Camino crítico** (11 changes): `C-01 → C-03 → C-04 → C-05 → C-06 → C-07 → C-08 → C-09 → C-10 → C-15 → C-16`.
- **Gates de paralelismo**: 13 (GATE 0…GATE 12). Forks grandes en GATE 5, GATE 6 y GATE 9.
- **Primer change**: `C-01` (`acuerdo-proctoring-dpia`) — gate legal. El primer change de **código** es `C-03` (`poc-carga-mensajeria`, Tier 1, BLOQUEANTE).

### Gates bloqueantes (Fase 0 — bloquean TODO el desarrollo)

- **C-01** `acuerdo-proctoring-dpia` — Acuerdo de Nivel de Proctoring firmado + DPIA completo + 14 ADRs aprobados. **CRITICO, no-código.**
- **C-02** `designacion-revisores` — Revisores humanos designados y capacitados. **La dependencia más subestimada del proyecto (SU-03).** CRITICO, no-código.
- **C-03** `poc-carga-mensajeria` ★ Tier 1 — PoC de carga al **pico (~2.100 concurrentes / ~5.000 inserts/s)** que **decide la arquitectura** de cola/transporte/backplane. **BLOQUEA todo lo de cola/transporte/tiempo real.**

> Sin C-01 y C-02 en `[x]` no se toca código de dominio. Sin C-03 en `[x]` no se asume ninguna arquitectura de mensajería.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change (no arranques uno con dependencias en `[ ]`) y los archivos de "Leer antes".

---

## Reglas Duras de Dominio (no negociables — vienen de decisiones ya tomadas)

Estas reglas son **contrato del proyecto Proctoring**. Romperlas es un defecto.

1. **NFR de capacidad: 1.000 concurrentes sostenido / ~2.100 pico.** Nunca dimensionar para 700 (cifra superada en el discovery). La PoC C-03 se clava al **pico** (~2.100 concurrentes / ~5.000 inserts/s), no al sostenido.
2. **Flujo de trabajo obligatorio: OpenSpec/OPSX.** Todo cambio pasa por `/opsx:propose → /opsx:apply → /opsx:archive`. El orden de los changes y sus gates están en [CHANGES.md](CHANGES.md). No se codea fuera de un change.
3. **C-01 y C-02 son gates bloqueantes previos a TODO desarrollo. C-03 bloquea todo lo de cola/transporte/tiempo real.** Respetar el árbol de dependencias de CHANGES.md.
4. **La arquitectura de mensajería/transporte NO está cerrada — la decide C-03.** Hipótesis default A4 = **Postgres-como-cola + SSE + LISTEN/NOTIFY**; el SAD (RabbitMQ+Celery+WebSocket+sticky+Redis) entra **solo si la métrica de C-03 lo exige**. **Ningún agente asume una u otra antes de C-03.**
5. **El sistema NUNCA sanciona automáticamente (L2.5).** Flaggea y produce evidencia; el score **prioriza**, no emite veredicto. La decisión disciplinaria es **siempre humana** (revisión asíncrona).
6. **Cliente = sensor no confiable.** Toda evidencia se **re-hashea, re-infiere y firma server-side** (cadena de custodia: cliente → backend → worker/clave maestra → re-inferencia). El backend nunca confía en el dato crudo del cliente.
7. **Cumplimiento Ley 25.326 (Argentina) + DPIA.** Privacidad por diseño; el **embedding se trata como dato sensible por defecto** ("responsabilidad reforzada"). Eliminación del embedding al egreso; holds difieren la eliminación.

---

## Reglas Duras de Código (no negociables)

Estas reglas son **contrato técnico**. Romperlas es un defecto, no una decisión de estilo.

1. **No buildear automático.** Nunca ejecutar build/compile/bundle sin pedido explícito del usuario.
2. **No commitear sin pedido explícito.** `git add`/`commit`/`push` SOLO cuando el usuario lo pide. Si estás en la rama default, ramificá antes.
3. **Conventional Commits sin `Co-Authored-By`.** Formato `tipo(scope): mensaje` (feat, fix, chore, refactor, test, docs). JAMÁS agregar atribución a IA ni `Co-Authored-By`.
4. **Tests sin mocks de DB.** Usar base real o contenedor de test (testcontainers / DB efímera). Mockear la base de datos invalida el test — no prueba nada.
5. **Pydantic schemas con `extra='forbid'`.** Todo schema rechaza campos no declarados (`model_config = ConfigDict(extra='forbid')`).
6. **snake_case en Python.** Funciones, variables, columnas de BD, módulos y paquetes.
7. **PascalCase en componentes React.** Nombre del componente y del archivo (`ProctorPanel.tsx`).

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y gates
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (instalando skills)     → respetando TODAS las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change y desbloquear gates
```

Aplicar TODAS las reglas duras (dominio + código) en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen. Ante conflicto sobre arquitectura de mensajería antes de C-03, **no asumir**: la decisión la toma la PoC.
