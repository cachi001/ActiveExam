# CHANGES — Roadmap de pendientes

> Índice **solo de lo que falta** del proyecto **Proctoring** (plataforma self-hosted de supervisión asistida por IA de evaluaciones remotas).
> Regenerado el **2026-06-11** (sesión 2, post-c-39), última actualización manual **2026-08-13** (sesión post-c-75) a partir del estado real del CLI de OpenSpec (`openspec list --json`).
> El plan original completo (los 65 changes, hechos y pendientes) quedó archivado en **[CHANGES.legacy.md](CHANGES.legacy.md)**.

---

## Cómo usar este documento

1. La **fuente de verdad del progreso es el CLI**: `openspec status --change "<nombre>"` / `openspec list --json`. Un change entra acá si `completedTasks < totalTasks`.
2. Respetá las dependencias: no arranques un change cuyas deps sigan abiertas.
3. Flujo: `/opsx:propose` (si falta) → `/opsx:apply` → `/opsx:archive`. Al archivar, el change sale de este roadmap.
4. **Este archivo se desactualiza solo** (archivar un change no lo edita). Antes de confiar en la sección de pendientes, corré `openspec list --json` — es la única fuente que no miente.

> **Foto al 2026-08-26**: con `c-78` archivado, `openspec list --json` devuelve **3 changes
> abiertos**, y los tres son gates o dependen de uno: `c-01` (0/23, gate legal), `c-03`
> (24/45, PoC de carga) y `c-15b` (0/10, SSE — depende de c-03). No queda ningún change de
> código activo. `c-76`, `c-77`, `c-78` y `c-79` están archivados.

> **Foto al 2026-08-13 (post-C-75)**: `openspec list --json` devuelve **solo 3 changes pendientes en todo el proyecto**: `c-01`, `c-03`, `c-15b`. Todo lo demás — incluyendo **c-16 a c-20** (que este archivo tenía listados como "0% sin empezar" desde el 11-jun) y **c-67 a c-75** (nunca reflejados acá) — está **archivado**. Ver "Resumen por estado" al final para el detalle completo de lo que se sumó al archivo desde la última regeneración real (17-jul).

> **c-76-panel-supervision-en-vivo — ARCHIVADO (2026-08-18)**: rediseño de roles del panel de supervisión (elimina `PROCTOR`, tutor acotado por comisión) + UX completa. 20/20 tareas cerradas: bloques 1-13 (roles, chat/pausas, límite configurable, screenshots de pausa, rediseño visual del detalle) + bloques nuevos de esta sesión — estados de entrega/archivado/filtros en Notas (14), evidencia de contexto en `copiar_pegar`/`cambio_pestana` (15), eliminación del borrado de sesiones de examen real por cadena de custodia (16), Registro de sesiones como tabla con paginación/filtros/stats reales (17/19/20), fix crítico de auth (`auth_provider='jwt'` no podía cambiar su clave, 18), y cierre del módulo "Sesiones" muerto de Auditoría. Verificado en vivo end-to-end en el navegador (no solo tests). Archivado como `2026-08-18-c-76-panel-supervision-en-vivo`.

> **c-77-minio-worm-evidencia — ARCHIVADO (2026-08-18)**: conecta MinIO/WORM (Object Lock Compliance, diseño C-12 hasta ahora sin usar) a la app real (`main_activeexam.py`, la que se despliega a Render). Decisión del dueño: **NO se migra nada existente** — `proctoring_event.screenshot_b64` sigue escribiéndose en Postgres exactamente igual (cero riesgo). MinIO se agrega como depósito **adicional, opcional y tolerante**: sin las 4 variables `MINIO_*` (caso Render hoy, sin VPS) el sistema se comporta idéntico a antes del change, sin ningún error al arrancar. Verificado end-to-end: arranque sin `MINIO_*` (0 errores) y arranque con `MINIO_*` (evidencia real en el bucket, Object Lock modo Compliance confirmado con `mc retention info` — incluye verificación real de que un DELETE es rechazado antes de `retain_until`). Tests contra Postgres real + MinIO real en Docker (no mocks). Archivado como `2026-08-18-c-77-minio-worm-evidencia`.

> **c-79-permisos-nm-coordinador — ARCHIVADO (2026-08-22)**: reemplaza el alcance por
> `comision.docente_id` (un solo docente por comisión) por un modelo **N:M real** —
> `comision_tutor` y `materia_coordinador` — y **acota al COORDINADOR a su materia** (antes
> era de alcance institucional, equivalente a admin; revisado a pedido del dueño). El único
> rol institucional que queda es `ADMIN_SISTEMA`. Suma la pantalla de asignación de
> coordinadores y la auditoría con **entidad real** (`entidad_de_accion`), que resuelve el
> "Ver detalle" a la entidad afectada en vez de caer al listado genérico. Archivado como
> `2026-08-22-c-79-permisos-nm-coordinador`.
>
> ⚠️ **Su archivado quedó incompleto y se corrigió el 2026-08-25 (durante c-78)**: las dos
> delta specs (`permisos-nm-pertenencia`, `auditoria-entidad-actor`) habían quedado **solo
> dentro del archivo** y nunca se sincronizaron a `openspec/specs/`, así que la fuente de
> verdad no tenía sus requisitos. Ya están sincronizadas. En la misma pasada se corrigieron
> **3 specs de c-74** (`post-exam-reports`, `report-exports-and-summary`,
> `statistical-distribution-analytics`) que se habían archivado en **formato delta**
> (`## ADDED Requirements`, sin `## Purpose`) en vez de spec final, y por eso
> `openspec validate --specs` venía fallando 3/187. Hoy: **187 passed / 0 failed**.
> Lección: `/opsx:archive` tiene que dejar la spec en formato FINAL y copiada a
> `openspec/specs/` — conviene verificar con `openspec validate --specs` al cerrar.

> **c-78-coherencia-y-mejoras-relevamiento — ARCHIVADO (2026-08-26, 105/105 COMPLETO)**: el
> change de código más grande del proyecto. Scope original (baja lógica de exámenes,
> coherencia de denominadores, filtro de etiqueta) + retención y baja biométrica DSR +
> multi-comisión, duplicar y sorteo por intento + capacidad medida contra Render +
> write-back de notas verificado de punta a punta contra el campus real.
>
> **§18 salió de recorrer producción a mano el 26/8**: las tres materias estaban **sin
> profesor y sin coordinador** y las cinco comisiones **sin tutor**, y nada lo advertía — con
> el write-back saliendo con la credencial del tutor, eso significaba notas retenidas
> descubiertas con el examen ya rendido. Se cerró por los dos lados: los responsables
> quedaron asignados en producción (18.1) y el sistema ahora **avisa** cuando faltan (18.4).
> De paso, la flecha de los `<select>` dejó de estar pegada al borde en toda la app (18.5).
>
> **§16 se terminó en vez de diferirse**, y cada tarea encontró algo que ya estaba mal:
> - **16.2** El pool de conexiones estaba fijo en el código con la cuenta para 4 workers. Al
>   derivarlo del entorno real apareció que **dev corría 5 procesos con techo 120 contra un
>   `max_connections=100`**. Trampa: `uvicorn --workers N` NO setea ninguna variable, así que
>   hay que contar los procesos de verdad o la cuenta sale mal por un factor de N.
> - **16.3b** `grabador_metricas.py` (solo stdlib, sin infraestructura nueva) + wrapper
>   `tools/grabar-metricas.sh`. Deja un `.jsonl` por examen con resumen al cerrar.
> - **16.5** Ingesta binaria de la captura: **24,6% menos de subida medido contra el backend
>   real**, con el hash IDÉNTICO por los dos caminos (si no, toda la evidencia histórica
>   dejaría de verificar). El guard de arquitectura del repo agarró un bug propio: usar
>   `fetch` crudo habría hecho fallar todos los eventos a los 15 minutos de examen.
> - **18.2** `tools/despertar-render.sh`. Medido: dormido tarda **63 segundos** en despertar,
>   y ese minuto se lo comía el primer alumno que entraba por el link de Moodle.
>
> **16.6 (SSE) se movió a `c-15b`**, que es donde corresponde: es un cambio de transporte, no
> una mejora de coherencia. Estaba en c-78 como recordatorio y lo mantenía abierto por algo
> que no le pertenecía. El análisis hecho con el dueño se conserva en la §0 de c-15b.

> **Cambios respecto del estado anterior (sesión 2 del 2026-06-11)**:
> - **Archivados nuevos**: c-66 (UI estudiante onboarding desktop+mobile, frontend-only, todas las 24 tasks completadas — tsc limpio, build verde).
> - **Sesión 2 (2026-06-11)**: c-04, c-32, c-34, c-35, c-52, c-56 (código en main + verificación cerrada).
> - **Cancelados** (movidos a `archive/<fecha>-c-NN-name-CANCELLED/` con nota): **c-02** (basta asignar rol `proctor` en Keycloak), **c-44** (no se crean exámenes en plataforma — LMS lo hará vía change futuro de integración LMS, DD-20; **alcance revivido por c-69**: examen en plataforma con Moodle + lockdown + write-back de nota, ver DD-20 revisión C-69), **c-53** (Object Detection diferido sine die), **c-39** (análisis DNI mock client-side contradice la postura "no análisis cliente" ya escrita en `EnrollmentDniStep.tsx`; el análisis real será server-side a futuro).
> - **c-03 sincronizado** desde rama `feat/c-03-poc-carga` → main: trae `/poc/` (harness multi-instancia + k6 + panels_asyncio) y `results-4core-baseline.md`. Estado pasó de 0/25 → **24/45** (Bloques 0-4 hechos; Bloque 5 medición + Bloque 6 condicional + cierre veredictos pendientes).
> - **Deuda de specs canónicas malformadas**: regeneradas las 26 que fallaban `openspec validate --specs --strict`. Hoy: **111 passed / 0 failed**.

---

## ⚠️ Reality check 2026-06-11 — rama "activeexam" (Postgres puro + screenshots) vs rama "full" (TimescaleDB + clips)

> Los proposals/designs originales fueron escritos asumiendo la **rama "full"** (TimescaleDB hypertables + continuous aggregates + clips de video). La realidad de producción (Railway con `Dockerfile.activeexam`) es la **rama "activeexam"** (Postgres puro + screenshots por evento). Diferencias clave que afectan a varios changes activos:
>
> | Concepto en designs | Realidad activeexam (hoy) | Aplica a |
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

> **Todo el ciclo MVP de revisión/legal ya está archivado**: c-16 (cola-revisión-humana), c-17 (DSR), c-18 (verificación cadena/apelación), c-19 (retención/holds) y c-20 (reportes/analytics) — los 5 con 100% de tasks completas (ver "Resumen por estado"). **Único pendiente real del camino crítico**: `c-03 → c-15b` (tiempo real del panel).
>
> **PARTICIÓN 2026-06-24**: c-10 y c-15 se **archivaron por su scope entregado** y lo que dependía de c-03 se movió a un sucesor. c-10: implementación del fan-out completa; la **verificación de SLO bajo carga** (p99<500ms, cero pérdida, e2e, OTEL) se consolidó en **c-03** (su harness es el banco de carga). c-15: se entregó el **activeexam** (chat/pausa/observaciones/cierre/RBAC vía REST+polling); el **tiempo real** (SSE, priorización por score, alertas <500ms, MFA) pasó a **c-15b**.

| Change | Progreso | Qué falta / scope | Dep | Estado |
|--------|----------|-------------------|-----|--------|
| **c-10** `event-ingestion-transport` | 26/26 | Contrato de evento, WS del estudiante, validación HMAC, persistencia hypertable y **fan-out** (puerto + adaptadores LISTEN/NOTIFY y Redis) entregados. Verificación de SLO bajo carga → **c-03**. | c-03 | ✅ **Archivado** (scope entregado) |
| **c-15** `panel-proctor-sse` | — | **ActiveExam entregado**: acciones del proctor (chat, observaciones, cierre forzado), pausa autorizada + contextualización de score, RBAC por rol. | c-10 ✓ | ✅ **Archivado** (activeexam) |
| **c-15b** `panel-proctor-sse-transport` | 0/10 | Tiempo real: transporte SSE sin sticky + backplane (ganador c-03); priorización por score (continuous aggregates c-13); alertas críticas p99<500ms; reconexión SSE; MFA del panel. | c-03, c-13 | ⛔ Bloqueado por c-03 |
| **c-16** `cola-revision-humana` | 15/15 | Cola por score + aislada por jurisdicción + audit de acceso + decisión humana terminal inmutable. | c-13, c-15 ✓ (activeexam) | ✅ **Archivado** (2026-06-11) |
| **c-17** `dsr-derechos-titular` | 20/20 | `POST /api/v1/dsr/{type}` access/rectification/erasure/portability + holds + audit log. | c-06 ✓ | ✅ **Archivado** (2026-06-11) |
| **c-18** `verificacion-cadena-apelacion` | 20/20 | `POST /api/v1/evidence/{id}/verify-chain` que re-verifica 4 etapas de firma + emite certificado independiente para perito externo. | c-12 ✓ | ✅ **Archivado** (2026-06-11) |
| **c-19** `retencion-holds` | 19/19 | Motor retención automática (activeexam: `RetentionEngine`, política default **180 días sesiones / 5 años audit log**, endpoints admin `POST /api/v1/admin/retention/{session,biometric}`) + holds por caso abierto (activeexam: `NullHoldVerifier`, no hay `caso_disciplinario` en activeexam) + eliminación embedding al egreso (Ley 25.326, RN-DSR-02). **Object Lock/WORM explícitamente fuera de alcance en activeexam** (sin MinIO — fotos como BYTEA en Postgres). ⚠️ **No hay cron/scheduler wireado** que invoque esos endpoints admin automáticamente — el motor existe pero nadie lo dispara todavía en producción; ver ítem de higiene en Prioridad 2. | c-07 ✓ | ✅ **Archivado** (2026-06-11) |
| **c-20** `reportes-analytics` | 25/25 | Reportes post-examen agregados (distribución scores, outliers, métricas calidad detector). **Sin veredictos automáticos.** | c-13 ✓, c-16 ✓ | ✅ **Archivado** (2026-08-03) |

**Leer antes**: la KB indicada por change en [CHANGES.legacy.md](CHANGES.legacy.md) (sección FASE 1) — o directamente `openspec/changes/archive/2026-06-11-c-1{6,7,8,9}-*/` y `openspec/changes/archive/2026-08-03-c-20-*/` para el detalle real implementado.

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

| **c-68** `configuracion-sistema-funcional` | ✅ archivado (2026-06-22) | **Configuración del Sistema funcional + consentimiento persistido** (no planificado; se le asignó el siguiente número libre). Backend (ola 1): tablas `configuracion_sistema` (singleton versionado: umbrales/detectores/retención) y `consentimiento_perfil` (append-only, atado a usuario, versionado/revocable, eliminación al egreso) en activeexam+full; API de config + `GET /config/effective`; API de consentimiento de perfil server-side; consumo server-side de scoring/umbrales (snapshot por sesión). Frontend (ola 2): admin (Proctoring/Detección/Consentimiento) cableado a la config real con escala amigable (segundos / Baja-Media-Alta / %); consentimiento contra backend (re-pedir, no migrar localStorage); el examen de prueba y TEST DETECCIÓN consumen la config viva con invalidación de cache. **L2.5 intacto** (la config prioriza/flaggea, no sanciona). Decisión del dueño: consentimiento implementado ya (sin gate de DPIA, se ajusta luego). **Sesión 2026-06-16 (ampliación aprobada por el dueño)**: fix de caché de scoring (editar peso se refleja en effective); evento `corte_conectividad_prolongado` crítico; **consentimiento con texto VERSIONADO editable** (tabla `consent_texto_version`; agregar/editar/eliminar cláusulas; publicar versión → re-consentimiento); **gestión de usuarios** (detalle de alumno con consentimiento+biometría sin exponer embedding, filtros server-side, reactivar, switch de estado); el examen **respeta `detectores_activos`**; la cola lee el umbral de la config (no 60 fijo) y excluye sesiones sin examen; rediseño UI completo de Configuración + Test Detección. Tests: backend 77 verde (áreas del change) + frontend 440 verde; tsc limpio. **Sesión 2026-06-22 (cierre)**: re-consentimiento en el Inicio del alumno (detecta versión desactualizada), auditoría `config_update` también en PATCH scoring, infra de test (NullPool + pin pytest-asyncio + rangos 0021). Áreas de C-68 70/70 verde. **ARCHIVADO** (7.1 smoke prod = post-deploy; 7.4 aceptación del dueño = OK). | c-54 ✓, c-59 ✓, c-65 ✓, c-67 ✓ (scoring/consent-gate/user-management archivados) | **MEDIO** (consentimiento = CRÍTICO Ley 25.326; resto MEDIO) |

**Leer antes**: `05_reglas_de_negocio.md` §RN-SC/§RN-CO, `13_legal_y_cumplimiento_argentina.md`, `04_modelo_de_datos.md`.

---

## 🔵 Prioridad — Examen en plataforma (Moodle + lockdown) — fuera del roadmap original

> Línea de trabajo **revivida por DD-20** (examen operado EN la plataforma con import Moodle XML + lockdown + write-back de nota), nacida fuera del plan original de 65 changes. **c-69** entregó la rendición completa (import, config por examen, rendición robusta, nota entera estilo Moodle, revisión, gate de visibilidad de resultados) y está **archivado** (2026-07-07). **c-70** (matriculación por código estilo Moodle, enrolment key) le siguió y está archivado. **c-71** es el sucesor directo: hizo que la inscripción de c-70 **realmente gatee** (c-70 explícitamente "NO altera puede_rendir"; c-71 SÍ) y entregó además la Cola de Revisión (slices 1+2, archivado). **c-72** continúa la línea: cierra la integridad de la rendición server-side (deadline efectivo, auto-finalización, candado direccional de config) y **absorbe las Sesiones Grabadas** que originalmente eran el slice 3 de c-71. Registrados a mano (no vinieron del `/roadmap-generator`); regenerar el roadmap formalmente cuando se cierre.

| Change | Progreso | Qué es / scope | Dep | Gov |
|--------|----------|----------------|-----|-----|
| **c-69** `examen-plataforma-moodle-lockdown` | ✅ archivado (2026-07-07) | Examen operado en la plataforma: import Moodle XML → pool de preguntas seleccionable, config por examen (timer/ventana/intentos/nota/shuffle), rendición robusta (sesión anti-zombie), nota entera ROUND_HALF_UP estilo Moodle, revisión post-examen, gate de visibilidad de resultados (Review options), write-back de nota a Moodle. | c-68 ✓ | MEDIO |
| **c-70** `matriculacion-por-codigo` | ✅ archivado (2026-07-07) | **Modelo enrolment-key de Moodle**: cada comisión gana un `codigo_matriculacion` único (autogenerado `{materia}-{sufijo}`, editable/rotable por el docente). El alumno se auto-matricula posteando el código (`POST /api/v1/exam-content/inscribirme`, auth-only, `usuario_id` del principal — NUNCA del body). Idempotente ante ya-inscripto; coexiste con la inscripción manual; NO altera el gate `puede_rendir` (**eso lo cierra c-71**). Migración activeexam `0038` aditiva en dos pasos con backfill. Frontend docente (código + copiar) + alumno (unirse con código). **Incluye hardening del enrollment biométrico contra inyección de embedding.** | c-69 ✓ | ALTO (endpoint de acceso + toca biometría) |
| **c-71** `inscripcion-gate-y-cola-revision` | ✅ archivado (2026-07-15, slices 1+2) | **Change de integridad de examen, entregado en dos slices.** **Slice 1 — gate de inscripción**: el alumno solo VE y solo RINDE exámenes de comisiones donde está inscripto por código. Catálogo (`listar_examenes_contenido`) y "Mis materias/comisiones" filtrados **server-side por rol** (staff ve todo); backstop **403 `no_inscripto`** en `crear_sesion` (cliente no confiable). Cierra el agujero que c-70 dejó abierto. **Slice 2 — Cola de Revisión + transparencia al alumno**: decisión en dos fases (revisar `revisar_sesion` / resolver `resolver_caso`), resolución `anulado_por_fraude` reversible por acto compensatorio append-only, gate de write-back a Moodle por estado de revisión, informe de devolución al alumno (Ley 25.326). Tests verdes (DB real). **Sesiones Grabadas (ex-slice 3) → reasignado a c-72.** | c-70 ✓ | ALTO (control de acceso + notas + disciplina) |
| **c-72** `integridad-rendicion-serverside` | ✅ archivado (2026-07-18, 121 tasks, 9 specs sincronizados) | **Cerró los agujeros de integridad de la rendición confirmados en vivo (H-1/H-2/H-3): la API rechazaba mal respuestas y `finalizar` fuera de tiempo/ventana.** Server-side: **deadline efectivo** (min(tiempo_limite, fin_ventana)) + **gracia**, **auto-finalización** de sesiones vencidas, **evento de reanudación** (con duración de ausencia), **candado direccional** de config (congelado-duro + cierre/intentos solo ampliar + publicación solo aflojar). Absorbió **Registro de sesiones** (ex-slice 3 de c-71, expediente sin video), **gestión de catálogo** (editar código, borrar solo si vacío, activar/desactivar materia con enforcement), **cifrado at-rest de evidencia** (Fernet, Ley 25.326), statcards unificadas y timeout de pausa. | c-71 ✓ | ALTO/CRÍTICO (integridad de examen, anti-tampering) |

| **c-73** `persistencia-carga-cliente` | ✅ archivado (2026-08-03, PR #25) | Write-back de nota Moodle **por-docente** (no por sistema), modelo de decisión de revisión colapsado a **3 estados en un solo paso** (no dos fases), cierre de auditoría/estadísticas. Specs sincronizadas: `client-session-persistence`, `moodle-campus-integration`, `resilient-data-loading`. | c-72 ✓ | MEDIO |
| **c-74** `banco-preguntas-categorias-cloze` | ✅ archivado (2026-08-10, PR #26) | Banco de preguntas por categorías + tipo cloze + sorteo + aislamiento por comisión + sync Moodle + seed tutor TUT-001. | c-73 ✓ | MEDIO |
| **c-75** `lti-auto-provisioning-moodle` | ✅ archivado (2026-08-13) | **Tool Provider LTI 1.3** completo: JWKS + registro dinámico, login OIDC, validación de launch (firma RS256, nonce anti-replay, aud/iss contra allowlist), **JIT provisioning** de alumnos (rol fijo estudiante, matrícula por mapeo `context_id→comisión`), allowlist admin CRUD, landing frontend, contraseña inicial LTI (1er ingreso define, 2do+ directo). Verificado end-to-end contra Moodle real (campustest). Revisión de seguridad enfocada sin hallazgos ≥8/10 de confianza. Specs sincronizadas: `lti-tool-provider`, `lti-jit-provisioning`, `lti-trust-config`, `user-registration`. | c-72 ✓ | CRÍTICO (Auth) |

**Leer antes**: el archivo de c-72 en `openspec/changes/archive/2026-07-18-c-72-integridad-rendicion-serverside/` (proposal/design/specs/tasks), el de c-71 en `openspec/changes/archive/2026-07-15-c-71-inscripcion-gate-y-cola-revision/`, y los de c-73/c-74/c-75 en sus respectivas carpetas `archive/2026-08-*-c-7{3,4,5}-*/`. `04_modelo_de_datos.md` §comisión/inscripción/sesión, `05_reglas_de_negocio.md` §RN-BIO (embedding = dato sensible, cliente no confiable) y §RN-SC (integridad de rendición).

---

## 🟠 Prioridad — Higiene / deuda técnica identificada (sin change formal todavía)

> Items reales encontrados en sesiones posteriores a C-72 que no tienen change propio. No cuentan en los pendientes del CLI.

| Ítem | Qué es | Gov |
|------|--------|-----|
| **Cron de retención** | El motor de C-19 (`RetentionEngine`) existe y sus endpoints admin están montados, pero **no hay ningún cron/scheduler configurado** que los invoque — la retención automática de 180 días no corre sola en producción hoy. | ALTO |
| **Evidencia a MinIO/WORM** | Screenshots y foto de referencia se guardan hoy como texto/BYTEA en Postgres (marcado "solo demo" en el propio código). Decisión del dueño: **MinIO self-hosted, NO S3** (S3 es pago). Sin change propio — hoy vive implícito en el scope no cubierto de C-19 (que excluyó Object Lock explícitamente por ser activeexam). | ALTO |
| **Rename ActiveExam → ActibeExam** | El dueño corrigió (dos veces) que el nombre del producto es **ActibeExam** (con b) en todo el código/UI. | BAJO |
| **Bug de autorización: tutor crea materias/comisiones** | `gestionar_academico` (que tiene TUTOR) hoy también habilita crear/editar materias y comisiones — debería ser solo `gestionar_estructura` (admin-only). Fix: separar capacidades. | CRÍTICO (Auth) |
| **Deploy cleanup** | Sacar Keycloak (no se usa, JWT propio + LTI) y otras piezas de referencia sin uso real de docker-compose/env templates antes del deploy productivo. | MEDIO |

---

## Árbol de dependencias (pendientes reales al 2026-08-13)

```
c-01-acuerdo-proctoria-dpia (0/23)                      ← gate legal, no-código
  └── c-03-poc-carga-mensajeria (24/45)                 ← absorbe verificación de SLO de c-10
        └── c-15b-panel-proctor-sse-transport (0/10)    ← tiempo real; dep c-03 + c-13
              └── (panel en vivo de producción)
```

Eso es **todo lo que queda pendiente en el CLI**. Todo el resto del árbol original (c-10, c-15 activeexam, c-16 a c-20, c-66 a c-75) está **archivado** — ver tablas arriba.

Planificado sin proponer:
  integracion-lms-lti (Fase 2, sin número — se le asigna el siguiente libre al proponerlo; **c-75 ya cubrió el Tool Provider LTI 1.3**, esto queda para NRPS/AGS/quizaccess si se retoma)

### Camino crítico restante (2 changes)

```
c-03 (Bloque 5, host 8+ cores) → c-15b (panel en vivo de producción)
```

(c-01 es gate legal independiente; corre en paralelo, no en serie con el código.)

### Plan de ataque con 3 agentes (foto al 2026-06-11 sesión 2)

| Paso | Agente A (MVP crítico) | Agente B (MVP desbloqueado) | Agente C (Gate paralelo) |
|------|------------------------|-----------------------------|--------------------------|
| 1 | (espera c-03 con host 8+ cores) | c-17 dsr-derechos-titular | c-01 acuerdo + DPIA (drafts legales) |
| 2 | c-16 cola-revision-humana (ya desbloqueado por el activeexam de c-15) | c-18 verificacion-cadena-apelacion | c-01 firma DPO |
| 3 | c-15b panel-proctor-sse-transport (tras veredicto c-03) | c-19 retencion-holds | — |
| 4 | c-20 reportes-analytics (tras c-16) | — | — |
| 5 | integracion-lms-lti (post-MVP, sin número aún) | — | — |

> Agente A camino crítico (depende de c-03 cerrado). Agente B avanza independiente en módulo legal/cumplimiento (DSR + cadena custodia + retención). Agente C corre la pista legal de c-01 en paralelo.

---

## Orden sugerido de ataque

1. **Recuperar c-03**: levantar host con 8+ cores (Codespaces Pro / AWS spot) y correr Bloque 5 — barrido P0→E6 — para cerrar veredictos (a/b/c). **Esto consolida la verificación de SLO que se descopeó de c-10 y desbloquea c-15b** (tiempo real del panel).
2. **En paralelo, c-16** (ya desbloqueado por el activeexam de c-15: consume las observaciones del proctor) **y c-17/c-18/c-19** (módulo legal/cumplimiento, deps archivadas). Ideal para varios agentes en paralelo.
3. **Cuando DPO esté disponible, c-01**: drafts de Acuerdo L2.5 + DPIA + Acta ADRs los puede preparar Claude desde la KB; firma humana cierra el gate.
4. **Tras veredicto c-03**: c-15b (panel en vivo de producción). c-20 tras c-16.
5. **Fase 2**: integración LMS/LTI (sin número aún, ver Prioridad 2) cuando el MVP esté operativo. **Análisis real del DNI** (server-side, OCR + PDF417 + RENAPER) sería un change nuevo separado cuando aparezca la necesidad — no reabrir c-39 (cancelado).

> Regla dura del proyecto (DD-19): la arquitectura de mensajería **la decide C-03**. No asumir A4 ni SAD antes de esa PoC.

---

## Resumen por estado

| Bucket | Changes | Tasks totales | Tasks completas |
|--------|---------|---------------|-----------------|
| Gate bloqueante (parcial) | c-01 (0/23), c-03 (24/45) | 68 | 24 |
| MVP bloqueado por c-03 | c-15b (0/10) | 10 | 0 |
| **Total pendientes (CLI)** | **3** | **78** | **24** |
| Archivados 2026-06-24 (scope entregado) | c-10, c-15 (activeexam) | — | — |
| Archivados ciclo revisión/legal (2026-06-11 / 2026-08-03) | c-16, c-17, c-18, c-19, c-20 | 99 | 99 |
| Archivados "examen en plataforma" (2026-07-07 → 2026-08-13) | c-69, c-70, c-71, c-72, c-73, c-74, c-75 | — | — |
| Archivados (resto: biometría, UI, config, etc.) | c-66, c-67, c-68 + anteriores | — | — |
| Cancelados (sin retomar) | 4 (c-02, c-39, c-44, c-53) | — | — |
| **Total universo (archive/ + pendientes)** | **76** | — | — |
| Planificado sin crear | integracion-lms-lti (Fase 2, sin número — parcialmente cubierto por c-75) | — | — |

> **Nota de higiene**: este archivo quedó desactualizado entre el 17-jul (último commit real que lo tocó, cierre de c-72) y el 13-ago (esta edición manual). Archivar un change con `openspec archive` **no** actualiza `CHANGES.md` automáticamente — es un paso aparte. Si volvés a ver esta nota vieja en una sesión futura, corré `openspec list --json` antes de confiar en las tablas de arriba.
