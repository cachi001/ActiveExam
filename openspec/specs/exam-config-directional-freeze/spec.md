# exam-config-directional-freeze Specification

## Purpose
TBD - created by archiving change c-72-integridad-rendicion-serverside. Update Purpose after archive.
## Requirements
### Requirement: Campos de configuración congelados tras la primera rendición

Una vez que un examen tiene al menos un intento finalizado, el sistema SHALL rechazar con `409 config_congelada` todo cambio a los campos cuya modificación alteraría **retroactivamente** la nota o la equidad de quienes ya rindieron: `nota_maxima`, `nota_aprobacion`, `tiempo_limite_min`, `mezclar_preguntas`, `apertura` y la selección de preguntas. El rechazo SHALL identificar los campos congelados presentes en el cambio, y SHALL NOT persistir ninguno de los campos del PATCH (rechazo atómico).

#### Scenario: Cambiar la escala de nota tras la primera rendición

- **WHEN** un administrador intenta modificar `nota_maxima` en un examen con al menos un intento finalizado
- **THEN** el sistema responde `409 config_congelada` indicando el campo, y ningún campo del PATCH se persiste

#### Scenario: Cambiar el tiempo límite tras la primera rendición

- **WHEN** un administrador intenta modificar `tiempo_limite_min` en un examen con al menos un intento finalizado
- **THEN** el sistema responde `409 config_congelada` y no persiste el cambio

#### Scenario: Examen sin rendiciones admite cualquier cambio

- **WHEN** un administrador modifica cualquier campo de configuración de un examen sin intentos finalizados
- **THEN** el sistema persiste el cambio normalmente

#### Scenario: Rechazo atómico de un PATCH mixto

- **WHEN** un PATCH sobre un examen ya rendido incluye a la vez un campo congelado y uno libre
- **THEN** el sistema rechaza la operación completa con `409 config_congelada` y no persiste el campo libre

### Requirement: Campos direccionales — aflojar se permite, apretar no

Tras la primera rendición, el sistema SHALL permitir los cambios que **amplían** las condiciones del alumno y SHALL rechazar con `409 config_congelada` los que las **restringen**: `cierre` SHALL admitir únicamente valores posteriores al vigente (extender la ventana), e `intentos_permitidos` SHALL admitir únicamente valores mayores al vigente (otorgar más intentos). Restringir cualquiera de los dos perjudicaría retroactivamente a alumnos que aún no rindieron o que dependen de un intento ya habilitado.

#### Scenario: Extender la ventana ante una contingencia

- **WHEN** un administrador extiende `cierre` a una fecha posterior en un examen con al menos un intento finalizado
- **THEN** el sistema persiste el cambio y responde 200

#### Scenario: Acortar la ventana se rechaza

- **WHEN** un administrador intenta adelantar `cierre` a una fecha anterior a la vigente en un examen ya rendido
- **THEN** el sistema responde `409 config_congelada` y no persiste el cambio

#### Scenario: Otorgar un intento extra

- **WHEN** un administrador aumenta `intentos_permitidos` de 1 a 2 en un examen ya rendido
- **THEN** el sistema persiste el cambio y responde 200

#### Scenario: Quitar intentos se rechaza

- **WHEN** un administrador intenta reducir `intentos_permitidos` de 2 a 1 en un examen ya rendido
- **THEN** el sistema responde `409 config_congelada` y no persiste el cambio

### Requirement: Los controles de publicación permanecen editables

El sistema SHALL mantener editables tras la rendición los campos que solo gobiernan **qué ve el alumno después** y no alteran su nota ni las condiciones en que rindió: `mostrar_nota` y `revision_habilitada`. Liberar u ocultar resultados es un acto académico legítimo posterior a la rendición.

#### Scenario: Liberar la nota tras corregir

- **WHEN** un administrador activa `mostrar_nota` en un examen con intentos finalizados
- **THEN** el sistema persiste el cambio y responde 200

#### Scenario: Habilitar la revisión posterior

- **WHEN** un administrador activa `revision_habilitada` en un examen ya rendido
- **THEN** el sistema persiste el cambio y responde 200

### Requirement: La configuración expone su estado de bloqueo

La lectura de la configuración del examen SHALL exponer qué campos están congelados y cuáles admiten cambio direccional, de modo que la interfaz de administración pueda deshabilitar los controles correspondientes y explicar el motivo **antes** de que el administrador intente un cambio que será rechazado.

#### Scenario: La UI conoce el estado de bloqueo

- **WHEN** se consulta la configuración de un examen con al menos un intento finalizado
- **THEN** la respuesta indica qué campos están congelados y qué campos admiten únicamente ampliación

#### Scenario: Examen sin rendiciones no reporta bloqueo

- **WHEN** se consulta la configuración de un examen sin intentos finalizados
- **THEN** la respuesta indica que ningún campo está congelado

