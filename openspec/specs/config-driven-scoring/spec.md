# config-driven-scoring Specification

## Purpose
TBD - created by archiving change c-68-configuracion-sistema-funcional. Update Purpose after archive.
## Requirements
### Requirement: El cálculo de score server-side usa la configuración persistida
El cálculo de score server-side (consolidación de finalización y scoring de proctoring) SHALL ponderar los eventos usando los pesos y umbrales **vivos** leídos desde la configuración persistida (`evento_score_config` + `configuracion_sistema`), NO mapas hardcodeados. El fallback hardcodeado SHALL usarse únicamente como red de seguridad de degradación graceful cuando la configuración no esté disponible, y SHALL registrar esa degradación (RN-GLB-03), nunca como fuente normal.

#### Scenario: Editar un peso cambia el score de una sesión nueva
- **WHEN** un `admin_sistema` cambia el `peso` de un tipo de evento y luego finaliza una sesión nueva que contiene ese tipo de evento
- **THEN** el score final SHALL reflejar el peso editado (no el valor por defecto hardcodeado)

#### Scenario: Fallback solo ante config ausente
- **WHEN** la configuración persistida no está disponible al calcular el score
- **THEN** el sistema SHALL usar los pesos por defecto como red de seguridad y SHALL registrar un evento/log de degradación

### Requirement: El score prioriza, nunca sanciona (L2.5)
El score calculado a partir de la configuración SHALL usarse exclusivamente para **priorizar** la cola de revisión humana; el sistema SHALL NO emitir ningún veredicto ni sanción automática a partir del score (RN-SC-01, RN-RV-07).

#### Scenario: Score alto no produce sanción automática
- **WHEN** una sesión alcanza un score por encima del umbral de cola
- **THEN** la sesión SHALL entrar a la cola de revisión humana y el sistema SHALL NO aplicar ninguna sanción automática

### Requirement: Reproducibilidad: snapshot de versión de config por sesión
La consolidación de una sesión SHALL registrar la `version` de configuración usada en el cálculo, de modo que un cambio posterior de configuración NO altere el score de sesiones ya finalizadas (la config nueva aplica a sesiones nuevas).

#### Scenario: Cambio posterior no altera score histórico
- **WHEN** se finaliza una sesión con la versión de config N y luego un `admin_sistema` edita la configuración (versión N+1)
- **THEN** el score de la sesión ya finalizada SHALL permanecer calculado con la versión N

