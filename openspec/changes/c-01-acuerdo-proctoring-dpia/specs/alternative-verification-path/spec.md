# Spec — alternative-verification-path

> Capacidad de **governance documental**. Decisión sobre vía alternativa sin biometría y población menor de 18. Los "scenarios" son criterios de Done verificables sobre la decisión firmada.

## ADDED Requirements

### Requirement: Decisión sobre la vía alternativa de verificación sin biometría
La dirección académica y legal SHALL decidir y documentar si se ofrece una **vía alternativa de verificación sin biometría** (p. ej. proctor humano en vivo) para quien no consienta la captura biométrica, condición necesaria para que el consentimiento sea genuinamente libre (Ley 25.326, base de consentimiento).

#### Scenario: Decisión documentada sobre la vía alternativa
- **WHEN** dirección académica y legal evalúan el requisito de consentimiento libre
- **THEN** existe una decisión firmada que define si se ofrece la vía alternativa sin biometría y, si se ofrece, su mecanismo (proctor humano en vivo u otro)

#### Scenario: Impacto en el flujo de consentimiento de C-08
- **WHEN** el change de consentimiento (C-08) se diseñe
- **THEN** parte de esta decisión: si hay vía alternativa, el flujo de consentimiento debe ofrecerla sin penalizar al estudiante

### Requirement: Determinación de población menor de 18 años
El proyecto SHALL determinar tempranamente si existe población **menor de 18 años** entre los evaluados y, de haberla, requerir un flujo de **consentimiento parental** y **retención diferenciada** validados por legal antes de Fase 1.

#### Scenario: Población menor identificada
- **WHEN** legal y dirección académica analizan la cohorte
- **THEN** existe una determinación documentada de si hay menores de 18 años

#### Scenario: Consecuencias para menores definidas
- **WHEN** la determinación confirma población menor de 18
- **THEN** la decisión exige consentimiento prestado por quien ejerce la responsabilidad parental y un flujo de retención diferenciado, como insumo para C-08 y C-19
