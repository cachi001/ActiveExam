# Tasks — C-16 `cola-revision-humana`

> Implementa la cola de revisión asíncrona — orden por score, aislamiento por jurisdicción, apertura auditada, contexto completo y decisión terminal humana inmutable. **Cierra el ciclo MVP.** Principio inviolable: el sistema NUNCA sanciona automáticamente. El Done de cada tarea es un test verde.

## 1. Cola ordenada y aislada (capability `review-queue-ordering`)

- [ ] 1.1 Construir la cola leyendo **sesiones flaggeadas** (de C-13), ordenadas por **score descendente** (RN-RV-02); Done: test de orden por score desc
- [ ] 1.2 Filtrar por **jurisdicción** del revisor (RN-RV-01, RN-AU-07); Done: test de aislamiento por jurisdicción
- [ ] 1.3 Rechazar acceso a sesiones de otra jurisdicción; Done: test de rechazo

## 2. Apertura auditada y contexto completo (capability `review-session-context`)

- [ ] 2.1 Apertura de sesión escribe **audit log con propósito declarado** (RN-RV-03); Done: test de audit en cada apertura
- [ ] 2.2 Ensamblar el **contexto completo** de solo lectura: timeline de eventos, clips firmados, observaciones del proctor (C-15), re-inferencia (C-12), audit log previo (RN-RV-04); Done: test de contexto completo
- [ ] 2.3 Servir clips vía **URL firmada de 15 min** (RN-CC-05), auditando cada acceso con propósito; Done: test de URL caduca + acceso auditado
- [ ] 2.4 Garantizar solo-lectura sobre la evidencia (WORM, no alterable por el revisor); Done: test de inmutabilidad de la evidencia accedida

## 3. Decisión terminal humana inmutable (capability `review-terminal-decision`)

- [ ] 3.1 Capturar **una de tres** resoluciones: descartar | escalar | derivar a disciplina (RN-RV-05); Done: test de exactamente una resolución
- [ ] 3.2 Derivar a disciplina abre un **`Caso disciplinario`** vinculado a la evidencia (RACI: dirección académica); Done: test de apertura de caso
- [ ] 3.3 Persistir decisión + fundamento **inmutables** vinculados a la evidencia (RN-RV-06); Done: test de persistencia inmutable no editable

## 4. Garantía de no-sanción automática (capability `review-terminal-decision`)

- [ ] 4.1 Verificar que **ningún path** emite sanción/decisión disciplinaria automática (RN-RV-07, RN-DSR-04, DD-01); Done: test exhaustivo de ausencia de veredicto automático
- [ ] 4.2 Verificar que un score muy alto **prioriza pero NO deriva ni sanciona** solo; requiere acción humana explícita; Done: test de no-auto-derivación por score

## 5. Backlog y cierre del ciclo MVP

- [ ] 5.1 Instrumentar la **profundidad de la cola de revisión** como métrica de negocio (`14`, SU-03) para vigilar el backlog; Done: métrica visible en Prometheus
- [ ] 5.2 Documentar la co-dependencia con **C-02** (revisores designados/capacitados): sin capacidad humana sostenida la cola se acumula; Done: dependencia organizacional registrada
- [ ] 5.3 Test e2e de cierre de ciclo: sesión flaggeada → revisor abre (audit) → contexto completo → decisión terminal inmutable; Done: ciclo MVP verde extremo a extremo
