# exam-consent-lightweight Specification

## Purpose
TBD - created by archiving change c-58-pulido-ux-flujo-examen-login. Update Purpose after archive.
## Requirements
### Requirement: Examen activo seteado antes del consentimiento

Al iniciar el flujo de rendición desde "Rendir", el sistema SHALL fijar el examen activo en el estado de sesión antes de llegar al paso de consentimiento del examen, de modo que el botón de consentimiento pueda avanzar. El consentimiento del examen SHALL NOT quedar bloqueado por un examen activo nulo en el flujo normal del alumno.

#### Scenario: Iniciar rendición desde Mis Exámenes

- **WHEN** el alumno pulsa "Rendir" en una inscripción habilitada que pasó el gate
- **THEN** el sistema resuelve el examen de la inscripción y lo fija como examen activo en el estado de sesión
- **AND** al llegar al paso de consentimiento del examen, el examen activo está disponible

#### Scenario: Confirmar el consentimiento del examen

- **WHEN** el alumno marca la casilla de consentimiento del examen y pulsa el botón de confirmación
- **THEN** el sistema registra el acuse por-rendición (`recordConsent(examen.id)`) y navega a la verificación biométrica
- **AND** el botón nunca queda inerte por un examen activo nulo en el flujo normal

#### Scenario: Examen no resoluble en el catálogo

- **WHEN** el examen de la inscripción no se encuentra en el catálogo al iniciar la rendición
- **THEN** el sistema construye un examen mínimo a partir de la inscripción y lo fija como examen activo
- **AND** el flujo de consentimiento puede continuar sin romperse

### Requirement: Consentimiento del examen liviano de un click

Cuando el alumno ya consintió el tratamiento de datos en su perfil con la versión vigente del texto, el paso de consentimiento del examen SHALL presentarse como una confirmación corta de un click que referencia el acuse de perfil existente, en lugar de re-mostrar el texto completo. El acuse por-rendición (`recordConsent`) SHALL seguir registrándose siempre, preservando la cadena de custodia. La casilla de confirmación MUST NOT venir pre-marcada (acción afirmativa, RN-CO-02).

#### Scenario: Perfil ya consentido con versión vigente

- **WHEN** el alumno entra al paso de consentimiento del examen y el acuse de perfil existe con la versión vigente del texto (o vía alternativa)
- **THEN** se muestra una confirmación corta indicando la fecha del acuse de perfil y una casilla afirmativa no pre-marcada para aceptar la supervisión de esta evaluación
- **AND** al confirmar, se registra el acuse por-rendición y se avanza a la biometría

#### Scenario: Perfil no consentido o versión desactualizada

- **WHEN** el alumno no consintió el tratamiento en el perfil, o el acuse de perfil corresponde a una versión distinta de la vigente
- **THEN** se muestra el consentimiento completo (bloques informativos + texto largo) como en el flujo previo
- **AND** al aceptar, se registra el acuse por-rendición igual que antes

#### Scenario: Acuse por-rendición preservado

- **WHEN** el alumno confirma el consentimiento del examen por cualquiera de las dos ramas (liviana o completa)
- **THEN** el sistema siempre registra el acuse por-rendición atado al id del examen (cadena de custodia RN-CC)

### Requirement: Consentimiento sin pantalla de spinner intermedia

El paso de consentimiento (perfil y examen) SHALL NOT mostrar una pantalla de spinner que bloquee el render del layout mientras se carga el texto. El layout MUST renderizarse de inmediato y los bloques de texto MUST rellenarse cuando llega la respuesta (render progresivo), sin mensajes de "Cargando texto de consentimiento…".

#### Scenario: Carga del texto de consentimiento del perfil

- **WHEN** el alumno entra al paso de consentimiento del perfil y el texto aún no llegó
- **THEN** el encabezado, la versión visible y la acción se muestran de inmediato sin una pantalla de spinner intermedia
- **AND** los bloques informativos aparecen cuando la respuesta del texto llega

#### Scenario: Carga del texto de consentimiento del examen

- **WHEN** el alumno entra al paso de consentimiento del examen y el texto aún no llegó
- **THEN** no se muestra un mensaje de "Cargando texto de consentimiento…" bloqueante
- **AND** el contenido aparece cuando la respuesta llega, sin salto de layout disruptivo

