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
> - **Cancelados** (movidos a `archive/<fecha>-c-NN-name-CANCELLED/` con nota): **c-02** (basta asignar rol `proctor` en Keycloak), **c-44** (no se crean exámenes en plataforma — LMS lo hará vía change futuro de integración LMS, DD-20), **c-53** (Object Detection diferido sine die), **c-39** (análisis DNI mock client-side contradice la postura "no análisis cliente" ya escrita en `EnrollmentDniStep.tsx`; el análisis real será server-side a futuro).
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

> Camino crítico restante: `c-03 → c-10 → c-15 → c-16 → c-20`. c-17, c-18, c-19 están desbloqueados y pueden correr en paralelo.

| Change | Progreso | Qué falta / scope | Dep | Estado |
|--------|----------|-------------------|-----|--------|
| **c-10** `event-ingestion-transport` | 22/26 | WS del estudiante + validación HMAC + fan-out (ganador C-03). Las 4 tasks pendientes (SLO p99<500ms, cero pérdida bajo reconexión, e2e Flujo 3, OTEL) **se validan con el harness de c-03**. | c-03 | Archiva con c-03 |
| **c-15** `panel-proctor-sse` | 0/16 | Supervisión en vivo vía SSE; priorización por score; alertas críticas <500 ms; cierre forzado de sesión. | c-10 | Bloqueado por c-10 |
| **c-16** `cola-revision-humana` | 0/15 | Cola por score + aislada por jurisdicción + audit de acceso + decisión humana terminal inmutable. **Cierre del ciclo MVP.** | c-15 | Bloqueado por c-15 |
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

## Árbol de dependencias (pendientes)

```
c-01-acuerdo-proctoring-dpia (0/23)
  └── c-03-poc-carga-mensajeria (24/45)
        └── c-10-event-ingestion-transport (22/26)   ← archiva en paralelo con c-03 (misma métrica)
              └── c-15-panel-proctor-sse (0/16)
                    └── c-16-cola-revision-humana (0/15)
                          └── c-20-reportes-analytics (0/19)

Desbloqueados hoy (deps ya archivadas — pueden arrancar en paralelo):
  c-17-dsr-derechos-titular (0/20)         [c-06 ✓]
  c-18-verificacion-cadena-apelacion (0/20) [c-12 ✓]
  c-19-retencion-holds (0/19)              [c-07 ✓]

Planificado sin proponer:
  integracion-lms-lti (Fase 2, sin número — se le asigna el siguiente libre al proponerlo)
```

### Camino crítico restante (5 changes)

```
c-03 → c-10 → c-15 → c-16 → c-20
```

(c-01 es gate legal independiente; corre en paralelo, no en serie con el código)

### Plan de ataque con 3 agentes (foto al 2026-06-11 sesión 2)

| Paso | Agente A (MVP crítico) | Agente B (MVP desbloqueado) | Agente C (Gate paralelo) |
|------|------------------------|-----------------------------|--------------------------|
| 1 | (espera c-03 con host 8+ cores) | c-17 dsr-derechos-titular | c-01 acuerdo + DPIA (drafts legales) |
| 2 | c-10 cerrar 4 tasks (junto con veredicto c-03) | c-18 verificacion-cadena-apelacion | c-01 firma DPO |
| 3 | c-15 panel-proctor-sse | c-19 retencion-holds | — |
| 4 | c-16 cola-revision-humana | — | — |
| 5 | c-20 reportes-analytics | — | — |
| 6 | integracion-lms-lti (post-MVP, sin número aún) | — | — |

> Agente A camino crítico (depende de c-03 cerrado). Agente B avanza independiente en módulo legal/cumplimiento (DSR + cadena custodia + retención). Agente C corre la pista legal de c-01 en paralelo.

---

## Orden sugerido de ataque

1. **Recuperar c-03**: levantar host con 8+ cores (Codespaces Pro / AWS spot) y correr Bloque 5 — barrido P0→E6 — para cerrar veredictos (a/b/c). **Esto desbloquea c-10 simultáneamente** (comparten métrica).
2. **En paralelo, c-17/c-18/c-19**: tres changes del módulo legal/cumplimiento ya desbloqueados (deps archivadas), sin dependencia entre ellos. Ideal para 3 agentes en paralelo.
3. **Cuando DPO esté disponible, c-01**: drafts de Acuerdo L2.5 + DPIA + Acta ADRs los puede preparar Claude desde la KB; firma humana cierra el gate.
4. **Camino crítico cerrado**: c-15 → c-16 → c-20 después de c-10.
5. **Fase 2**: integración LMS/LTI (sin número aún, ver Prioridad 2) cuando el MVP esté operativo. **Análisis real del DNI** (server-side, OCR + PDF417 + RENAPER) sería un change nuevo separado cuando aparezca la necesidad — no reabrir c-39 (cancelado).

> Regla dura del proyecto (DD-19): la arquitectura de mensajería **la decide C-03**. No asumir A4 ni SAD antes de esa PoC.

---

## Resumen por estado

| Bucket | Changes | Tasks totales | Tasks completas |
|--------|---------|---------------|-----------------|
| Gate bloqueante (parcial) | c-01, c-03 | 68 | 24 |
| MVP camino crítico (parcial) | c-10 | 26 | 22 |
| MVP sin empezar (0%) | c-15, c-16, c-17, c-18, c-19, c-20 | 109 | 0 |
| **Total pendientes** | **9** | **203** | **46** |
| Archivados | 53 (c-66 + anteriores) | — | — |
| Cancelados (sin retomar) | 4 (c-02, c-39, c-44, c-53) | — | — |
| **Total universo** | **66** | — | — |
| Planificado sin crear | integracion-lms-lti (Fase 2, sin número) | — | — |
