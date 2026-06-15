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

### Requirement: La confirmación de la sonrisa tiene un hold propio ajustable

El sistema SHALL utilizar una constante de hold propia para el gesto de sonrisa (`SMILE_GESTURE_HOLD_MS`), independiente de `GESTURE_HOLD_MS`, de modo que el valor pueda ajustarse sin afectar los demás gestos. El valor actual es **500 ms** (igual a los demás gestos), priorizando anti-spoofing sobre latencia percibida — conforme a la decisión del dueño del producto (2026-06-13). El gate de neutralidad y el criterio de hold por tiempo acumulado se mantienen.

> **Decisión de producto (2026-06-13):** hold de sonrisa = 500 ms (NO reducción de latencia). Se eligió mantener el hold idéntico a los demás gestos para priorizar la defensa contra presentación de fotos/videos (ISO 30107-3). El valor es ajustable en `enrollmentChallengeDetector.ts` mediante `SMILE_GESTURE_HOLD_MS` sin necesidad de tocar la lógica del caller.

#### Scenario: La sonrisa confirma al sostener el hold propio

- **WHEN** el alumno sostiene una sonrisa válida durante `SMILE_GESTURE_HOLD_MS` (actualmente 500 ms)
- **THEN** el reto de sonrisa se confirma, sin saltar el gate de neutralidad

#### Scenario: El hold de sonrisa es configurable independientemente

- **WHEN** se requiere ajustar la latencia del gesto de sonrisa
- **THEN** basta modificar `SMILE_GESTURE_HOLD_MS` en `enrollmentChallengeDetector.ts`; los demás gestos no se ven afectados
