## MODIFIED Requirements

### Requirement: Terminología de evidencia de eventos en knowledge-base

La knowledge-base SHALL usar "captura" o "screenshot" (no "clip") para referirse a la evidencia de eventos automáticos del sistema de monitoreo, alineando con la decisión DD-24-01/03 (C-24) que establece que la evidencia es un frame estático, no un clip de video.

#### Scenario: Referencia a evidencia de eventos usa "captura" en lugar de "clip"

- **GIVEN** cualquier archivo de knowledge-base que describe la evidencia generada ante eventos severos o heartbeats
- **WHEN** un agente o desarrollador lee la descripción del artefacto de evidencia de eventos
- **THEN** el texto usa "captura" o "screenshot", no "clip" ni "video de 5-10 s"

### Requirement: Terminología de enrollment biométrico en knowledge-base

La knowledge-base SHALL describir la captura del enrollment biométrico como "foto de referencia (snapshot) + embedding". Los términos "video corto 3-5s" y "clip de verificación" NO SHALL usarse para el artefacto de enrollment, dado que el modelo confirmado es un snapshot único + embedding.

#### Scenario: Descripción de enrollment biométrico usa "foto (snapshot)" en lugar de "video/clip"

- **GIVEN** cualquier archivo de knowledge-base que describe el proceso de verificación biométrica de identidad en el enrollment
- **WHEN** un agente o desarrollador lee el paso de captura biométrica
- **THEN** el texto dice "foto (snapshot)" o "foto de referencia", no "video 3-5s" ni "clip de verificación"
- **AND** el artefacto persistido se describe como "foto + embedding", no como "clip + embedding"

### Requirement: Nota DPIA sobre tradeoff de liveness temporal en 10_preguntas_abiertas.md

El archivo `knowledge-base/10_preguntas_abiertas.md` SHALL contener una nota explícita registrando que el modelo foto+embedding no cubre liveness temporal server-side y que el DPIA (C-01) debe registrar y justificar ese tradeoff L2.5 para el nivel de supervisión declarado.

#### Scenario: Nota DPIA sobre liveness temporal está presente en preguntas abiertas

- **GIVEN** el archivo knowledge-base/10_preguntas_abiertas.md
- **WHEN** un responsable del DPIA o un agente revisa las preguntas de gobernanza
- **THEN** existe una sección de cambios con impacto de gobernanza que contiene una nota sobre C-51
- **AND** la nota explica que foto+embedding resuelve identidad pero no liveness temporal server-side
- **AND** la nota menciona que el DPIA (C-01) debe registrar y justificar el tradeoff L2.5
