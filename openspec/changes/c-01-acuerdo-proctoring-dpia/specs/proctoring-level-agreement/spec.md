# Spec — proctoring-level-agreement

> Capacidad de **governance documental**. Los "scenarios" son criterios de Done verificables sobre documentos firmados, no comportamiento de software.

## ADDED Requirements

### Requirement: Acuerdo de Nivel de Proctoring L2.5 firmado
El proyecto SHALL contar con un Acuerdo de Nivel de Proctoring que fije el nivel **L2.5** (análisis en cliente + verificación biométrica + anti-tampering pasivo) como contrato vivo, firmado por el patrocinador, la dirección académica y el proveedor, antes de iniciar cualquier desarrollo de dominio (DD-01, DD-14).

#### Scenario: Acuerdo firmado por todas las partes
- **WHEN** el área legal y la dirección recopilan las firmas requeridas
- **THEN** existe un documento "Acuerdo de Nivel de Proctoring" con firma de patrocinador, dirección académica y proveedor, con fecha y versión registradas

#### Scenario: Nivel L2.5 declarado explícitamente
- **WHEN** se revisa el Acuerdo firmado
- **THEN** declara el nivel L2.5 y descarta explícitamente niveles superiores (L3 grabación completa, L4 sincrónico, L5 lockdown nativo) como fuera de alcance

### Requirement: Finalidad acotada y límites deliberados declarados
El Acuerdo SHALL declarar la finalidad acotada del tratamiento (verificar identidad y supervisar integridad del examen, nunca otros fines) y los límites deliberados del sistema: **sin video continuo**, **sin lockdown** y **sin sanción automática** (lección caso SRFP; proporcionalidad).

#### Scenario: Finalidad y no reutilización declaradas
- **WHEN** se revisa el Acuerdo
- **THEN** incluye una cláusula de finalidad acotada y prohibición explícita de reutilizar los datos para vigilancia, marketing o cesión a terceros

#### Scenario: Límites deliberados y revisión humana obligatoria
- **WHEN** se revisa el Acuerdo
- **THEN** establece que ninguna sanción es automática (toda decisión disciplinaria pasa por revisión humana) y que no hay video continuo ni lockdown nativo

### Requirement: RACI de responsabilidad delimitado
El Acuerdo SHALL delimitar la responsabilidad de cada parte (proveedor, institución, DPO, revisores) de modo que la brecha de expectativas (riesgo L-004) quede explícitamente gestionada.

#### Scenario: Responsabilidades asignadas
- **WHEN** surge una disputa sobre alcance o garantía probatoria
- **THEN** el Acuerdo permite identificar qué parte es responsable de cada concern, evitando la brecha de expectativas
