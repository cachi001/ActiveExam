# Spec — load-poc-harness

> Capacidad de **validación de carga**. Los "scenarios" son criterios de Done verificables sobre el harness de la PoC y su instrumentación, no comportamiento de software de producción. El harness es **descartable**.

## ADDED Requirements

### Requirement: Generadores de carga calibrados al pico contra el capacity model
El harness SHALL generar tráfico sintético calibrado contra el capacity model del `14`: ~2.100 conexiones de estudiante concurrentes, heartbeats firmados cada 5 s (~200 inserts/s), eventos normales (~1.000 inserts/s sostenido) y ráfaga multi-examen hasta **~5.000 inserts/s** en pico.

#### Scenario: Perfil de pico sostenido reproducible
- **WHEN** se ejecuta el perfil P2 (pico)
- **THEN** el harness sostiene ~2.100 concurrentes y ~5.000 inserts/s durante una ventana de medición de al menos 10 minutos, no un burst instantáneo

#### Scenario: Validación de la suposición de escalado lineal de inserts (SU-06)
- **WHEN** se ejecutan P1 (sostenido, ~1.000 conc. / ~1.000 inserts/s) y P2 (pico, ~2.100 conc. / ~5.000 inserts/s)
- **THEN** se registra si el escalado de inserts respecto del sostenido es ~lineal, confirmando o refutando la Suposición SU-06

### Requirement: Paneles de proctor sintéticos a la proporción real
El harness SHALL simular **N paneles de proctor activos** a la proporción operativa (≈ 1 proctor / 50–100 estudiantes ⇒ ~20–40 paneles concurrentes), cada uno suscripto a sus sesiones asignadas, midiendo la latencia evento→panel.

#### Scenario: N paneles suscriptos midiendo propagación
- **WHEN** se ejecuta P2 con 20–40 paneles sintéticos suscriptos a sus sesiones
- **THEN** cada panel registra el timestamp de recepción de cada evento para calcular la latencia de propagación evento→panel por percentil

### Requirement: Instrumentación completa montada antes de generar carga
El harness SHALL exponer instrumentación completa (Prometheus para percentiles y profundidad de cola/lag; Tempo para la traza distribuida evento→persist→fan-out→panel) **antes** de la primera corrida de carga, de modo que toda decisión se tome por métrica y no por opinión (DD-12, DD-19).

#### Scenario: Métricas disponibles antes de la primera corrida
- **WHEN** se inicia cualquier perfil de carga
- **THEN** Prometheus expone p50/p95/p99 por concern, inserts/s, profundidad de cola, lag de backplane y conexiones por instancia, y Tempo registra la traza completa del camino del evento

#### Scenario: Decisión soportada por métrica, no por inspección ad-hoc
- **WHEN** se evalúa cualquier criterio de aceptación de los demás concerns
- **THEN** el número que decide se lee de Prometheus/Tempo (percentil contra umbral), no de logs ad-hoc ni de impresiones manuales

### Requirement: Código de la PoC declarado descartable
El harness SHALL documentar explícitamente que su código es un **prototipo descartable** y que su entregable es la **decisión de arquitectura**, no código de producción; ningún componente del harness se promueve a `openspec/specs/` ni a producción.

#### Scenario: Naturaleza descartable declarada
- **WHEN** se revisa el entregable del change
- **THEN** consta que el código del harness no es de producción y que C-04…C-15 re-implementan el ganador con calidad de producción
