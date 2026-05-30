# Design — C-01 `acuerdo-proctoring-dpia`

> **Aclaración de naturaleza**: este NO es un design técnico de software. Es el design de un **gate organizacional/legal**. Documenta el proceso de aprobación, **qué decisiones quedan congeladas** al firmarse y **qué riesgos legales mitiga**. No hay arquitectura de código, schemas de datos ni endpoints.

## Context

El proyecto Proctoring es una plataforma self-hosted de supervisión IA de exámenes remotos (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO), bajo Ley 25.326 (Argentina), con NFR de 1.000 concurrentes sostenido / ~2.100 pico. El discovery dejó:

- **19 decisiones de arquitectura** sin aprobación formal: 14 ADRs Tier 1 (DD-01…DD-14) + 5 revisiones del análisis independiente A4 (DD-15…DD-19). Algunas de las revisiones A4 **sustituyen** decisiones del SAD original (RabbitMQ→Postgres-como-cola, WebSocket+sticky→SSE+backplane); aprobar el set completo evita que el equipo construya sobre decisiones en conflicto.
- **Cuestiones legales abiertas**: DPIA no realizado, base legal del tratamiento biométrico no formalizada, clasificación del embedding ambigua (IN-04), inscripción AAIP pendiente.
- **Una brecha de expectativas latente** (L-004): sin un Acuerdo de Nivel de Proctoring, el patrocinador podría esperar garantía probatoria absoluta que L2.5 no ofrece.

**Constraints**:
- El marco legal argentino está **en reforma**; el diseño legal debe anticipar el estándar más exigente (RGPD/LGPD-like) para evitar retrabajo.
- "No constituye asesoramiento legal": el DPO/área legal es el decisor final; este change orquesta, no reemplaza, el juicio legal.
- Es la Fase 0: **no se escribe código de dominio** hasta cerrar este gate.

**Stakeholders**: patrocinador, dirección académica, DPO/área legal, AAIP (registro de bases), equipo técnico (receptor de los ADRs congelados), representación estudiantil (comunicación de transparencia).

## Goals / Non-Goals

**Goals:**
- Dejar **firmado** el Acuerdo de Nivel de Proctoring L2.5 con finalidad acotada, límites deliberados y RACI.
- Dejar **aprobado por el DPO** un DPIA completo con base legal, proporcionalidad, derechos del titular e inscripción AAIP planificada.
- Dejar **aprobada y congelada** la línea base de los 19 ADRs (DD-01…DD-19) como contrato técnico.
- Resolver **IN-04** clasificando el embedding como sensible por defecto (SU-08), con firma del DPO.
- Decidir y documentar la **vía alternativa sin biometría** y la **existencia de población menor de 18**.
- Mitigar los riesgos legales L-001, L-002, L-004 antes de tocar código.

**Non-Goals:**
- NO implementar ninguna funcionalidad de software (eso empieza en C-04+).
- NO validar la arquitectura bajo carga — eso es C-03 (PoC de carga), un change distinto.
- NO designar ni capacitar revisores humanos — eso es C-02, change paralelo.
- NO fijar valores numéricos de umbrales (score, distancia coseno) — son decisiones de calibración de Fase 1/2.
- NO redactar el texto legal definitivo del DPIA dentro de OpenSpec; el área legal lo produce con sus herramientas. Aquí se rastrea el **estado** (completo/aprobado/firmado).

## Decisions

### D1 — Modelar el gate como capacidades de governance verificables, no como código
**Decisión**: cada entregable legal/administrativo se modela como una "capability" con requisitos cuyo Done es un documento firmado/aprobado, verificable por inspección.
**Por qué**: permite que el CLI openspec rastree el estado del gate con la misma maquinaria que un change de software, sin forzar una semántica de código que no aplica.
**Alternativa considerada**: dejar el gate fuera de OpenSpec como checklist suelto → se pierde trazabilidad y la dependencia de bloqueo no queda explícita en el grafo de changes.

### D2 — Aprobar los 19 ADRs como un único acto, no ADR por ADR disperso
**Decisión**: un acta única que apruebe DD-01…DD-19 en conjunto, registrando que las revisiones A4 (DD-15…DD-19) **prevalecen** sobre las piezas del SAD original que sustituyen, con las opciones del SAD documentadas como evolución condicionada a métricas de C-03.
**Por qué**: evita el estado inconsistente de "DD-06 (RabbitMQ) aprobado" y "DD-15 (Postgres-como-cola) aprobado" sin jerarquía. El acta fija explícitamente que para el MVP rige A4.
**Alternativa considerada**: aprobar solo los 14 Tier 1 y dejar A4 como "recomendación" → el equipo no sabría qué construir; reintroduce IN-01/IN-02.

### D3 — Resolver IN-04 hacia el estándar más exigente (embedding = sensible por defecto)
**Decisión**: clasificar el embedding como sensible por defecto (SU-08), aunque la Resolución AAIP 4/2019 podría no exigirlo siempre.
**Por qué**: el costo de sobre-proteger es bajo (cifrado at-rest ya previsto); el de sub-proteger es alto (exposición legal, caso SRFP). Anticipa la reforma que define el biométrico como categoría sensible.
**Alternativa considerada**: clasificar caso por caso según AAIP 4/2019 → introduce ambigüedad jurídica y riesgo de sub-protección.

### D4 — DPIA como precondición dura (gate), no como tarea paralela al desarrollo
**Decisión**: el DPIA aprobado por el DPO bloquea el inicio de cualquier change de dominio.
**Por qué**: producir el DPIA "mientras se codifica" es la falla clásica; si el DPIA cambia el diseño (p. ej. minimización), genera retrabajo masivo.
**Alternativa considerada**: DPIA en paralelo a Fase 1 → contradice la recomendación de cierre estratégico ("no saltar la Fase 0").

### D5 — Vía alternativa sin biometría como condición del consentimiento libre
**Decisión**: tomar una decisión explícita sobre ofrecer (o no) una vía sin biometría, antes de diseñar el consentimiento (C-08).
**Por qué**: sin alternativa, el consentimiento podría no ser "libre" y la base legal se cae; la relación académica no puede usarse para forzarlo.
**Alternativa considerada**: dejarlo para Fase 1 → arriesga rediseñar el flujo de consentimiento ya construido.

## Decisiones congeladas al aprobarse este change

| ADR | Decisión que queda congelada | Consume (downstream) |
|-----|------------------------------|----------------------|
| DD-01 | Nivel L2.5 | C-04, C-11 |
| DD-02 | Procesamiento en cliente (client-heavy) | C-11 |
| DD-03 | Biometría con liveness desde el MVP | C-09 |
| DD-04 | Anti-tampering pasivo (modo log, no abort) | C-04, C-11 |
| DD-05 | TimescaleDB para eventos (hypertable) | C-10 |
| DD-06→DD-15 | Mensajería: **Postgres-como-cola** en MVP (RabbitMQ como evolución medida) | C-03, C-10 |
| DD-07 | Cadena de custodia WORM + firmas encadenadas + audit log inmutable | C-12, C-18 |
| DD-08→DD-16 | Transporte: **SSE + backplane** para el panel (WebSocket solo estudiante) | C-03, C-15 |
| DD-09 | Keycloak como IdP | C-06 |
| DD-10 | FastAPI mono-hilo escalado horizontalmente | infra Fase 1 |
| DD-11 | Docker Compose inicial, twelve-factor | infra Fase 1 |
| DD-12 | Observabilidad de primera clase (Prometheus/Loki/Tempo/Grafana) | C-03+ |
| DD-13 | Privacidad por diseño (minimización, retención configurable, DSR nativos) | C-08, C-17, C-19 |
| DD-14 | Acuerdo de Nivel de Proctoring contractual | este change |
| DD-17 | Motor de visión abstraído (MediaPipe→ONNX Runtime Web) | C-11 |
| DD-18 | Liveness escalonado (híbrido propio MVP) | C-09 |
| DD-19 | Principio rector: simplicidad + instrumentación + complejidad solo por métrica | C-03, global |
| IN-04/SU-08 | Embedding = dato sensible por defecto | C-09, C-19 |

## Risks / Trade-offs

- **[El gate se eterniza esperando firmas legales]** → Mitigación: criterios de Done binarios y verificables; responsable y fecha objetivo por entregable en `tasks.md`; correr C-02 y C-03 en paralelo para no bloquear todo el equipo.
- **[Legal exige cambios de diseño tras el DPIA]** → Mitigación: es precisamente el objetivo del gate — absorber esos cambios ANTES de codificar; el costo de un cambio aquí es de documento, no de código.
- **[Reforma legal cambia el marco a mitad de proyecto (L-001)]** → Mitigación: diseñar contra el estándar más exigente (RGPD-like) y prever revisión legal anual; la clasificación sensible por defecto ya anticipa la reforma.
- **[Caso disciplinario llega a la justicia (L-002)]** → Mitigación: el Acuerdo + DPIA + cadena de custodia (DD-07) sostienen el peritaje; este change asienta la base documental.
- **[Brecha de expectativas (L-004)]** → Mitigación: el Acuerdo de Nivel de Proctoring con RACI y límites deliberados es la mitigación directa.
- **[Aprobar A4 sin congelar la jerarquía sobre el SAD]** → Mitigación: D2 — acta que declara explícitamente que A4 prevalece en el MVP y el SAD es evolución condicionada a C-03.
- **Trade-off aceptado**: el gate retrasa el inicio de código 4–8 semanas. Es deliberado y barato comparado con construir sobre una base legal inválida.

## Migration Plan

No aplica migración técnica (no hay sistema en producción). "Despliegue" = transición de estado organizacional:

1. Recopilar y aprobar los 19 ADRs (acta firmada).
2. En paralelo, el DPO produce el DPIA y la clasificación del embedding.
3. Recopilar firmas del Acuerdo de Nivel de Proctoring.
4. Decidir vía alternativa + población menor.
5. Iniciar inscripción AAIP.
6. **Criterio de salida del gate**: todos los entregables firmados/aprobados → Fase 0 desbloqueada para C-04+.

**Rollback**: no hay rollback de software. Si un entregable es rechazado (p. ej. legal no aprueba el DPIA), el gate permanece cerrado y se itera el documento; ningún change downstream inicia.

## Open Questions

Las que este change debe **cerrar** (no quedan abiertas al archivar):
- ¿Se firma el Acuerdo y se completa el DPIA antes de codificar? → debe resolverse SÍ (criterio de salida).
- ¿Embedding es dato sensible? → resuelto: sí, por defecto (D3).
- ¿Se ofrece vía alternativa sin biometría? → decisión explícita requerida (D5).
- ¿Hay población menor de 18? → determinación requerida.

Las que **quedan fuera** de este change (otros decisores/changes):
- Mensajería MVP definitiva Postgres vs RabbitMQ a nivel métrico → C-03 (PoC de carga), no aquí; aquí solo se congela la hipótesis A4.
- Designación/capacitación de revisores → C-02 (paralelo).
- Valores de umbrales, política de retención numérica concreta → Fase 1/2.
