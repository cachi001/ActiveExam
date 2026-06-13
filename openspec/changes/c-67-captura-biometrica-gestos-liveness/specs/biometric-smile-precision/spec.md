# biometric-smile-precision Specification

## ADDED Requirements

### Requirement: La detección de sonrisa usa una métrica de landmarks más precisa

La detección del gesto de sonrisa SHALL usar una métrica de landmarks más discriminante que el solo ancho de boca, incorporando la **elevación de las comisuras** (landmarks 61 y 291) relativa a un punto de referencia estable de la boca/rostro, evaluada como cambio relativo respecto del baseline neutral del alumno.

La métrica SHALL seguir siendo **relativa al baseline** (no un umbral absoluto global), de modo que una cara en reposo natural NO confirme la sonrisa (sin reabrir el falso positivo de auto-OK en reposo). El baseline de sonrisa SHALL seguir validándose para rechazar baselines capturados con el alumno ya sonriendo.

#### Scenario: Sonrisa real confirma

- **WHEN** el alumno sonríe (las comisuras se elevan y/o el ancho de boca aumenta respecto del baseline)
- **THEN** la métrica de sonrisa supera el umbral relativo y el frame cumple el reto

#### Scenario: Cara neutral no confirma sonrisa

- **WHEN** el alumno mantiene una expresión neutral (reposo)
- **THEN** la métrica de sonrisa NO supera el umbral relativo y el frame no cumple el reto

#### Scenario: Boca abierta sin sonreír no confirma

- **WHEN** el alumno abre la boca sin elevar las comisuras (no es sonrisa)
- **THEN** la métrica compuesta no confirma el gesto de sonrisa

### Requirement: La confirmación de la sonrisa tiene menor latencia

El sistema SHALL permitir que el gesto de sonrisa confirme con menor latencia que la de los otros gestos (un umbral de hold propio o factor reducido para la sonrisa), de modo que responda más rápido una vez detectada, manteniendo el gate de neutralidad y el criterio de hold por tiempo.

#### Scenario: La sonrisa confirma más rápido que antes

- **WHEN** el alumno sostiene una sonrisa válida
- **THEN** el reto de sonrisa se confirma con menor latencia que el comportamiento previo, sin saltar el gate de neutralidad
