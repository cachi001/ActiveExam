# biometric-recapture-rate-limit Specification

## Purpose
TBD - created by archiving change c-65-fixes-captura-liveness-biometrica. Update Purpose after archive.
## Requirements
### Requirement: La re-captura de la referencia se permite con un límite suave

El sistema SHALL permitir que el alumno re-capture/renueve su referencia biométrica desde el perfil (incluido el caso "Rehacer captura" con referencia vigente), pero SHALL aplicar un límite suave: un cooldown y/o un contador máximo de re-capturas en una ventana de tiempo configurable. Al alcanzar el límite, el sistema SHALL impedir nuevas re-capturas hasta que pase el cooldown, comunicándolo al alumno, sin sancionar.

El límite suave SHALL existir para evitar el "fishing" de un liveness aprobado por reintentos repetidos.

#### Scenario: Re-captura dentro del límite
- **WHEN** el alumno re-captura su referencia y no superó el límite
- **THEN** el flujo de captura procede normalmente

#### Scenario: Límite alcanzado
- **WHEN** el alumno supera el contador máximo de re-capturas dentro de la ventana
- **THEN** el sistema bloquea nuevas re-capturas hasta el fin del cooldown y lo informa, sin sanción

### Requirement: Cada re-captura/renovación queda registrada en el audit log y conserva la referencia anterior

El sistema SHALL registrar en el audit log cada re-captura/renovación de referencia: quién (usuario), cuándo (timestamp), y el origen/contexto de la solicitud. La referencia anterior SHALL conservarse versionada (no se sobre-escribe destructivamente), para soportar la cadena de custodia y de apelación.

La renovación SHALL pasar por la misma cadena de custodia que el enrollment original (liveness cliente → re-inferencia + firma server-side); NO SHALL ser un overwrite silencioso del lado del cliente. La renovación NO SHALL auto-sancionar ni invalidar una rendición en curso (L2.5).

#### Scenario: Renovación auditada
- **WHEN** el alumno renueva su referencia
- **THEN** el audit log registra usuario, timestamp y origen de la renovación
- **THEN** la referencia anterior queda conservada como versión previa

#### Scenario: Renovación no afecta rendición en curso
- **WHEN** se dispara una renovación anticipada por deriva del embedding durante una rendición
- **THEN** la rendición en curso no se invalida ni se sanciona automáticamente (decisión humana)

