# validacion-nota-examen Specification

## Purpose
TBD - created by archiving change c-76-panel-supervision-en-vivo. Update Purpose after archive.
## Requirements
### Requirement: Validación declarativa de `nota_aprobacion ≤ nota_maxima` en el schema

Los schemas Pydantic de configuración de examen que aceptan `nota_maxima` y `nota_aprobacion` (creación de examen y edición de configuración por examen) SHALL rechazar, a nivel del propio schema, cualquier cuerpo donde `nota_aprobacion > nota_maxima`, devolviendo `422 Unprocessable Entity`. Esta validación es **defensa en profundidad**: hoy la invariante se aplica de forma imperativa en los routers (`nota_aprobacion > nota_maxima → 422`) y en el frontend, pero NO en el schema; declararla en el schema evita que un endpoint nuevo omita el chequeo. Los schemas SHALL mantener `model_config = ConfigDict(extra='forbid')`.

En una edición parcial (PATCH) donde `nota_aprobacion` o `nota_maxima` puedan venir ausentes, la validación cruzada del schema SHALL aplicarse únicamente cuando ambos valores estén presentes en el cuerpo; el chequeo sobre los valores finales mergeados (schema ausente + valor persistido) queda cubierto por la validación de dominio existente (`validar_config_examen`), que NO se elimina.

#### Scenario: Rechazo en creación cuando aprobación supera el máximo
- **WHEN** se envía la creación de un examen con `nota_aprobacion` mayor que `nota_maxima` (por ejemplo `nota_aprobacion=80`, `nota_maxima=60`)
- **THEN** el schema rechaza el cuerpo con `422 Unprocessable Entity` antes de alcanzar la lógica de aplicación

#### Scenario: Aceptación cuando aprobación es menor o igual al máximo
- **WHEN** se envía `nota_aprobacion=60` y `nota_maxima=100`
- **THEN** el schema acepta el cuerpo y el flujo continúa normalmente

#### Scenario: PATCH parcial con un solo campo no dispara la validación cruzada del schema
- **WHEN** un PATCH de configuración envía solo `nota_maxima` (sin `nota_aprobacion`)
- **THEN** el schema NO rechaza el cuerpo por la validación cruzada, y la coherencia sobre los valores finales mergeados la garantiza `validar_config_examen`

#### Scenario: Campos no declarados siguen rechazados
- **WHEN** el cuerpo incluye un campo no declarado en el schema
- **THEN** el schema lo rechaza con `422` por `extra='forbid'`

