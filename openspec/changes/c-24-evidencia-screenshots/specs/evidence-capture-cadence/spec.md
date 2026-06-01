# Spec — evidence-capture-cadence

> Política de **cadencia** de captura de evidencia: disparador **event-driven** (evento de severidad alta/crítica) **+ heartbeat** periódico de baja frecuencia como línea base, **configurable por examen**. Decisión DD-24-02.

## ADDED Requirements

### Requirement: Captura event-driven ante evento de severidad alta o crítica
El cliente SHALL capturar un screenshot **en el instante** en que un detector emite un evento de severidad **alta o crítica** (RN-CC-01); los eventos de severidad media o baseline NO SHALL disparar captura por este mecanismo. Esta es la evidencia primaria del flag.

#### Scenario: Evento severo dispara screenshot
- **WHEN** el detector emite un evento de severidad alta o crítica (p. ej. múltiples rostros, posible cambio de identidad)
- **THEN** el cliente captura un **screenshot** asociado a ese evento, en el instante del evento

#### Scenario: Evento no severo no dispara captura event-driven
- **WHEN** el detector emite un evento de severidad media o baseline (p. ej. mirada desviada)
- **THEN** el mecanismo event-driven NO captura ningún screenshot de evidencia

### Requirement: Heartbeat periódico de baja frecuencia como línea base
El cliente SHALL capturar un screenshot periódico de **baja frecuencia** (heartbeat) independiente de los eventos, para proveer una **línea base** de la sesión que permita a la revisión humana contextualizar los frames de eventos.

#### Scenario: Heartbeat captura línea base periódica
- **WHEN** transcurre el intervalo de heartbeat configurado y el heartbeat está activado
- **THEN** el cliente captura un screenshot de línea base, siguiendo la misma cadena de custodia que cualquier evidencia

#### Scenario: Heartbeat desactivado no captura línea base
- **WHEN** el heartbeat está desactivado para el examen
- **THEN** el cliente NO captura screenshots periódicos de línea base, y solo opera el mecanismo event-driven

### Requirement: Cadencia configurable por examen con proporcionalidad
La frecuencia del heartbeat y su activación SHALL ser **parámetros de configuración por examen**, con un default conservador y un tope máximo; a mayor frecuencia, mayor dato retenido, por lo que la configuración SHALL respetar el principio de proporcionalidad (Ley 25.326, minimización de datos).

#### Scenario: Examen de alto riesgo sube la frecuencia dentro del tope
- **WHEN** un administrador configura un examen de alto riesgo con mayor frecuencia de heartbeat
- **THEN** el sistema aplica esa frecuencia siempre que no exceda el tope máximo permitido

#### Scenario: Default conservador cuando no se configura
- **WHEN** un examen no especifica configuración de heartbeat
- **THEN** el sistema aplica un default conservador de baja frecuencia
