# Spec — state-transition-rules (delta C-53)

> Suma una transición sostenida que convierte la señal de objeto prohibido en el evento discreto `objeto_prohibido_detectado`. Como toda regla, produce EVENTO (no sanción): el peso prioriza para revisión humana (L2.5).

## ADDED Requirements

### Requirement: Transición de objeto prohibido sostenido
Las reglas de transición SHALL emitir el evento `objeto_prohibido_detectado` cuando un objeto cuya etiqueta pertenece a la lista configurable de objetos prohibidos (`prohibited_object_labels`) se detecta con confianza por encima de `object_confidence_threshold` durante al menos `object_detection_frames` fotogramas consecutivos. La señal de objetos (`objects`) en el frame SHALL ser opcional: si está ausente (`undefined`), la regla NO SHALL emitir evento (retrocompatible). La regla NO SHALL emitir de nuevo mientras el objeto persiste; SHALL resetear cuando el objeto desaparece. La regla NUNCA SHALL derivar una sanción automática.

#### Scenario: objeto prohibido sostenido emite evento
- **WHEN** un objeto de la lista prohibida se detecta con confianza ≥ umbral durante `object_detection_frames` fotogramas consecutivos
- **THEN** se emite un evento `objeto_prohibido_detectado` de severidad `alta` con `trigger_evidence: true` y payload `{ etiqueta, confianza, frames_consecutivos }`

#### Scenario: objeto instantáneo no emite (filtra ruido)
- **WHEN** un objeto prohibido aparece en menos fotogramas consecutivos que `object_detection_frames`
- **THEN** no se emite ningún evento

#### Scenario: objeto no prohibido no emite
- **WHEN** se detecta un objeto cuya etiqueta NO está en `prohibited_object_labels`
- **THEN** no se emite ningún evento de objeto prohibido

#### Scenario: de-dup mientras el objeto persiste
- **WHEN** ya se emitió el evento y el mismo objeto sigue presente en frames siguientes
- **THEN** no se re-emite el evento; al desaparecer el objeto el estado se resetea para una próxima detección

#### Scenario: señal de objetos ausente es retrocompatible
- **WHEN** el frame de señales no incluye el campo `objects` (`undefined`)
- **THEN** la regla de objeto prohibido no se evalúa y el comportamiento de las demás reglas no cambia
