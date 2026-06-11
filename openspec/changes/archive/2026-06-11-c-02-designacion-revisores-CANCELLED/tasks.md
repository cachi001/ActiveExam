# Tasks — C-02 `designacion-revisores`

> **Naturaleza**: gate organizacional **no-código**. Las "tasks" son **entregables de gestión / RRHH / capacitación**, no implementación de software. Cada una tiene un criterio de Done **verificable** (documento, lista nominal, registro de capacitación, firma). El responsable principal es la **dirección académica**, con coordinación operativa, RRHH y on-call/TI. Corre **en paralelo a C-01**.

## 1. Modelo de dimensionamiento humano

- [ ] 1.1 Confirmar el volumen objetivo (1.000 sostenido / ~2.100 pico, SU-06) y la tasa de flagging de partida (5–15%, SU-03) como entradas del modelo.
  - **Done**: documento con las entradas `V` y `f` citando SU-06 y SU-03.
- [ ] 1.2 Estimar `t_rev` (tiempo medio de revisión por sesión), `h` (horas productivas/revisor/día) y `SLA_rev` (plazo objetivo de resolución) con dirección académica y RRHH.
  - **Done**: las tres variables documentadas con su justificación y marcadas como supuestos a re-validar.
- [ ] 1.3 Calcular la plantilla base al sostenido (1.000 / 5%) y el refuerzo/doble cobertura al pico (~2.100 / 15%), con margen por ausencias/rotación.
  - **Done**: número de revisores y coordinadores derivado de la fórmula, con base y refuerzo diferenciados.
- [ ] 1.4 Desagregar el dimensionamiento por jurisdicción (RBAC contextual).
  - **Done**: tabla de cobertura por jurisdicción; ninguna jurisdicción en cero.
- [ ] 1.5 Registrar el compromiso de re-validar el modelo (al cierre del piloto y trimestral el primer año).
  - **Done**: cláusula de re-validación incluida en el documento del modelo.

## 2. Designación nominal del equipo

- [ ] 2.1 Designar nominalmente a los revisores académicos por jurisdicción, satisfaciendo el dimensionamiento de la sección 1.
  - **Done**: lista nominal de revisores con jurisdicción asignada; cada jurisdicción con titular.
- [ ] 2.2 Designar la coordinación operativa (gestión de cola/backlog, escalado a TI).
  - **Done**: al menos un coordinador nominado con responsabilidad declarada.
- [ ] 2.3 Designar suplentes y definir el esquema de doble cobertura para picos.
  - **Done**: suplentes nominados y esquema de doble cobertura documentado.
- [ ] 2.4 Documentar el RACI de la decisión (revisor → coordinador → dirección académica) dejando explícito que la decisión disciplinaria final es siempre humana (DD-01).
  - **Done**: tabla RACI firmada; cláusula de "sin sanción automática" presente.

## 3. Plan de capacitación por rol

- [ ] 3.1 Definir la currícula del **revisor académico**: tres decisiones terminales, lectura del contexto completo (timeline, clips firmados, re-inferencia, observaciones), gestión de falsos positivos.
  - **Done**: currícula del revisor con objetivos de aprendizaje y caso práctico de evaluación.
- [ ] 3.2 Definir la currícula del **coordinador operativo**: gestión de cola/backlog, umbrales, escalado, lectura del capacity model.
  - **Done**: currícula del coordinador documentada.
- [ ] 3.3 Definir la currícula del **proctor en vivo**: panel por riesgo, mensajería, observaciones, cierre forzado, derivación a revisión.
  - **Done**: currícula del proctor documentada.
- [ ] 3.4 Definir la currícula de **on-call/TI**: runbooks, simulacros, doble cobertura en picos (vínculo O-001).
  - **Done**: currícula de on-call con al menos un simulacro previsto.
- [ ] 3.5 Definir el módulo **transversal**: privacidad/Ley 25.326, audit log, MFA, acceso con propósito declarado, límites del sistema, comunicación a estudiantes.
  - **Done**: módulo transversal documentado.
- [ ] 3.6 Ejecutar la capacitación y registrar la finalización con evaluación verificable por persona.
  - **Done**: registro de capacitación completada (caso práctico aprobado, no solo asistencia) para cada designado.

## 4. Mecanismo de monitoreo de backlog

- [ ] 4.1 Definir la métrica de backlog (tamaño de cola + antigüedad de la sesión más vieja sin resolver, por jurisdicción).
  - **Done**: métrica documentada con su segmentación.
- [ ] 4.2 Definir umbrales (verde/ámbar/rojo) contra el `SLA_rev` y la regla de escalado (quién escala a quién en rojo).
  - **Done**: umbrales y regla de escalado documentados.
- [ ] 4.3 Asignar responsable (coordinador) y aprobador (dirección académica en estado rojo).
  - **Done**: responsabilidades asignadas en el documento.
- [ ] 4.4 Documentar el plan de respuesta escalonado ante backlog crítico (suplentes/doble cobertura → re-priorización por score → ajuste del umbral de flagging → re-dimensionamiento → escalado al patrocinador).
  - **Done**: plan de respuesta con acciones y responsables.
- [ ] 4.5 Fijar la cadencia de re-validación del capacity model (cierre del piloto + trimestral el primer año).
  - **Done**: cadencia registrada.
- [ ] 4.6 Coordinar con el roadmap que la instrumentación técnica de la métrica se materialice en C-16/C-13 (hand-off, no implementación aquí).
  - **Done**: nota de hand-off a C-16/C-13 registrada en el mecanismo.

## 5. Confirmación de capacidad sostenida (cierre del gate)

- [ ] 5.1 Consolidar los entregables de las secciones 1–4 en un paquete de evidencia trazable.
  - **Done**: paquete que referencia modelo, designación, capacitación y monitoreo.
- [ ] 5.2 Obtener la **firma de la dirección académica** confirmando capacidad sostenida (no solo de piloto) al volumen objetivo.
  - **Done**: documento firmado con fecha y versión, declarando capacidad continua.
- [ ] 5.3 Comunicar al patrocinador y registrar el cierre del gate C-02 (junto con C-01) como precondición de Fase 0.
  - **Done**: cierre comunicado; checkbox de C-02 listo para marcar `[x]` en CHANGES.md.

## Definición de Done del change

- [ ] D.1 Modelo de dimensionamiento documentado y por jurisdicción (sección 1).
- [ ] D.2 Equipo de revisión y coordinación designado nominalmente con suplentes (sección 2).
- [ ] D.3 Capacitación por rol ejecutada y verificada (sección 3).
- [ ] D.4 Mecanismo de monitoreo de backlog definido con plan de respuesta y cadencia (sección 4).
- [ ] D.5 Confirmación firmada de capacidad sostenida por dirección académica (sección 5).
- [ ] D.6 Gate co-cerrado con C-01: Fase 0 puede cerrarse y desbloquear el desarrollo (GATE 1).
