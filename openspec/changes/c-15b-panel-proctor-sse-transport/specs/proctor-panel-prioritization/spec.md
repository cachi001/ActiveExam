# Spec — proctor-panel-prioritization

> Presentación de sesiones priorizadas por score de riesgo, leídas de continuous aggregates (CQRS-lite), con alertas críticas propagadas en p99 < 500 ms (US-011, RN-EV-04, `14`).

## ADDED Requirements

### Requirement: Sesiones priorizadas por score de riesgo
El panel SHALL presentar las sesiones **ordenadas por score de riesgo** (mayor primero), leyendo de **continuous aggregates** materializados de TimescaleDB (CQRS-lite), no recorriendo la hypertable cruda.

#### Scenario: Sesiones de mayor riesgo primero
- **WHEN** el proctor abre el panel con varias sesiones activas
- **THEN** las sesiones se presentan ordenadas por score de riesgo descendente, leídas del continuous aggregate

### Requirement: Alertas críticas propagadas en p99 < 500 ms
La propagación de una **alerta crítica** (p. ej. múltiples rostros, posible cambio de identidad) desde el evento hasta el panel SHALL cumplir **p99 < 500 ms**, medido en Prometheus en sostenido (SLO `14`, RN-EV-04).

#### Scenario: Alerta crítica llega a tiempo
- **WHEN** se genera un evento crítico en una sesión que el proctor está supervisando
- **THEN** la alerta aparece en el panel del proctor con una latencia de propagación p99 < 500 ms

### Requirement: Refresco de grilla tolera el lag del agregado
El refresco de la **grilla de sesiones** SHALL leerse de los continuous aggregates y NO está sujeto al SLO de 500 ms; las alertas accionables viajan por el push de baja latencia, separadas del refresco agregado.

#### Scenario: Grilla y alerta usan caminos distintos
- **WHEN** llega un evento crítico mientras la grilla se refresca desde el agregado
- **THEN** la alerta crítica se propaga por el push de baja latencia (< 500 ms) independientemente del ciclo de refresco de la grilla
