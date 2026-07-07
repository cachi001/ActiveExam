# student-exam-rendering Specification

## Purpose
TBD - created by archiving change c-69-examen-plataforma-moodle-lockdown. Update Purpose after archive.
## Requirements
### Requirement: La rendición muestra las preguntas reales del examen
La pantalla de examen del alumno SHALL renderizar las preguntas y opciones obtenidas de la API de rendición (`exam-taking-api`), reemplazando la pregunta hardcodeada actual. El alumno SHALL poder seleccionar una opción por cada pregunta.

#### Scenario: El alumno ve y responde las preguntas reales
- **WHEN** el alumno entra a rendir un examen con preguntas cargadas
- **THEN** la pantalla muestra las preguntas y opciones reales servidas por la API, y el alumno puede seleccionar una opción por pregunta

#### Scenario: No queda contenido hardcodeado
- **WHEN** se renderiza la pantalla de examen
- **THEN** el enunciado y las opciones provienen de la API, no de una constante hardcodeada en el componente

### Requirement: No se notifica al alumno cada evento de proctoring por toast
La pantalla de examen del alumno SHALL NOT mostrar un toast (notificación emergente) por cada evento de proctoring detectado. La detección de eventos, el cálculo de score y la persistencia server-side SHALL permanecer sin cambios; sólo se elimina el feedback por evento visible al alumno.

#### Scenario: Un evento de proctoring no dispara toast al alumno
- **WHEN** durante el examen se detecta un evento de proctoring (p. ej. rostro ausente)
- **THEN** no aparece ningún toast informando al alumno del evento ni de los puntos sumados

#### Scenario: La detección y el score siguen registrándose
- **WHEN** se detecta un evento de proctoring durante el examen
- **THEN** el evento se sigue scoreando y persistiendo server-side exactamente igual que antes, pese a no mostrarse toast al alumno

