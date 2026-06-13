# exam-verification-result-screen Specification

## ADDED Requirements

### Requirement: El examen detiene el flujo y muestra el resultado de la verificación antes de continuar

Tras la verificación 1:1 del examen, el sistema SHALL detener el flujo y presentar al alumno una pantalla de resultado que indique de forma clara si la verificación **coincide** (es vos) o **no coincide**. El sistema NO SHALL avanzar automáticamente tras la verificación; el avance al examen SHALL requerir una confirmación explícita del alumno (gate de "continuar").

#### Scenario: Verificación exitosa requiere confirmación explícita

- **WHEN** la verificación 1:1 resulta en coincidencia
- **THEN** el sistema muestra un resultado claro de que se confirmó la identidad
- **THEN** el examen no avanza hasta que el alumno presiona un botón explícito de continuar

#### Scenario: Verificación fallida se muestra con opciones claras

- **WHEN** la verificación 1:1 no coincide
- **THEN** el sistema muestra un resultado claro de que no se pudo confirmar la identidad
- **THEN** el alumno ve opciones de reintentar o de escalar a una persona, sin avance automático

### Requirement: El resultado se explica en lenguaje claro, sin jerga visible

El copy principal de la pantalla de resultado SHALL estar redactado en español cotidiano, comprensible para una persona sin conocimiento técnico, y NO SHALL contener jerga visible como "embedding", "coseno", "umbral", "descriptor", "1:1" ni "distancia" en el texto principal. Los valores técnicos (distancia/umbral) SHALL ubicarse, si se muestran, en un detalle opcional o tooltip de glosario, nunca como texto principal.

El sistema NUNCA SHALL mostrar el vector de embedding (dato sensible, Ley 25.326). El mensaje SHALL preservar la garantía L2.5 de que ninguna decisión la toma una máquina y siempre la revisa una persona.

#### Scenario: El copy principal no contiene jerga

- **WHEN** se renderiza la pantalla de resultado (coincide o no coincide)
- **THEN** el texto principal no incluye "embedding", "coseno", "umbral", "descriptor", "1:1" ni "distancia"
- **THEN** el alumno entiende qué se verificó y cuál fue el resultado en lenguaje cotidiano

#### Scenario: Valores técnicos solo en detalle opcional

- **WHEN** el alumno abre el detalle técnico opcional
- **THEN** puede ver los valores numéricos (distancia/umbral) sin que aparezcan en el copy principal
- **THEN** el vector de embedding nunca se muestra

#### Scenario: La verificación informa, no sanciona

- **WHEN** el resultado es "no coincide"
- **THEN** el sistema no emite ningún veredicto disciplinario automático (L2.5)
- **THEN** el mensaje deja claro que una persona del equipo puede revisar el caso
