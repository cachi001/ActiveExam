# Proposal — C-16 `cola-revision-humana`

> **Naturaleza del change**: feature de producción, governance **ALTO**. **Cierra el ciclo MVP** (verificación → examen → evidencia → **revisión humana**) — US-012, FR-12, UC-04, Flujo 7. **Depende de C-15** (panel/observaciones) y **requiere C-02** (revisores designados y capacitados) para cumplir su propósito (SU-03). **Principio inviolable**: el sistema NUNCA sanciona automáticamente; la decisión final es **siempre humana** (RN-RV-07, DD-01).

## Why

Este change es la **razón de ser del sistema**. Todo lo anterior — biometría, eventos, evidencia firmada, score — existe para alimentar **una decisión humana informada y trazable**. El score prioriza (C-13), pero **no juzga**; el panel supervisa (C-15), pero no resuelve casos. La revisión humana asíncrona es donde un revisor académico (Lucía, `03`) mira el contexto completo de una sesión sospechosa y **decide con criterio**.

El discovery es categórico (RN-RV-07, RN-DSR-04, DD-01): **ninguna sanción es automática; la decisión disciplinaria final es siempre humana**. El sistema **prioriza y presenta evidencia**, pero la resolución terminal (descartar / escalar / derivar a disciplina) la emite una persona, con propósito declarado y traza inmutable. Esto cumple por arquitectura el derecho de oposición a decisiones automatizadas.

Hay una dependencia **co-bloqueante subestimada** (SU-03, C-02): sin revisores **designados y capacitados** y capacidad sostenida de revisión (5–15% de sesiones, RN-RV-01), la cola se acumula y el sistema **falla en su propósito aunque el código exista** (Flujo 7 §casos de error). Por eso C-16 requiere C-02 cerrado.

## What Changes

Implementa la cola de revisión asíncrona extremo a extremo (Flujo 7, US-012):

- **Cola ordenada por score descendente**, **filtrada por jurisdicción** del revisor (RN-RV-02, RN-AU-07): solo ve las sesiones flaggeadas de su área.
- **Apertura de sesión auditada**: cada apertura por un revisor se registra en el **audit log con propósito declarado** (RN-RV-03); cada acceso a evidencia se audita.
- **Contexto completo** (RN-RV-04): línea de tiempo de eventos, **clips firmados** (vía URL firmada de 15 min, RN-CC-05), **observaciones del proctor** (de C-15), output de **re-inferencia** server-side (de C-12), y **audit log de accesos previos**.
- **Decisión terminal** (RN-RV-05): exactamente **una de tres** — **descartar** (falso positivo) | **escalar** (investigación adicional) | **derivar a proceso disciplinario** formal; persistida **inmutable** vinculada a la evidencia (RN-RV-06).
- **No-sanción automática** (RN-RV-07, DD-01): el sistema **NUNCA** emite la decisión; la decisión terminal es **siempre humana**. La derivación a disciplina abre un `Caso disciplinario` cuya resolución final es humana (RACI: dirección académica).

**Decisiones consumidas (no se re-deciden aquí)**:
- El **score y su orden** (sesiones flaggeadas) vienen de C-13; el revisor recibe la cola ya ordenada.
- Los **clips firmados, hashes, firma maestra y re-inferencia** vienen de C-12 (cadena de custodia); aquí se **leen** vía URL firmada de 15 min.
- Las **observaciones del proctor** vienen de C-15; el **audit log** append-only de C-12/C-05; el **RBAC contextual + MFA** de C-06.

**BREAKING**: ninguno. **Cierra el ciclo MVP**: con C-16 el sistema cumple su propósito extremo a extremo (cumple junto con C-02).

## Capabilities

> Cada SHALL se prueba con un test (orden por score, aislamiento por jurisdicción, audit de cada apertura, persistencia inmutable de decisión).

### New Capabilities

- `review-queue-ordering`: la cola de revisión ordenada por score descendente y filtrada por la jurisdicción del revisor (aislamiento por área).
- `review-session-context`: la apertura de sesión auditada (audit log con propósito declarado) con acceso al contexto completo — línea de tiempo, clips firmados vía URL 15 min, observaciones del proctor, re-inferencia y audit log de accesos previos.
- `review-terminal-decision`: la decisión terminal humana (descartar | escalar | derivar a disciplina), persistida inmutable vinculada a la evidencia, garantizando que el sistema nunca sanciona automáticamente.

### Modified Capabilities

<!-- Ninguna spec de dominio previa en openspec/specs/. El score (C-13), la evidencia/audit log (C-12), las observaciones (C-15) y el RBAC (C-06) son dependencias de implementación, no specs a modificar aquí. -->

(Ninguna — este change agrega capacidades nuevas; no modifica requisitos ya especificados en `openspec/specs/`.)

## Impact

- **Cierra el ciclo MVP**: último change indispensable del camino crítico (`… → C-15 → C-16`); con él, el sistema cumple su propósito extremo a extremo (verificación → examen → evidencia → revisión humana).
- **Dependencias entrantes**: `C-15` (panel/observaciones del proctor + transporte), y transitivamente `C-13` (sesiones flaggeadas ordenadas por score), `C-12` (clips firmados + re-inferencia + audit log), `C-06` (RBAC contextual + MFA), `C-05` (`Caso disciplinario`, `Audit log`).
- **Co-dependencia organizacional**: `C-02` — sin revisores **designados, capacitados y con capacidad sostenida** (SU-03), la cola se acumula y el sistema falla en su propósito aunque el código exista. **C-16 requiere C-02 cerrado.**
- **Decisiones que consume**: orden por score (C-13), evidencia firmada + URL 15 min (C-12), observaciones (C-15).
- **Actores/sistemas afectados**: revisor académico (Lucía — opera la cola y decide), coordinador (aprueba según RACI), dirección académica (decisión disciplinaria final), audit log, `Caso disciplinario`.
- **Garantía de gobernanza (load-bearing)**: refuerza por arquitectura "ninguna sanción automática" (RN-RV-07, RN-DSR-04, DD-01) — el sistema presenta y prioriza; **la persona decide**. Esto es parte del contrato de C-01.
- **Riesgo principal**: backlog de revisión acumulado por capacidad humana insuficiente (SU-03). Mitigación: C-02 (capacidad sostenida confirmada) + métrica de profundidad de la cola de revisión (`14`).
