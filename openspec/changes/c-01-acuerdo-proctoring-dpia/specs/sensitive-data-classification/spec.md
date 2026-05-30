# Spec — sensitive-data-classification

> Capacidad de **governance documental**. Resuelve IN-04 a favor de SU-08. Los "scenarios" son criterios de Done verificables sobre la clasificación firmada por el DPO.

## ADDED Requirements

### Requirement: Embedding facial clasificado como dato sensible por defecto
El DPO SHALL clasificar formalmente el embedding facial como **dato sensible por defecto** ("responsabilidad reforzada"), aun cuando la Resolución AAIP 4/2019 podría no exigirlo siempre, resolviendo la inconsistencia IN-04 a favor del supuesto SU-08.

#### Scenario: Clasificación firmada por el DPO
- **WHEN** el DPO completa el análisis de IN-04
- **THEN** existe un documento firmado que clasifica el embedding como dato sensible por defecto, justificando que el costo de sobre-proteger es bajo y el de sub-proteger es alto

#### Scenario: Coherencia con la Resolución AAIP 4/2019
- **WHEN** se revisa la clasificación
- **THEN** reconoce el criterio de la Resolución AAIP 4/2019 (biométrico sensible solo si revela información potencialmente discriminatoria) y opta por el estándar más exigente (responsabilidad reforzada)

### Requirement: Consecuencias de responsabilidad reforzada definidas
La clasificación SHALL definir las consecuencias técnicas que heredarán los changes downstream: cifrado at-rest del embedding, minimización de datos, finalidad acotada y prohibición de reutilización.

#### Scenario: Requisitos derivados documentados
- **WHEN** un change de biometría (C-09) o de retención (C-19) consume esta clasificación
- **THEN** hereda las obligaciones de cifrado at-rest, minimización y no reutilización derivadas de la clasificación sensible
