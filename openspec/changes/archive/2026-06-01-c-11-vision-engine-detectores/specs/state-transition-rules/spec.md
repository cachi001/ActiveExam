# Spec — state-transition-rules

> Reglas de transición de estado configurables por institución que convierten señales continuas en eventos discretos con severidad (RN-EV-01…RN-EV-06, US-006). La IA NO decide fraude: produce señales; las reglas producen eventos.

## ADDED Requirements

### Requirement: Señales continuas a eventos discretos con severidad
Las reglas de transición SHALL convertir las señales continuas de los detectores en eventos discretos con severidad usando umbrales temporales, fotogramas consecutivos y patrones sostenidos (RN-EV-01, RN-EV-02). La IA SHALL NOT emitir un veredicto de "fraude"; solo produce señales.

#### Scenario: Rostro ausente sostenido produce evento, no un fotograma aislado
- **WHEN** no se detecta rostro durante más de 3 s sostenidos
- **THEN** se emite un evento "rostro ausente" de severidad media

#### Scenario: Ausencia instantánea no produce evento (ruido)
- **WHEN** no se detecta rostro en un único fotograma aislado
- **THEN** no se emite ningún evento (filtrado por umbral temporal)

### Requirement: Mirada normal no es evento; patrón sostenido sí
Las reglas SHALL distinguir la mirada desviada normal (pensar, mirar al techo) de un patrón sostenido hacia un punto fijo fuera de pantalla; solo el patrón sostenido SHALL producir un evento (RN-EV-06).

#### Scenario: Mirar al techo para pensar no genera evento
- **WHEN** el iris se desvía brevemente de forma normal
- **THEN** no se emite ningún evento de mirada

#### Scenario: Consulta sostenida hacia un punto fijo genera evento
- **WHEN** el iris se mantiene fuera del marco hacia un punto fijo de forma sostenida
- **THEN** se emite un evento "mirada desviada sostenida" de severidad media

### Requirement: Múltiples rostros dispara alta severidad, evidencia y alerta < 500 ms
La detección de ≥2 rostros durante N fotogramas consecutivos SHALL emitir un evento de severidad **alta**, disparar la captura de evidencia (vía C-12) y propagar la alerta al panel en **< 500 ms** (vía el fan-out de C-10) (RN-EV-04).

#### Scenario: Dos rostros sostenidos disparan evidencia y alerta rápida
- **WHEN** se detectan ≥2 rostros durante N fotogramas consecutivos
- **THEN** se emite un evento de severidad alta que dispara captura de evidencia y alerta al panel en menos de 500 ms

### Requirement: Reglas configurables por institución
Las reglas de transición (umbrales temporales, fotogramas consecutivos, patrones) SHALL ser configurables por la institución (RN-EV-03).

#### Scenario: Cambiar el umbral temporal de una regla
- **WHEN** la institución ajusta el umbral de "rostro ausente" de 3 s a otro valor
- **THEN** las reglas evalúan con el nuevo umbral sin cambios de código

### Requirement: Las reglas no aplican sanciones
Las reglas SHALL limitarse a producir eventos con severidad; ninguna sanción ni decisión disciplinaria SHALL derivarse automáticamente de una transición (L2.5, RN-EV-01, RN-RV-07).

#### Scenario: Evento crítico no produce sanción automática
- **WHEN** una regla emite un evento de severidad crítica
- **THEN** el sistema emite la señal sin aplicar ninguna sanción automática
