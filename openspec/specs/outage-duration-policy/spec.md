# outage-duration-policy Specification

## Purpose
TBD - created by archiving change c-14-resiliencia-reconexion. Update Purpose after archive.
## Requirements
### Requirement: Corte menor a 5 minutos sin pérdida
Un corte de conectividad de hasta 5 minutos SHALL NOT generar pérdida: al reconectar, el replay del buffer reenvía todos los eventos del período sin pérdida ni duplicación (RN-HB-03).

#### Scenario: Corte corto recupera todos los eventos
- **WHEN** el WebSocket cae por menos de 5 minutos y luego reconecta
- **THEN** todos los eventos producidos durante el corte se reenvían y persisten, sin pérdida ni duplicados

### Requirement: Corte mayor a 5 minutos emite evento crítico al reconectar
Un corte de conectividad de más de 5 minutos (reconexión tras > 5 min sin heartbeats) SHALL generar un evento crítico al reconectar (RN-HB-04, RN-EV-04). Este evento es una señal para el panel y SHALL NOT derivar ninguna sanción automática (L2.5, RN-RV-07).

#### Scenario: Corte largo genera evento crítico, no sanción
- **WHEN** el cliente reconecta tras más de 5 minutos sin heartbeats
- **THEN** se emite un evento crítico de "corte de conectividad prolongado" como señal para el panel, sin aplicar ninguna sanción automática

