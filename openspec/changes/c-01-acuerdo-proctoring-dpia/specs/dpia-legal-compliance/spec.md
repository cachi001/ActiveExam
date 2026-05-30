# Spec — dpia-legal-compliance

> Capacidad de **governance documental**. Cumplimiento Ley 25.326 / Decreto 1558/2001 / AAIP. Los "scenarios" son criterios de Done verificables sobre el DPIA y el paquete legal.

## ADDED Requirements

### Requirement: DPIA aprobado por el DPO antes de codificar dominio
El proyecto SHALL contar con una Evaluación de Impacto en Protección de Datos (DPIA) completa y **aprobada formalmente por el DPO / área legal** antes de escribir código de dominio (Fase 0).

#### Scenario: DPIA completo y aprobado
- **WHEN** el DPO finaliza la evaluación
- **THEN** existe un documento DPIA con aprobación firmada por el DPO, fechado, que cubre tratamiento biométrico, riesgos y medidas de mitigación

#### Scenario: Gate de bloqueo activo hasta la aprobación
- **WHEN** un change de dominio (C-04 en adelante) intenta iniciar implementación
- **THEN** el DPIA aprobado es precondición; sin él, el proyecto permanece en Fase 0

### Requirement: Base legal del tratamiento documentada
El DPIA SHALL documentar la base legal del tratamiento: **consentimiento informado** (libre, expreso, con acción afirmativa, registrado con timestamp y hash) como base principal de la captura biométrica, sin usar la relación académica para forzarlo.

#### Scenario: Consentimiento como base principal
- **WHEN** se revisa el DPIA
- **THEN** identifica el consentimiento informado como base legal principal de la biometría y exige una vía alternativa sin biometría para que el consentimiento sea genuinamente libre

### Requirement: Proporcionalidad y derechos del titular garantizados
El DPIA SHALL fundamentar la proporcionalidad del tratamiento (L2.5 + ausencia de video continuo, lección caso SRFP: legalidad, necesidad, proporcionalidad) y garantizar los derechos del titular: acceso, rectificación, supresión, portabilidad y **oposición a decisiones automatizadas**.

#### Scenario: Argumento de proporcionalidad presente
- **WHEN** se revisa el DPIA
- **THEN** justifica necesidad y proporcionalidad y referencia los límites de la jurisprudencia SRFP (finalidad acotada, control independiente, no reutilización)

#### Scenario: Derechos del titular cubiertos
- **WHEN** se revisa el DPIA
- **THEN** describe cómo se garantizan acceso, rectificación, supresión, portabilidad y oposición a decisiones automatizadas (esta última ya cubierta por revisión humana obligatoria)

### Requirement: Inscripción de bases ante la AAIP planificada
El paquete legal SHALL incluir la planificación o el inicio de la inscripción de las bases de datos ante el Registro Nacional de Bases de Datos de la AAIP, y confirmar la soberanía de datos (datos alojados en el país, self-hosted).

#### Scenario: Inscripción AAIP iniciada
- **WHEN** legal completa el paquete de cumplimiento
- **THEN** existe constancia de inicio o plan de inscripción de las bases ante la AAIP, con responsable y fecha objetivo

#### Scenario: Soberanía de datos confirmada
- **WHEN** se revisa el paquete legal
- **THEN** confirma que el tratamiento es self-hosted en infraestructura institucional dentro del país
