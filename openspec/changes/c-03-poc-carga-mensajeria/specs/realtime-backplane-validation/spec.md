# Spec — realtime-backplane-validation (Concern c) ⚠️ riesgo de tiempo real #1

> Capacidad de **validación de carga** del **Concern (c) — backplane de eventos**, el **riesgo de tiempo real #1**. Tiempo real (< 500 ms). Hipótesis default = Postgres `LISTEN/NOTIFY` (A4, DD-16); mayor probabilidad de promover Redis Pub/Sub. Este es el concern que la PoC ataca **de frente**.

## ADDED Requirements

### Requirement: Fan-out evento→panel bajo 500 ms p99 en sostenido al pico
El backplane SHALL propagar cada evento desde la ingesta hasta los N=20–40 paneles de proctor activos suscriptos en **p99 < 500 ms EN SOSTENIDO AL PICO** (P2: ~2.100 conc. / ~5.000 inserts/s), no en reposo ni en burst aislado. Esta es la métrica que decide `LISTEN/NOTIFY` vs Redis Pub/Sub (SLO de propagación del `14`).

#### Scenario: LISTEN/NOTIFY medido al pico con N paneles activos
- **WHEN** se ejecuta P2 con el backplane sobre Postgres `LISTEN/NOTIFY` y 20–40 paneles suscriptos en sostenido al pico
- **THEN** la latencia de propagación evento→panel se mide en Prometheus como p99 y se compara contra el umbral de 500 ms

#### Scenario: Redis Pub/Sub medido bajo idéntico tráfico
- **WHEN** se ejecuta el mismo perfil P2 con el backplane sobre Redis Pub/Sub
- **THEN** se registra el mismo p99 de propagación bajo idéntico tráfico para comparar apples-to-apples contra `LISTEN/NOTIFY`

### Requirement: Punto de quiebre del LISTEN/NOTIFY localizado
El backplane SHALL ser sometido a un barrido de carga creciente (P3) que **degrade `LISTEN/NOTIFY` hasta el punto de quiebre** donde el p99 de fan-out cruza 500 ms, registrando el throughput (eventos/s × N paneles) en ese punto y comparándolo con el pico requerido, para cuantificar el margen (headroom).

#### Scenario: Punto de quiebre registrado con su margen
- **WHEN** se ejecuta el barrido P3 incrementando eventos/s y N paneles por encima del pico
- **THEN** se registra el throughput exacto donde `LISTEN/NOTIFY` cruza p99=500 ms y si ese punto está por encima o por debajo del pico requerido (margen disponible)

### Requirement: Cero pérdida bajo reconexión y caída de instancia (exactly-once lógico)
El backplane SHALL garantizar **cero pérdida de eventos confirmados** con **exactly-once lógico** bajo reconexión de panel y caída de instancia durante el pico (P4 caos), para ambas opciones.

#### Scenario: Sin pérdida ni duplicados bajo caos al pico
- **WHEN** se inyecta caída de instancia/nodo y reconexión de paneles durante P2 (perfil P4 caos)
- **THEN** ningún evento confirmado se pierde y ninguno se entrega duplicado al panel (exactly-once lógico), verificado por conteo extremo a extremo

### Requirement: Veredicto explícito del backplane (sostiene ✓ / se promueve ✗)
El concern (c) SHALL registrar un **veredicto explícito**: `LISTEN/NOTIFY` sostiene el pico ✓ (conservar A4) **o** se promueve Redis Pub/Sub ✗, decidido por la métrica de fan-out al pico y el punto de quiebre, documentado como evolución condicionada y no como retrabajo (DD-19).

#### Scenario: Conservar LISTEN/NOTIFY si sostiene con margen
- **WHEN** `LISTEN/NOTIFY` mantiene p99 < 500 ms al pico y su punto de quiebre queda por encima del pico requerido con margen
- **THEN** el veredicto registra "LISTEN/NOTIFY sostiene el pico ✓ — conservar A4" con la cota de migración a Redis documentada para producción

#### Scenario: Promover Redis si no sostiene el fan-out al pico
- **WHEN** `LISTEN/NOTIFY` cruza p99 ≥ 500 ms al pico o su punto de quiebre cae por debajo del pico requerido
- **THEN** el veredicto registra "se promueve Redis Pub/Sub ✗" como evolución condicionada documentada en el ADR, consumida por C-10 y C-15
