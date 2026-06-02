## ADDED Requirements

### Requirement: No development jargon in user-facing text
El sistema SHALL no mostrar los términos "demo", "stub", "Ej:" ni "modo demo" en ningún texto visible al usuario final (labels, placeholders, títulos de secciones, mensajes de estado, atributos `title` de elementos HTML). Los disclaimers legales L2.5 y las notas de privacidad (Ley 25.326) que contengan estos términos MUST reformularse conservando íntegro su significado legal.

#### Scenario: No demo label in EnrollmentDniStep OCR section
- **WHEN** se renderiza la sección de resultados OCR en EnrollmentDniStep
- **THEN** el encabezado de la sección dice "Datos extraídos por OCR" sin "(demo)"

#### Scenario: L2.5 disclaimer body preserved in EnrollmentDniStep
- **WHEN** se renderiza el disclaimer del análisis de DNI en EnrollmentDniStep
- **THEN** el cuerpo del disclaimer contiene "La validación oficial del documento... se realiza server-side" y "La decisión de habilitación o sanción es siempre humana" (texto legal L2.5 íntegro)

#### Scenario: No demo label in EnrollmentDniStep analysis header
- **WHEN** se renderiza el encabezado del bloque de análisis indicativo en EnrollmentDniStep
- **THEN** el encabezado dice "Análisis indicativo" sin "(demo)"

#### Scenario: No modo demo in EquipmentCheck failure message
- **WHEN** hay requisitos con fallas en EquipmentCheck y se muestra el mensaje
- **THEN** el mensaje NO contiene el texto "(modo demo)" o "modo demo"

#### Scenario: No stub reference in AdminDetectionHarness error
- **WHEN** el motor MediaPipe falla al cargar en AdminDetectionHarness
- **THEN** el mensaje de error dice "Las señales de visión corresponden al motor de respaldo (sin MediaPipe)" o equivalente sin la palabra "stub"

### Requirement: ConfigureExam placeholders are neutral
Los placeholders de los campos de texto en ConfigureExam SHALL ser descriptivos del dato esperado, sin usar el prefijo "Ej:" ni ejemplos literales.

#### Scenario: Exam name placeholder is neutral
- **WHEN** se renderiza el campo "Nombre del examen" en ConfigureExam
- **THEN** el placeholder dice "Nombre del examen" (u otro texto neutro sin "Ej:")

#### Scenario: Catedra placeholder is neutral
- **WHEN** se renderiza el campo "Cátedra" en ConfigureExam
- **THEN** el placeholder dice "Nombre de la cátedra" (u otro texto neutro sin "Ej:")

### Requirement: StudentProfile coming soon text is neutral
El texto mostrado cuando `ENABLE_DNI_SCAN` es falso en StudentProfile SHALL decir "No disponible en esta versión" (o equivalente neutro) en lugar de "Disponible próximamente". El resto del texto que explica el tratamiento legal del dato MUST conservarse.

#### Scenario: DNI unavailable text is neutral
- **WHEN** `ENABLE_DNI_SCAN` es `false` en StudentProfile
- **THEN** el texto no contiene "próximamente" ni variantes de marketing/roadmap
- **AND** el texto conserva la referencia a Ley 25.326 y tratamiento como dato sensible

### Requirement: ScreenNavigator texts are neutral
Los textos del componente ScreenNavigator (atributo `title` del botón flotante y la etiqueta de modo) SHALL ser neutros respecto al contexto de desarrollo.

#### Scenario: Button title is neutral
- **WHEN** se inspecciona el atributo `title` del botón flotante de ScreenNavigator
- **THEN** dice "Navegador de pantallas" sin "(demo)"

#### Scenario: Mode label reformulated
- **WHEN** `api.modoDemo` es `true` en ScreenNavigator
- **THEN** la etiqueta muestra "Modo simulación" en lugar de "Modo demo"
