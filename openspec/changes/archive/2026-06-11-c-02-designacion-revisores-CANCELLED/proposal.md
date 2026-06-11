# Proposal — C-02 `designacion-revisores`

> **🚫 CANCELADO 2026-06-11**: El alcance se reduce a "asignar rol `proctor` a un usuario", que se resuelve directamente con C-52 (Keycloak realm) + C-61 (gestión de usuarios, ya archivado). No amerita un change de 30 tasks organizacionales — la capacitación de revisores queda como tarea operativa fuera del roadmap de software.
> **Decisión del dueño**: el equipo humano se forma cuando la plataforma entre en producción real; no es un gate de desarrollo.

> **Naturaleza del change**: gate **organizacional de Fase 0**, governance **CRÍTICO**, **NO-CÓDIGO**. No produce software de dominio. Sus entregables son de gestión / RRHH / capacitación: un equipo humano de revisión designado, capacitado y con capacidad sostenida confirmada por escrito. Corre **en paralelo a C-01** (no tiene dependencias técnicas) y, junto a él, es la **precondición dura** para que arranque cualquier desarrollo.

## Why

El factor de riesgo dominante del proyecto **no es tecnológico sino organizacional**: el compromiso institucional sostenido, y en particular la **capacidad de revisión humana** (KB 15 §cierre estratégico). Es **la dependencia más subestimada del proyecto** (SU-03), y el riesgo O-003 ("capacidad insuficiente de revisión humana", impacto **Alto**, estado *acción del cliente*) es su materialización.

La lógica es directa y no negociable: el sistema opera a nivel **L2.5** y **nunca sanciona automáticamente** (DD-01). El score de riesgo **prioriza, no emite veredicto**; la decisión disciplinaria final es **siempre humana** (RACI: Revisor responsable, Coordinador aprobador, Dirección académica decisión terminal). Por eso, **aunque el código de la cola de revisión (C-16) exista y funcione perfecto, sin el equipo humano que la atienda el sistema NO cumple su propósito**: la evidencia se acumula en backlog, las sesiones flaggeadas no se resuelven y la garantía probatoria se vuelve teórica. C-02 es el change que **provee al humano** que toda la arquitectura presupone.

Por eso es **co-bloqueante del camino crítico**: la cadena `C-01 → C-03 → … → C-15 → C-16*` se cierra en C-16, pero C-16 solo cumple su propósito si C-02 está en `[x]`. Estimar tarde la carga de revisión y descubrir en Fase 1 que no hay revisores capacitados es el modo de fracaso más caro y más probable de todo el roadmap.

## What Changes

Este change **no modifica código ni infraestructura**. Formaliza y deja confirmados por escrito los siguientes entregables de capacidad organizacional, antes del inicio de Fase 1:

- **Modelo de dimensionamiento humano** que estime la carga de revisión a partir de la **tasa esperada de sesiones flaggeadas (5–15%)** aplicada al **volumen objetivo** (1.000 concurrentes sostenido / ~2.100 pico multi-examen, SU-06), traduciéndola a un número de revisores y de coordinadores con capacidad sostenida.
- **Designación nominal de revisores académicos por jurisdicción** (RBAC contextual: cada revisor cubre su área) y de **coordinación operativa**, con suplentes/doble cobertura para los picos.
- **Plan de capacitación por rol** (proctor en vivo, revisor académico, coordinador operativo, on-call/TI), cubriendo: criterio de decisión sobre evidencia, las **tres decisiones terminales** (descartar / escalar / derivar a disciplina), acceso auditado con **propósito declarado**, MFA, límites del sistema (sin sanción automática) y manejo de falsos positivos.
- **Mecanismo de monitoreo de backlog de revisión** definido (umbrales de alerta, responsable de escalado, frecuencia de revisión del capacity model) para detectar a tiempo si SU-03 empieza a fallar.
- **Confirmación por escrito de capacidad sostenida**: la dirección académica firma que el equipo nominado y capacitado puede sostener la revisión del 5–15% de las sesiones al volumen objetivo, de forma continua (no solo durante el piloto).
- **Plan de gestión del cambio asociado** (KB 15 §Gestión del cambio): doble cobertura en picos, simulacros y vínculo con la capacitación de on-call (que comparte O-001).

**BREAKING (gate)**: hasta que estos entregables estén confirmados/firmados, **el roadmap no debe cerrar Fase 0**. C-16 (cola de revisión humana) podrá construirse técnicamente en Fase 1, pero **no cumple su propósito** mientras C-02 no esté en `[x]`. Es un bloqueo deliberado de propósito, no una regresión técnica.

## Capabilities

> Estas "capabilities" son de **capacidad organizacional / governance**, no de software. Cada una representa un entregable de gestión cuyo estado (designado / capacitado / confirmado por escrito) es verificable. No introducen código, endpoints ni esquema; fijan el **equipo humano** sobre el que descansa el propósito del sistema.

### New Capabilities

- `review-capacity-sizing`: el **modelo de dimensionamiento humano** — estima la carga de revisión (5–15% de las sesiones al volumen objetivo de 1.000/~2.100) y la traduce a número de revisores y coordinadores con capacidad sostenida (SU-03, SU-06, O-003).
- `reviewer-designation`: la **designación nominal** de revisores académicos por jurisdicción y de coordinación operativa, con suplentes y doble cobertura para picos (KB 03 §RACI/RBAC).
- `role-training-plan`: el **plan de capacitación por rol** (proctor, revisor, coordinador, on-call) ejecutado y verificado, incluyendo criterio de decisión, decisiones terminales, acceso auditado con propósito y límites del sistema (KB 15 §Gestión del cambio).
- `backlog-monitoring`: el **mecanismo de monitoreo de backlog** de revisión — umbrales, responsable de escalado y cadencia de re-validación del capacity model para detectar la falla de SU-03 a tiempo (Flujo 7 §caso de error).
- `sustained-capacity-signoff`: la **confirmación por escrito de capacidad sostenida** firmada por la dirección académica — el entregable terminal que cierra el gate.

### Modified Capabilities

(Ninguna — es un gate organizacional independiente; no hay specs de software previas que modificar. Habilita el propósito de la capability futura de C-16, pero no la modifica aquí.)

## Impact

- **Co-bloquea**: el **cierre de Fase 0** junto a C-01 (acuerdo/DPIA) y C-03 (PoC de carga). Sin C-01 ✓ y C-02 ✓ no se desbloquea el desarrollo (GATE 1).
- **Habilita el propósito de**: C-16 (cola-revision-humana) — el cierre del ciclo MVP. C-16 puede codificarse sin C-02, pero **no cumple su propósito** sin el equipo humano que C-02 provee. También alimenta el panel de proctor (C-15) y comparte la capacitación de on-call con la resiliencia operacional (O-001).
- **Dependencias entrantes**: **ninguna**. Puede iniciarse de inmediato y corre en paralelo a C-01.
- **Actores/áreas afectadas**: **dirección académica** (responsable del entregable), **coordinación operativa** (Diego), **revisores académicos** (Lucía) por jurisdicción, **proctors en vivo** (Martín), **on-call/TI** (Pablo), **RRHH/capacitación** y **patrocinador** (recibe la confirmación de capacidad). No afecta código ni infraestructura.
- **Riesgos mitigados**: **O-003** (capacidad insuficiente de revisión humana) — pasa de "acción del cliente" a gestionado; **SU-03** validado antes de Fase 1; aporta a **O-001** (on-call) vía capacitación compartida; reduce el riesgo de **R-002** (evidencia razonable vs. prueba) al asegurar revisores capacitados que sostienen la cadena de decisión.
- **Riesgo si se omite o subestima**: la evidencia se acumula sin revisión, el backlog crece, las sesiones flaggeadas no se resuelven y **el sistema falla en su propósito** pese a tener todo el código operativo (Flujo 7 §caso de error).
