## MODIFIED Requirements

### Requirement: El perfil incluye contenedores de consentimiento y biometría con estado de completitud
El sistema SHALL mostrar las secciones de perfil con estado de completitud visual. El bloque de simulación de deriva de embedding ("Control de demostración") SHALL renderizarse únicamente cuando `DEV_TOOLS_ENABLED === true` y las condiciones biométricas existentes se cumplan (`biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida`). Cuando `DEV_TOOLS_ENABLED` es `false`, el bloque no aparece en el DOM.

El texto mostrado cuando `ENABLE_DNI_SCAN` es `false` SHALL decir "No disponible en esta versión" (o equivalente neutro sin "próximamente") e incluir el disclaimer de Ley 25.326 sobre tratamiento del dato como sensible.

#### Scenario: Sección de consentimiento muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión
- **THEN** la sección "Consentimiento informado" muestra estado `pendiente`

#### Scenario: Sección de biometría muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil por primera vez en la sesión
- **THEN** la sección "Verificación biométrica" muestra estado `pendiente`

#### Scenario: Perfil completo habilita el gate puedeRendir
- **WHEN** ambas secciones (consentimiento y biometría) están en estado `completado`
- **THEN** `api.puedeRendir()` retorna `{ puede: true }`

#### Scenario: Perfil incompleto mantiene el gate bloqueado
- **WHEN** al menos una sección (consentimiento o biometría) está en estado `pendiente`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: string }`

#### Scenario: Embedding drift simulation absent when flag off
- **WHEN** `DEV_TOOLS_ENABLED` es `false` y `biometriaOk` es `true`
- **THEN** el bloque "Control de demostración" (simular deriva embedding) no aparece en el DOM

#### Scenario: Embedding drift simulation present when flag on
- **WHEN** `DEV_TOOLS_ENABLED` es `true` y `biometriaOk` es `true` y biometría no está caducada
- **THEN** el bloque de simulación de deriva aparece en la sección biométrica del perfil

#### Scenario: DNI unavailable text is neutral
- **WHEN** `ENABLE_DNI_SCAN` es `false`
- **THEN** el texto no contiene "próximamente" y conserva la referencia a Ley 25.326
