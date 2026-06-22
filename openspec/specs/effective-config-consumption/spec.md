# effective-config-consumption Specification

## Purpose
TBD - created by archiving change c-68-configuracion-sistema-funcional. Update Purpose after archive.
## Requirements
### Requirement: Endpoint de configuración efectiva
El sistema SHALL exponer `GET /api/v1/config/effective` (accesible a cualquier usuario autenticado) que retorne el objeto autoritativo completo de configuración: `version`, pesos de scoring, umbrales de detección, `umbral_cola_revision`, `detectores_activos` y `consent_version_vigente`. La respuesta SHALL incluir la `version` como ETag para detección de staleness.

#### Scenario: La config efectiva retorna versión coherente
- **WHEN** un cliente autenticado llama a `GET /api/v1/config/effective`
- **THEN** la respuesta SHALL incluir todos los parámetros autoritativos y un campo `version` consistente con la configuración persistida

### Requirement: Test Detección y exámenes consumen la configuración efectiva
TEST DETECCIÓN (harness) y la pantalla de examen SHALL cargar la configuración efectiva al inicio y usar esos valores como baseline, en lugar de las constantes `DEFAULT_CONFIG` hardcodeadas.

#### Scenario: El examen usa los pesos de la config efectiva
- **WHEN** se inicia un examen tras una edición de configuración
- **THEN** el scoring del examen SHALL usar los pesos y umbrales de la configuración efectiva vigente, no las constantes hardcodeadas

#### Scenario: El harness carga la config efectiva como baseline
- **WHEN** se abre TEST DETECCIÓN
- **THEN** el harness SHALL cargar la configuración efectiva real como baseline de sus umbrales (sin perder su naturaleza air-gapped para la captura local)

### Requirement: Invalidación de caché al editar la configuración
El cliente SHALL invalidar su caché de configuración efectiva cuando la configuración cambie, generalizando el mecanismo existente `resetScoringWeightsCache()` a la configuración completa.

#### Scenario: Editar la config refresca el caché del cliente
- **WHEN** un `admin_sistema` guarda una edición de configuración
- **THEN** el caché de configuración efectiva del cliente SHALL invalidarse y la próxima lectura SHALL traer la versión nueva

