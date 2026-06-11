# CHANGES — Roadmap de pendientes

> Índice **solo de lo que falta** del proyecto **Proctoring** (plataforma self-hosted de supervisión asistida por IA de evaluaciones remotas).
> Regenerado el **2026-06-11** a partir del estado real del CLI de OpenSpec (`openspec list --json`), no del optimismo.
> El plan original completo (los 65 changes, hechos y pendientes) quedó archivado en **[CHANGES.legacy.md](CHANGES.legacy.md)**.

---

## Cómo usar este documento

1. La **fuente de verdad del progreso es el CLI**: `openspec status --change "<nombre>"`. Un change entra acá si `completedTasks < totalTasks`.
2. Respetá las dependencias: no arranques un change cuyas deps sigan abiertas.
3. Flujo: `/opsx:propose` (si falta) → `/opsx:apply` → `/opsx:archive`. Al archivar, el change sale de este roadmap.
4. Regenerá este archivo con `/roadmap-generator` cuando cambie el estado (no lo edites a mano para "tildar").

> **Foto al 2026-06-11**: 65 changes totales · **46 archivados** (cerrados y versionados) · **19 pendientes** (abajo).

---

## ⛔ Prioridad 0 — Gates bloqueantes de Fase 0 (el CLI los ve en 0/N)

> ⚠️ El CLI marca estos tres en **0 tasks completas**. Si el trabajo (acuerdo legal, revisores, PoC) ya se hizo en la realidad pero nadie tildó las tasks, **tildalas y salen de acá**. Mientras el CLI los vea en 0, son pendientes — y son precondición dura del resto.

| Change | Progreso | Qué es | Dep | Gov |
|--------|----------|--------|-----|-----|
| **c-01** `acuerdo-proctoring-dpia` | 0/23 | Acuerdo de Nivel de Proctoring firmado + **DPIA** completo + 14 ADRs aprobados. No-código. | — | CRÍTICO |
| **c-02** `designacion-revisores` | 0/30 | Designación y capacitación de **revisores humanos** + coordinación operativa. La dep más subestimada (SU-03). No-código. | — | CRÍTICO |
| **c-03** `poc-carga-mensajeria` | 0/25 | PoC de carga al **pico (~2.100 concurrentes / ~5.000 inserts/s)** que **decide** cola/transporte/backplane (A4 vs SAD). Bloquea todo lo de tiempo real. | c-01, c-02 | CRÍTICO |

**Leer antes**: `13_legal_y_cumplimiento_argentina.md`, `09_decisiones_y_supuestos.md` §DD-14…DD-19, `14_observabilidad_y_devops.md` §SLOs/Capacity, `10_preguntas_abiertas.md`.

---

## 🟡 Prioridad 1 — MVP original sin terminar (camino crítico)

> Camino crítico restante: `c-03 → c-04 → c-10 → c-15 → c-16`. c-17, c-18, c-19 están desbloqueados y pueden correr en paralelo.

| Change | Progreso | Qué falta / scope | Dep | Estado |
|--------|----------|-------------------|-----|--------|
| **c-04** `foundation-setup` | 19/20 | Cerrar la última task de la fundación (monorepo/compose/Alembic/observabilidad). | c-03 | Bloqueado por gate c-03 |
| **c-10** `event-ingestion-transport` | 22/26 | WS del estudiante + validación de firma por evento + fan-out (ganador C-03). Faltan 4 tasks. | c-09 ✓ | **Listo para arrancar** |
| **c-15** `panel-proctor-sse` | 0/16 | Supervisión en vivo vía SSE; alertas críticas <500 ms; cierre forzado de sesión. | c-10 | Bloqueado por c-10 |
| **c-16** `cola-revision-humana` | 0/15 | Cola por score + audit de acceso + decisión humana. **Cierre del ciclo MVP.** Requiere c-02. | c-15, c-02 | Bloqueado por c-15 y c-02 |
| **c-17** `dsr-derechos-titular` | 0/20 | Derechos del titular (acceso/rectificación/eliminación/portabilidad) + holds. | c-06 ✓ | **Listo para arrancar** |
| **c-18** `verificacion-cadena-apelacion` | 0/20 | `POST verify-chain` + certificado de cadena de firmas para perito externo. | c-12 ✓ | **Listo para arrancar** |
| **c-19** `retencion-holds` | 0/19 | Políticas de retención automáticas + hold por caso (difiere eliminación). | c-07 ✓ | **Listo para arrancar** |
| **c-20** `reportes-analytics` | 0/19 | Reportes y analytics (Fase 2). | c-13 ✓, c-16 | Bloqueado por c-16 |

**Leer antes**: la KB indicada por change en [CHANGES.legacy.md](CHANGES.legacy.md) (sección FASE 1).

---

## 🔵 Prioridad 2 — Changes extra en progreso (track demo/slim, post-roadmap)

> Agregados después del roadmap original (pista paralela demo/slim sobre Vercel+Railway). Varios a un paso de cerrar.

| Change | Progreso | Qué falta / scope | Gov |
|--------|----------|-------------------|-----|
| **c-32** `harness-motor-cache-ux` | 29/32 | Cachear el motor de visión (no recompilar WASM por ciclo) + UX sin jerga + permiso `window-management`. 3 tasks. | MEDIO |
| **c-34** `biometria-perfil-funcional` | 41/45 | Liveness real en el enrollment (hoy mock de botones + embedding random) + fullscreen móvil. 4 tasks. | ALTO |
| **c-35** `fixes-deteccion-camara-mirada` | 17/20 | Bugs del harness: frame congelado al volver a la página + umbral de mirada inalcanzable. 3 tasks. | MEDIO |
| **c-39** `analisis-validacion-dni` | 28/32 | UI de análisis indicativo del DNI capturado (mock client-side, disclaimer L2.5). 4 tasks. | MEDIO |
| **c-44** `creacion-examenes-ui` | 0/40 | Validación inline en `ConfigureExam.tsx` (hoy `alert()`), feedback de guardado, preview. | MEDIO |
| **c-52** `keycloak-realm-config` | 0/20 | Crear realm `proctoring` + clients + usuarios + audience mapper (hoy `start-dev` sin realm). | ALTO |
| **c-53** `vision-mesh-objetos` | 12/33 | Mesh + detección de objetos + separar diagnóstico de staff de la experiencia del alumno. | MEDIO |
| **c-56** `persistencia-biometrica-referencia` | 23/33 | Persistir foto + embedding de referencia en backend (hoy en localStorage/memoria) — habilita 1:1 real. | ALTO |

---

## Árbol de dependencias (pendientes)

```
c-01-acuerdo-proctoring-dpia (0/23)
c-02-designacion-revisores (0/30)
  └── c-03-poc-carga-mensajeria (0/25)
        └── c-04-foundation-setup (19/20)
              └── c-10-event-ingestion-transport (22/26)  ← también listo independientemente
                    └── c-15-panel-proctor-sse (0/16)
                          └── c-16-cola-revision-humana (0/15)  [también dep c-02]
                                └── c-20-reportes-analytics (0/19)

Desbloqueados hoy (deps ya archivadas):
  c-10-event-ingestion-transport (22/26)  [c-09 ✓]
  c-17-dsr-derechos-titular (0/20)        [c-06 ✓]
  c-18-verificacion-cadena-apelacion (0/20) [c-12 ✓]
  c-19-retencion-holds (0/19)             [c-07 ✓]

Track paralelo demo/slim (sin dep dura del camino crítico):
  c-32-harness-motor-cache-ux (29/32)
  c-34-biometria-perfil-funcional (41/45)
  c-35-fixes-deteccion-camara-mirada (17/20)
  c-39-analisis-validacion-dni (28/32)
  c-44-creacion-examenes-ui (0/40)
  c-52-keycloak-realm-config (0/20)
  c-53-vision-mesh-objetos (12/33)
  c-56-persistencia-biometrica-referencia (23/33)
```

### Camino crítico restante (5 changes)

```
c-03 → c-04 → c-10 → c-15 → c-16 → c-20
```

### Plan de ataque con 3 agentes (foto al 2026-06-11)

| Paso | Agente A (MVP crítico) | Agente B (MVP desbloqueado) | Agente C (track slim/demo) |
|------|------------------------|-----------------------------|-----------------------------|
| 1 | c-10 event-ingestion-transport (cerrar 4 tasks) | c-17 dsr-derechos-titular | c-32 harness-motor-cache-ux |
| 2 | c-15 panel-proctor-sse | c-18 verificacion-cadena-apelacion | c-34 biometria-perfil-funcional |
| 3 | — (espera c-02 y c-15) | c-19 retencion-holds | c-35 fixes-deteccion-camara-mirada |
| 4 | c-16 cola-revision-humana | — | c-39 analisis-validacion-dni |
| 5 | c-20 reportes-analytics | — | c-53 vision-mesh-objetos |
| 6 | — | — | c-44 creacion-examenes-ui |
| 7 | — | — | c-52 keycloak-realm-config |
| 8 | — | — | c-56 persistencia-biometrica-referencia |

> Agentes A y B terminan en 5 pasos (c-20 es el cierre del ciclo MVP). Agente C tiene 8 steps de track demo/slim.

---

## Orden sugerido de ataque

1. **Resolver los gates** (c-01/c-02/c-03): tildarlos si ya se hicieron, o ejecutarlos. Sin esto, el camino crítico del MVP queda formalmente bloqueado.
2. **Cerrar los "casi listos"** (1–4 tasks): c-04, c-10, c-32, c-34, c-35, c-39. Victorias rápidas que limpian el tablero.
3. **Camino crítico del MVP**: c-10 → c-15 → c-16 (cierra el ciclo extremo-a-extremo) + los desbloqueados c-17/c-18/c-19 en paralelo.
4. **Track demo/slim**: c-53, c-44, c-52, c-56.
5. **Fase 2**: c-20 (reportes, requiere c-16 cerrado).

> Regla dura del proyecto (DD-19): la arquitectura de mensajería **la decide C-03**. No asumir A4 ni SAD antes de esa PoC.

---

## Resumen por estado

| Bucket | Changes | Tasks totales | Tasks completas |
|--------|---------|---------------|-----------------|
| Gate bloqueante (0%) | c-01, c-02, c-03 | 78 | 0 |
| MVP casi listo (≥75%) | c-04, c-10, c-32, c-34, c-35, c-39, c-56 | 198 | 159 |
| MVP sin empezar (0%) | c-15, c-16, c-17, c-18, c-19, c-20, c-44, c-52 | 169 | 0 |
| Parcial (track slim) | c-53 | 33 | 12 |
| **Total pendientes** | **19** | **478** | **171** |
| Archivados | 46 | — | — |
| **Total universo** | **65** | — | — |
