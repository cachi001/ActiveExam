# CHANGES — Roadmap de pendientes

> Índice **solo de lo que falta** del proyecto **Proctoring** (plataforma self-hosted de supervisión asistida por IA de evaluaciones remotas).
> Regenerado el **2026-06-11** (sesión 2, post-c-39) a partir del estado real del CLI de OpenSpec (`openspec list --json`), tras higiene masiva: 6 archivados + **4 cancelados** + 1 sincronizado desde rama + 26 specs canónicas regeneradas.
> El plan original completo (los 65 changes, hechos y pendientes) quedó archivado en **[CHANGES.legacy.md](CHANGES.legacy.md)**.

---

## Cómo usar este documento

1. La **fuente de verdad del progreso es el CLI**: `openspec status --change "<nombre>"`. Un change entra acá si `completedTasks < totalTasks`.
2. Respetá las dependencias: no arranques un change cuyas deps sigan abiertas.
3. Flujo: `/opsx:propose` (si falta) → `/opsx:apply` → `/opsx:archive`. Al archivar, el change sale de este roadmap.
4. Regenerá este archivo con `/roadmap-generator` cuando cambie el estado (no lo edites a mano para "tildar").

> **Foto al 2026-06-13 (sesión 3, post-c-66)**: 65 changes totales · **53 archivados** + **4 cancelados** (sin retomar) · **9 pendientes** (abajo) · **+1 planificado sin crear** (integración LMS/LTI, Fase 2 — ver Prioridad 2).

> **Cambios respecto del estado anterior (sesión 2 del 2026-06-11)**:
> - **Archivados nuevos**: c-66 (UI estudiante onboarding desktop+mobile, frontend-only, todas las 24 tasks completadas — tsc limpio, build verde).
> - **Sesión 2 (2026-06-11)**: c-04, c-32, c-34, c-35, c-52, c-56 (código en main + verificación cerrada).
> - **Cancelados** (movidos a `archive/<fecha>-c-NN-name-CANCELLED/` con nota): **c-02** (basta asignar rol `proctor` en Keycloak), **c-44** (no se crean exámenes en plataforma — LMS lo hará vía change futuro de integración LMS, DD-20; **alcance revivido por c-69**: examen en plataforma con Moodle + lockdown + write-back de nota, ver DD-20 revisión C-69), **c-53** (Object Detection diferido sine die), **c-39** (análisis DNI mock client-side contradice la postura "no análisis cliente" ya escrita en `EnrollmentDniStep.tsx`; el análisis real será server-side a futuro).
> - **c-03 sincronizado** desde rama `feat/c-03-poc-carga` → main: trae `/poc/` (harness multi-instancia + k6 + panels_asyncio) y `results-4core-baseline.md`. Estado pasó de 0/25 → **24/45** (Bloques 0-4 hechos; Bloque 5 medición + Bloque 6 condicional + cierre veredictos pendientes).
> - **Deuda de specs canónicas malformadas**: regeneradas las 26 que fallaban `openspec validate --specs --strict`. Hoy: **111 passed / 0 failed**.

---

## ⚠️ Reality check 2026-06-11 — rama "slim" (Postgres puro + screenshots) vs rama "full" (TimescaleDB + clips)

> Los proposals/designs originales fueron escritos asumiendo la **rama "full"** (TimescaleDB hypertables + continuous aggregates + clips de video). La realidad de producción (Railway con `Dockerfile.slim`) es la **rama "slim"** (Postgres puro + screenshots por evento). Diferencias clave que afectan a varios changes activos:
>
> | Concepto en designs | Realidad slim (hoy) | Aplica a |
> |---------------------|---------------------|----------|
> | Hypertable TimescaleDB | Tabla común `proctoring_event` | c-10, c-19 |
> | Continuous aggregates (`cagg_*`) | Query directa o materialized view manual | c-15, c-20 |
> | Compresión nativa TimescaleDB | No existe | c-19 |
> | Archivado a Parquet de chunks | `DELETE WHERE created_at < X` simple | **c-19 (el más afectado, esfuerzo baja de ~15h a ~8-10h)** |
> | "Clips de video URL firmada 15min" | **Screenshots por evento** (`proctoring_event.screenshot_b64`). La URL firmada sigue aplicando, pero sobre screenshot | c-16, c-17 |
> | Auth: Keycloak | JWT propio (c-55) hoy; Keycloak diferido a integración LMS | c-17 |
>
> **Decisión del dueño**: Postgres puro ahora, TimescaleDB cuando c-03 valide escala. Los design bodies originales siguen siendo válidos para **Fase 2 (post-c-03)**. Cada proposal afectado tiene una nota "⚠️ REALITY CHECK" al principio con el detalle.
>
> **Changes afectados (con nota en proposal.md)**: c-10, c-15, c-16, c-17, c-19. **Sin impacto**: c-18 (cadena de custodia funciona igual con screenshots).

---

## ⛔ Prioridad 0 — Gates bloqueantes

> El CLI los marca en 0% o con trabajo parcial sin veredicto cerrado. Son precondición dura del resto.

| Change | Progreso | Qué es | Dep | Gov |
|--------|----------|--------|-----|-----|
| **c-01** `acuerdo-proctoring-dpia` | 0/23 | Acuerdo de Nivel de Proctoring firmado + **DPIA** completo + 19 ADRs aprobados. **No-código** (legal/DPO). | — | CRÍTICO |
| **c-03** `poc-carga-mensajeria` | 24/45 | PoC de carga al **pico (~2.100 concurrentes / ~5.000 inserts/s)** que **decide** cola/transporte/backplane (A4 vs SAD). Bloques 0-4 hechos (publisher asyncpg + cola Postgres SKIP LOCKED + k6 + panels_asyncio); Bloque 5 (barrido + veredictos) requiere host 8+ cores. | c-01 | CRÍTICO |

> **c-02 (designación-revisores) fue cancelado en sesión 2** — basta con asignar rol `proctor` cuando llegue el momento (Keycloak ya tiene el realm listo, ver c-52 archivado).

**Leer antes**: `13_legal_y_cumplimiento_argentina.md`, `09_decisiones_y_supuestos.md` §DD-14…DD-19, `14_observabilidad_y_devops.md` §SLOs/Capacity, `10_preguntas_abiertas.md`, `poc/README.md` (harness PoC).

---

## 🟡 Prioridad 1 — MVP camino crítico

> Camino crítico restante: `c-03 → c-15b → c-16 → c-20` (c-10 y el slim de c-15 ya **archivados**). c-17, c-18, c-19 están desbloqueados y pueden correr en paralelo.
>
> **PARTICIÓN 2026-06-24**: c-10 y c-15 se **archivaron por su scope entregado** y lo que dependía de c-03 se movió a un sucesor. c-10: implementación del fan-out completa; la **verificación de SLO bajo carga** (p99<500ms, cero pérdida, e2e, OTEL) se consolidó en **c-03** (su harness es el banco de carga). c-15: se entregó el **slim** (chat/pausa/observaciones/cierre/RBAC vía REST+polling); el **tiempo real** (SSE, priorización por score, alertas <500ms, MFA) pasó a **c-15b**.

| Change | Progreso | Qué falta / scope | Dep | Estado |
|--------|----------|-------------------|-----|--------|
| **c-10** `event-ingestion-transport` | 26/26 | Contrato de evento, WS del estudiante, validación HMAC, persistencia hypertable y **fan-out** (puerto + adaptadores LISTEN/NOTIFY y Redis) entregados. Verificación de SLO bajo carga → **c-03**. | c-03 | ✅ **Archivado** (scope entregado) |
| **c-15** `panel-proctor-sse` | — | **Slim entregado**: acciones del proctor (chat, observaciones, cierre forzado), pausa autorizada + contextualización de score, RBAC por rol. | c-10 ✓ | ✅ **Archivado** (slim) |
| **c-15b** `panel-proctor-sse-transport` | 0/10 | Tiempo real: transporte SSE sin sticky + backplane (ganador c-03); priorización por score (continuous aggregates c-13); alertas críticas p99<500ms; reconexión SSE; MFA del panel. | c-03, c-13 | ⛔ Bloqueado por c-03 |
| **c-16** `cola-revision-humana` | 0/15 | Cola por score + aislada por jurisdicción + audit de acceso + decisión humana terminal inmutable. **Cierre del ciclo MVP.** Consume las **observaciones** del proctor (ya entregadas en el slim de c-15). | c-13, c-15 ✓ (slim) | Desbloqueado por el slim de c-15 (no requiere c-15b) |
| **c-17** `dsr-derechos-titular` | 0/20 | `POST /api/v1/dsr/{type}` access/rectification/erasure/portability + holds + audit log. | c-06 ✓ | **Listo para arrancar** |
| **c-18** `verificacion-cadena-apelacion` | 0/20 | `POST /api/v1/evidence/{id}/verify-chain` que re-verifica 4 etapas de firma + emite certificado independiente para perito externo. | c-12 ✓ | **Listo para arrancar** |
| **c-19** `retencion-holds` | 0/19 | Motor retención automática + holds por caso abierto + archivado a Parquet + eliminación embedding al egreso (Ley 25.326, RN-DSR-02). | c-07 ✓ | **Listo para arrancar** |
| **c-20** `reportes-analytics` | 0/19 | Reportes post-examen agregados (distribución scores, outliers, métricas calidad detector). **Sin veredictos automáticos.** | c-13 ✓, c-16 | Bloqueado por c-16 |

**Leer antes**: la KB indicada por change en [CHANGES.legacy.md](CHANGES.legacy.md) (sección FASE 1).

---

## 🟣 Prioridad 2 — Fase 2 planificada (integración LMS / LTI) — ⚠️ aún SIN change en el CLI

> Este change estaba en el plan original (`CHANGES.legacy.md` §[C-49] `c-49-integracion-lms-lti`) pero **nunca se creó como change real en el CLI**: el número `c-49` lo tomó otro change (`c-49-cablear-codigo-fantasma-proctoring`, ya archivado), así que al regenerar este roadmap desde `openspec list --json` quedó **invisible**. Se re-incorpora acá para que no se pierda. **NO cuenta en los 9 pendientes del CLI** hasta que se corra `/opsx:propose`.

| Change (propuesto) | Progreso | Qué es | Dep | Gov |
|--------------------|----------|--------|-----|-----|
| **integracion-lms-lti** (sin número) | sin crear | ⭐ Materializa **FR-17 (integración LMS) de Fase 2 — DD-20 (rev. 2026-06-11)**. **Dos capas**: (1) **LTI 1.3 Tool Provider** universal que cualquier LMS (Moodle, Canvas, Blackboard, D2L…) puede lanzar — launch OIDC (encaja con Keycloak ya configurado en c-52), roster vía **NRPS**, retorno vía **AGS** (resultado de proctoring, **NO la nota** — L2.5), mapeo de claims→3 roles reales; (2) **plugin Moodle `quizaccess`** (NO opcional) — proctoring como regla de acceso al quiz nativo (gate cámara/consentimiento + monitoreo durante el intento, sin saltar de pantalla). El examen lo opera el LMS; el proctoring NO crea ni importa exámenes. | c-01, c-06 ✓, c-07 ✓, c-16 | ALTO |

**Leer antes**: `09_decisiones_y_supuestos.md` §DD-20 · `CHANGES.legacy.md` §[C-49] (scope completo) · `02_descripcion_general.md` §Integraciones · `06_funcionalidades.md` §Épica 18 (FR-17).

**Para arrancarlo**: `/opsx:propose <c-XX>-integracion-lms-lti` con el siguiente número libre del CLI cuando se quiera arrancar. No antes del MVP operativo — no se integra un proctoring que todavía no existe.

---

## 🟢 Prioridad — Frontend / UX biométrico (no bloqueante)

> Changes 100% client-side sobre el flujo biométrico ya implementado. **No dependen de c-03** (no tocan cola/transporte/tiempo real) ni del camino crítico del MVP; pueden correr en paralelo. Construyen sobre el linaje biométrico archivado (c-22 / c-36 / c-54 / c-59 / c-65).

| Change | Progreso | Qué es / scope | Dep | Gov |
|--------|----------|----------------|-----|-----|
| **c-67** `captura-biometrica-gestos-liveness` | 62/63 | **Implementado y testeado** (suite 336/336 verde + verificación en navegador real con Playwright). Grupos 0–7 (scope original 27 tasks) + grupo 8 (28 fixes de UX/copy/robustez surgidos al probar en teléfono real, tasks 8.1–8.28): sonrisa precisa/rápida, anillo en la banda blanca con relleno verde progresivo y reanudación sin reinicio, cues de audio (+unlockAudio mobile), resultado del examen en lenguaje claro con gate, PAD anti-foto, persistencia de modelos (Service Worker) + −PoseLandmarker, animación de éxito (motion), stepper estilo wizard de perfil, cámara sin espejo en todo el flujo, severidad baja=azul, y limpieza total de jerga (acuse/hash/web worker/clips/embedding/liveness/Ley 25.326/DPIA). **No toca cadena de custodia ni embedding; autoridad = re-inferencia server-side.** **Falta solo:** 7.2 = revisión manual final de aceptación del dueño en dispositivo (no automatizable). | c-54 ✓, c-59 ✓, c-65 ✓ (archivados) | **Listo para archivar tras la pasada manual final** (aprobado e implementado; dominio CRÍTICO) |

**Leer antes**: `11_ia_y_vision.md`, `12_biometria_y_liveness.md`, `05_reglas_de_negocio.md` §RN-BIO.

| **c-68** `configuracion-sistema-funcional` | ✅ archivado (2026-06-22) | **Configuración del Sistema funcional + consentimiento persistido** (no planificado; se le asignó el siguiente número libre). Backend (ola 1): tablas `configuracion_sistema` (singleton versionado: umbrales/detectores/retención) y `consentimiento_perfil` (append-only, atado a usuario, versionado/revocable, eliminación al egreso) en slim+full; API de config + `GET /config/effective`; API de consentimiento de perfil server-side; consumo server-side de scoring/umbrales (snapshot por sesión). Frontend (ola 2): admin (Proctoring/Detección/Consentimiento) cableado a la config real con escala amigable (segundos / Baja-Media-Alta / %); consentimiento contra backend (re-pedir, no migrar localStorage); el examen de prueba y TEST DETECCIÓN consumen la config viva con invalidación de cache. **L2.5 intacto** (la config prioriza/flaggea, no sanciona). Decisión del dueño: consentimiento implementado ya (sin gate de DPIA, se ajusta luego). **Sesión 2026-06-16 (ampliación aprobada por el dueño)**: fix de caché de scoring (editar peso se refleja en effective); evento `corte_conectividad_prolongado` crítico; **consentimiento con texto VERSIONADO editable** (tabla `consent_texto_version`; agregar/editar/eliminar cláusulas; publicar versión → re-consentimiento); **gestión de usuarios** (detalle de alumno con consentimiento+biometría sin exponer embedding, filtros server-side, reactivar, switch de estado); el examen **respeta `detectores_activos`**; la cola lee el umbral de la config (no 60 fijo) y excluye sesiones sin examen; rediseño UI completo de Configuración + Test Detección. Tests: backend 77 verde (áreas del change) + frontend 440 verde; tsc limpio. **Sesión 2026-06-22 (cierre)**: re-consentimiento en el Inicio del alumno (detecta versión desactualizada), auditoría `config_update` también en PATCH scoring, infra de test (NullPool + pin pytest-asyncio + rangos 0021). Áreas de C-68 70/70 verde. **ARCHIVADO** (7.1 smoke prod = post-deploy; 7.4 aceptación del dueño = OK). | c-54 ✓, c-59 ✓, c-65 ✓, c-67 ✓ (scoring/consent-gate/user-management archivados) | **MEDIO** (consentimiento = CRÍTICO Ley 25.326; resto MEDIO) |

**Leer antes**: `05_reglas_de_negocio.md` §RN-SC/§RN-CO, `13_legal_y_cumplimiento_argentina.md`, `04_modelo_de_datos.md`.

---

## 🔵 Prioridad — Examen en plataforma (Moodle + lockdown) — fuera del roadmap original

> Línea de trabajo **revivida por DD-20** (examen operado EN la plataforma con import Moodle XML + lockdown + write-back de nota), nacida fuera del plan original de 65 changes. **c-69** entregó la rendición completa (import, config por examen, rendición robusta, nota entera estilo Moodle, revisión, gate de visibilidad de resultados) y está **archivado** (2026-07-07). **c-70** (matriculación por código estilo Moodle, enrolment key) le siguió y está archivado. **c-71** es el sucesor directo: hizo que la inscripción de c-70 **realmente gatee** (c-70 explícitamente "NO altera puede_rendir"; c-71 SÍ) y entregó además la Cola de Revisión (slices 1+2, archivado). **c-72** continúa la línea: cierra la integridad de la rendición server-side (deadline efectivo, auto-finalización, candado direccional de config) y **absorbe las Sesiones Grabadas** que originalmente eran el slice 3 de c-71. Registrados a mano (no vinieron del `/roadmap-generator`); regenerar el roadmap formalmente cuando se cierre.

| Change | Progreso | Qué es / scope | Dep | Gov |
|--------|----------|----------------|-----|-----|
| **c-69** `examen-plataforma-moodle-lockdown` | ✅ archivado (2026-07-07) | Examen operado en la plataforma: import Moodle XML → pool de preguntas seleccionable, config por examen (timer/ventana/intentos/nota/shuffle), rendición robusta (sesión anti-zombie), nota entera ROUND_HALF_UP estilo Moodle, revisión post-examen, gate de visibilidad de resultados (Review options), write-back de nota a Moodle. | c-68 ✓ | MEDIO |
| **c-70** `matriculacion-por-codigo` | ✅ archivado (2026-07-07) | **Modelo enrolment-key de Moodle**: cada comisión gana un `codigo_matriculacion` único (autogenerado `{materia}-{sufijo}`, editable/rotable por el docente). El alumno se auto-matricula posteando el código (`POST /api/v1/exam-content/inscribirme`, auth-only, `usuario_id` del principal — NUNCA del body). Idempotente ante ya-inscripto; coexiste con la inscripción manual; NO altera el gate `puede_rendir` (**eso lo cierra c-71**). Migración slim `0038` aditiva en dos pasos con backfill. Frontend docente (código + copiar) + alumno (unirse con código). **Incluye hardening del enrollment biométrico contra inyección de embedding.** | c-69 ✓ | ALTO (endpoint de acceso + toca biometría) |
| **c-71** `inscripcion-gate-y-cola-revision` | ✅ archivado (2026-07-15, slices 1+2) | **Change de integridad de examen, entregado en dos slices.** **Slice 1 — gate de inscripción**: el alumno solo VE y solo RINDE exámenes de comisiones donde está inscripto por código. Catálogo (`listar_examenes_contenido`) y "Mis materias/comisiones" filtrados **server-side por rol** (staff ve todo); backstop **403 `no_inscripto`** en `crear_sesion` (cliente no confiable). Cierra el agujero que c-70 dejó abierto. **Slice 2 — Cola de Revisión + transparencia al alumno**: decisión en dos fases (revisar `revisar_sesion` / resolver `resolver_caso`), resolución `anulado_por_fraude` reversible por acto compensatorio append-only, gate de write-back a Moodle por estado de revisión, informe de devolución al alumno (Ley 25.326). Tests verdes (DB real). **Sesiones Grabadas (ex-slice 3) → reasignado a c-72.** | c-70 ✓ | ALTO (control de acceso + notas + disciplina) |
| **c-72** `integridad-rendicion-serverside` | 🟡 propuesto (4/4 artefactos, `validate` = valid; 0/65 tasks, sin aplicar) | **Cierra los agujeros de integridad de la rendición confirmados en vivo (H-1/H-2/H-3): la API acepta respuestas y `finalizar` fuera de tiempo y fuera de ventana.** Server-side: **deadline efectivo** (min(tiempo_limite, fin_ventana)) + **gracia**, **auto-finalización** de sesiones vencidas, **evento de reanudación**, **candado direccional** de la config de mecánica/nota una vez rendido. **Absorbe las Sesiones Grabadas** (ex-slice 3 de c-71) + statcards UI/UX + ocultar eventos sin captura + timeout de pausa (scope ampliado por el owner). | c-71 ✓ | ALTO/CRÍTICO (integridad de examen, anti-tampering) |

**Leer antes**: `openspec/changes/c-72-integridad-rendicion-serverside/` (proposal/design/specs/tasks) y el archivo de c-71 en `openspec/changes/archive/2026-07-15-c-71-inscripcion-gate-y-cola-revision/`, `04_modelo_de_datos.md` §comisión/inscripción/sesión, `05_reglas_de_negocio.md` §RN-BIO (embedding = dato sensible, cliente no confiable) y §RN-SC (integridad de rendición).

---

## Árbol de dependencias (pendientes)

```
c-01-acuerdo-proctoring-dpia (0/23)
  └── c-03-poc-carga-mensajeria (24/45)   ← absorbe la verificación de SLO bajo carga de c-10
        └── c-15b-panel-proctor-sse-transport (0/10)   [tiempo real; dep c-03 + c-13]
              └── (panel en vivo de producción)

c-16-cola-revision-humana (0/15)   ← desbloqueado por el SLIM de c-15 (observaciones); dep c-13
      └── c-20-reportes-analytics (0/19)

Archivados 2026-06-24 (scope entregado):
  c-10-event-ingestion-transport  → fan-out implementado; verificación de SLO → c-03
  c-15-panel-proctor-sse (slim)    → chat/pausa/observaciones/cierre/RBAC (REST+polling)

Desbloqueados hoy (deps ya archivadas — pueden arrancar en paralelo):
  c-17-dsr-derechos-titular (0/20)         [c-06 ✓]
  c-18-verificacion-cadena-apelacion (0/20) [c-12 ✓]
  c-19-retencion-holds (0/19)              [c-07 ✓]

Planificado sin proponer:
  integracion-lms-lti (Fase 2, sin número — se le asigna el siguiente libre al proponerlo)
```

### Camino crítico restante (4 changes)

```
c-03 → c-15b → (panel en vivo prod)
c-16 → c-20            [c-16 ya desbloqueado por el slim de c-15; dep c-13]
```

(c-01 es gate legal independiente; corre en paralelo, no en serie con el código. c-10 y el slim de c-15 quedaron archivados 2026-06-24.)

### Plan de ataque con 3 agentes (foto al 2026-06-11 sesión 2)

| Paso | Agente A (MVP crítico) | Agente B (MVP desbloqueado) | Agente C (Gate paralelo) |
|------|------------------------|-----------------------------|--------------------------|
| 1 | (espera c-03 con host 8+ cores) | c-17 dsr-derechos-titular | c-01 acuerdo + DPIA (drafts legales) |
| 2 | c-16 cola-revision-humana (ya desbloqueado por el slim de c-15) | c-18 verificacion-cadena-apelacion | c-01 firma DPO |
| 3 | c-15b panel-proctor-sse-transport (tras veredicto c-03) | c-19 retencion-holds | — |
| 4 | c-20 reportes-analytics (tras c-16) | — | — |
| 5 | integracion-lms-lti (post-MVP, sin número aún) | — | — |

> Agente A camino crítico (depende de c-03 cerrado). Agente B avanza independiente en módulo legal/cumplimiento (DSR + cadena custodia + retención). Agente C corre la pista legal de c-01 en paralelo.

---

## Orden sugerido de ataque

1. **Recuperar c-03**: levantar host con 8+ cores (Codespaces Pro / AWS spot) y correr Bloque 5 — barrido P0→E6 — para cerrar veredictos (a/b/c). **Esto consolida la verificación de SLO que se descopeó de c-10 y desbloquea c-15b** (tiempo real del panel).
2. **En paralelo, c-16** (ya desbloqueado por el slim de c-15: consume las observaciones del proctor) **y c-17/c-18/c-19** (módulo legal/cumplimiento, deps archivadas). Ideal para varios agentes en paralelo.
3. **Cuando DPO esté disponible, c-01**: drafts de Acuerdo L2.5 + DPIA + Acta ADRs los puede preparar Claude desde la KB; firma humana cierra el gate.
4. **Tras veredicto c-03**: c-15b (panel en vivo de producción). c-20 tras c-16.
5. **Fase 2**: integración LMS/LTI (sin número aún, ver Prioridad 2) cuando el MVP esté operativo. **Análisis real del DNI** (server-side, OCR + PDF417 + RENAPER) sería un change nuevo separado cuando aparezca la necesidad — no reabrir c-39 (cancelado).

> Regla dura del proyecto (DD-19): la arquitectura de mensajería **la decide C-03**. No asumir A4 ni SAD antes de esa PoC.

---

## Resumen por estado

| Bucket | Changes | Tasks totales | Tasks completas |
|--------|---------|---------------|-----------------|
| Gate bloqueante (parcial) | c-01, c-03 | 68 | 24 |
| Archivados 2026-06-24 (scope entregado) | c-10, c-15 (slim) | — | — |
| MVP bloqueado por c-03 | c-15b | 10 | 0 |
| MVP sin empezar (0%) | c-16, c-17, c-18, c-19, c-20 | 93 | 0 |
| **Total pendientes** | **8** | **171** | **24** |
| Archivados | 53 (c-66 + anteriores) | — | — |
| Cancelados (sin retomar) | 4 (c-02, c-39, c-44, c-53) | — | — |
| **Total universo** | **66** | — | — |
| Planificado sin crear | integracion-lms-lti (Fase 2, sin número) | — | — |
