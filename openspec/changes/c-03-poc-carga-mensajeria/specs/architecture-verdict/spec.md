# Spec — architecture-verdict

> Capacidad de **gobernanza de la decisión de arquitectura**. Los "scenarios" son criterios de Done sobre el **entregable real del change**: el veredicto por concern documentado por métrica. Este es el producto del change; no es código.

## ADDED Requirements

### Requirement: Veredicto registrado por cada uno de los 3 concerns
El change SHALL registrar un veredicto independiente por cada concern — (a) cola de trabajos, (b) transporte del panel, (c) backplane de eventos — cada uno justificado por su métrica decisora medida al pico contra el umbral del `14`, y cada uno puede tener resultado distinto.

#### Scenario: Tres veredictos independientes con su métrica
- **WHEN** se cierra el change al archivar
- **THEN** existe un veredicto documentado para cada concern (a, b, c), cada uno citando la métrica medida (Prometheus/Tempo), el umbral aplicado y la decisión (conservar A4 / promover SAD)

### Requirement: Default A4 conservado por omisión; SAD solo por métrica
El veredicto SHALL conservar la opción A4 (la simple) por omisión y promover una pieza del SAD **solo si** la métrica del concern lo exige, respetando el principio rector DD-19 (complejidad solo cuando una métrica la demuestre necesaria).

#### Scenario: Promoción justificada por métrica, no por opinión
- **WHEN** un veredicto promueve una pieza del SAD (RabbitMQ, WebSocket+sticky o Redis Pub/Sub)
- **THEN** la promoción cita el número medido que cruzó el umbral, y no se promueve ninguna pieza por la que la métrica no lo exija

### Requirement: Decisión documentada como evolución, no como retrabajo
El veredicto SHALL documentar toda promoción como **evolución condicionada en el ADR** (la hipótesis A4 fue la apuesta inicial congelada en C-01; la métrica la confirma o la evoluciona), sin tratarla como contradicción ni retrabajo, y dejar el resultado consumible por los changes downstream (C-04, C-10, C-12, C-15).

#### Scenario: Veredicto consumible downstream
- **WHEN** C-04/C-10/C-12/C-15 necesitan saber qué infraestructura levantar
- **THEN** el veredicto por concern indica sin ambigüedad qué cola, qué transporte de panel y qué backplane se implementan en producción

#### Scenario: Veredicto del backplane explícito
- **WHEN** se revisa el veredicto del concern (c)
- **THEN** declara explícitamente si `LISTEN/NOTIFY` sostiene el pico ✓ o si se promueve Redis Pub/Sub ✗, con el punto de quiebre registrado
