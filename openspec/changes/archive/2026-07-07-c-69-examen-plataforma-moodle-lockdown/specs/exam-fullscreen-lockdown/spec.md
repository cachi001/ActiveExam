# Spec — exam-fullscreen-lockdown

> Enforcement de pantalla completa durante la rendición. Consume el `FullscreenDetector`/`FocusDetector` existentes SIN modificar su contrato (la señal hacia el score se conserva). Límite honesto (DD-21): el navegador detecta y reacciona, NO previene el minimize del SO.

## ADDED Requirements

### Requirement: Forzar pantalla completa al iniciar el examen
Al iniciar la rendición, el sistema SHALL solicitar el modo de pantalla completa del navegador (Fullscreen API) mediante un gesto del usuario (p. ej. el click de inicio del examen). El enforcement SHALL ser una capa nueva que NO modifica el contrato de los detectores de contexto existentes: estos SHALL seguir produciendo su señal hacia el score como hasta ahora.

#### Scenario: El examen entra en pantalla completa al iniciar
- **WHEN** el alumno inicia la rendición del examen con un gesto del usuario
- **THEN** el documento del examen entra en modo de pantalla completa

#### Scenario: La detección y el score existentes no cambian
- **WHEN** ocurre una salida de pantalla completa durante el examen
- **THEN** la señal de fullscreen hacia el pipeline de detección y el score se siguen produciendo igual que antes del enforcement (retrocompat)

### Requirement: Overlay de bloqueo ante salida de pantalla completa, blur o pestaña oculta
Cuando el examen sale de pantalla completa, la ventana pierde el foco (blur) o la pestaña deja de estar visible (visibilitychange = hidden), el sistema SHALL montar un overlay de bloqueo que tapa el contenido del examen e impide interactuar con las preguntas, y SHALL ofrecer una acción explícita para volver a pantalla completa. El overlay SHALL desaparecer únicamente cuando el examen vuelve a estar en pantalla completa y la pestaña visible.

#### Scenario: Salir de pantalla completa bloquea el examen
- **WHEN** el alumno sale del modo de pantalla completa durante el examen
- **THEN** aparece un overlay de bloqueo que tapa las preguntas y ofrece volver a pantalla completa, y el alumno no puede responder mientras esté bloqueado

#### Scenario: Cambio de pestaña o pérdida de foco bloquea el examen
- **WHEN** la pestaña del examen deja de estar visible o la ventana pierde el foco
- **THEN** el overlay de bloqueo se muestra hasta que el alumno regresa al examen en pantalla completa y la pestaña vuelve a estar visible

#### Scenario: Volver a pantalla completa re-habilita el examen
- **WHEN** el alumno usa la acción de volver a pantalla completa y la pestaña vuelve a estar visible
- **THEN** el overlay desaparece y el alumno puede continuar respondiendo

### Requirement: El bloqueo no sanciona ni expulsa (L2.5)
El enforcement de lockdown SHALL bloquear y re-forzar la pantalla completa, pero NUNCA SHALL sancionar automáticamente, anular la sesión ni expulsar al alumno del examen. El evento sigue registrándose como señal para el score (que prioriza, no emite veredicto).

#### Scenario: El lockdown bloquea pero no anula
- **WHEN** el alumno sale repetidamente de pantalla completa
- **THEN** el sistema lo bloquea y re-fuerza cada vez, registra las señales para el score, pero no anula ni cierra automáticamente la sesión

### Requirement: Límite honesto del anti-minimizar documentado (DD-21)
El sistema SHALL documentar que, por ser una web app (no lockdown nativo L5), el navegador no puede impedir el minimize del sistema operativo ni ver fuera de su sandbox: el lockdown DETECTA y REACCIONA (bloquea + re-fuerza), no PREVIENE a nivel SO. Cuando el navegador no soporta la Fullscreen API, el examen SHALL degradar sin romperse y el límite SHALL quedar comunicado.

#### Scenario: Navegador sin soporte de Fullscreen API
- **WHEN** el navegador del alumno no soporta la Fullscreen API
- **THEN** el examen sigue funcionando (no se rompe) y el límite del lockdown queda documentado/comunicado, sin prometer una garantía a nivel SO
