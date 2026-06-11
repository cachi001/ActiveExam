# Spec — evidence-capture-upload (delta C-24)

> Modifica la etapa 1 de la cadena de custodia (`evidence-capture-upload`, de c-12): el artefacto capturado ante evento severo pasa de **clip de 5–10 s** a **screenshot (frame único)**. El hash/firma de origen y el upload directo por URL firmada se mantienen, ahora aplicados a la imagen. Decisión DD-24-01.

## MODIFIED Requirements

### Requirement: Captura de clip ante evento de severidad alta o crítica
El cliente SHALL capturar un **screenshot (frame único)** cuando, y solo cuando, se produce un evento de severidad **alta o crítica** (RN-CC-01); los eventos de severidad media o baseline NO disparan captura de evidencia. El artefacto deja de ser un clip de video de 5–10 s y pasa a ser una captura de un único frame (proporcionalidad L2.5, minimización de datos), aceptando explícitamente la pérdida de re-inferencia temporal y de re-verificación de liveness/movimiento sobre la evidencia (DD-24-01).

#### Scenario: Evento severo dispara captura
- **WHEN** el detector emite un evento de severidad alta o crítica (p. ej. múltiples rostros, posible cambio de identidad)
- **THEN** el cliente captura un **screenshot (frame único)** asociado a ese evento

#### Scenario: Evento no severo no dispara captura
- **WHEN** el detector emite un evento de severidad media o baseline (p. ej. mirada desviada, heartbeat de eventos)
- **THEN** el cliente NO captura ningún screenshot de evidencia por este mecanismo

#### Scenario: No se captura video continuo ni clips
- **WHEN** transcurre la sesión de examen
- **THEN** el cliente NO graba video continuo ni clips de 5–10 s; la evidencia automática es siempre un frame único
