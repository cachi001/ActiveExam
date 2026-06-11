## ADDED Requirements

### Requirement: Tipo AnalisisDNI
El sistema SHALL definir el tipo `AnalisisDNI` en `frontend/src/lib/types.ts` con los siguientes campos: checks booleanos de integridad (`documento_detectado`, `imagen_legible`, `tipo_documento`, `pdf417_leido`), datos OCR mock (`datos_extraidos` con número de documento, apellido, nombre, fecha de nacimiento, fecha de vencimiento, sexo y CUIL), score de concordancia facial (`concordancia_facial: number` en rango 0..1), estado general (`estado: EstadoAnalisisDNI`), y metadatos del análisis (`timestamp_analisis`, `version_analisis`). El tipo `EstadoAnalisisDNI` SHALL ser `'preliminar_ok' | 'requiere_revision'` — NUNCA `'aprobado'` ni `'rechazado'`.

#### Scenario: Estado permitido preliminar_ok
- **WHEN** todos los checks de integridad son `true` y `concordancia_facial >= 0.85`
- **THEN** el campo `estado` SHALL ser `'preliminar_ok'`

#### Scenario: Estado permitido requiere_revision
- **WHEN** algún check de integridad es `false` o `concordancia_facial < 0.85`
- **THEN** el campo `estado` SHALL ser `'requiere_revision'`

### Requirement: Mock api.analizarDNI
El sistema SHALL implementar `api.analizarDNI(): Promise<AnalisisDNI>` como función mock que simula el análisis indicativo del DNI con un delay de 1.5–2s. El mock SHALL retornar datos coherentes con el alumno demo "Emiliano Cáceres" (FRM-23-4912) y `concordancia_facial` en el rango 0.88–0.96 (base determinista con variación cosmética). El mock MUST NO transmitir ningún dato a servicios externos (todo en memoria de sesión).

#### Scenario: Llamada a analizarDNI retorna análisis completo
- **WHEN** se invoca `api.analizarDNI()`
- **THEN** después de 1.5–2s SHALL retornar un `AnalisisDNI` con todos los campos completos, `estado: 'preliminar_ok'`, datos del alumno demo y `version_analisis: 'mock-v1'`

#### Scenario: Mock sin transmisión externa
- **WHEN** se invoca `api.analizarDNI()` en modo demo
- **THEN** el resultado SHALL ser generado localmente sin ninguna llamada de red

### Requirement: Fase analizando en EnrollmentDniStep
El sistema SHALL mostrar una fase de "analizando" con spinner y texto "Verificando documento…" tras capturar frente+dorso mientras `api.analizarDNI()` está en progreso.

#### Scenario: Transición automática a fase analizando
- **WHEN** `handleDorsoCapturado` finaliza el guardado del escaneo
- **THEN** SHALL mostrarse inmediatamente el spinner de análisis antes de que el usuario realice ninguna acción

#### Scenario: Duración mínima visible
- **WHEN** la fase analizando está activa
- **THEN** SHALL ser visible al menos 1.5 segundos (duración del mock) para que el usuario perciba el proceso

### Requirement: Panel de resultados del análisis en EnrollmentDniStep
El sistema SHALL mostrar un panel de resultados con cuatro secciones tras completar el análisis: (1) checks de integridad documental con íconos visuales, (2) datos OCR extraídos en grid, (3) barra de concordancia facial con porcentaje, y (4) estado general con badge. El panel SHALL reusar los componentes `Card`, `Badge`, `Icon` existentes sin nuevas dependencias de UI.

#### Scenario: Checks de integridad visibles
- **WHEN** el panel de resultados está visible
- **THEN** SHALL mostrarse al menos: documento detectado, imagen legible, tipo de documento y código de barras (PDF417) — cada uno con ícono y texto descriptivo

#### Scenario: Datos OCR en grid
- **WHEN** el panel de resultados está visible
- **THEN** SHALL mostrarse en un grid: nombre completo, número de documento, fecha de nacimiento, fecha de vencimiento y CUIL — con nota explícita "Extraídos por OCR (demo)"

#### Scenario: Concordancia facial con porcentaje
- **WHEN** el panel de resultados está visible
- **THEN** SHALL mostrarse la concordancia facial como barra de progreso y porcentaje, con una nota explicando que se compara contra la referencia biométrica del perfil

#### Scenario: Badge de estado general
- **WHEN** el estado del análisis es 'preliminar_ok'
- **THEN** SHALL mostrarse un badge verde/success con texto "Análisis preliminar — OK"

#### Scenario: Badge de estado requiere revisión
- **WHEN** el estado del análisis es 'requiere_revision'
- **THEN** SHALL mostrarse un badge amarillo/warning con texto "Análisis preliminar — Requiere revisión"

### Requirement: Disclaimer L2.5 obligatorio en panel de resultados
El sistema SHALL incluir un disclaimer permanente e inamovible en el panel de resultados del análisis que mencione: (a) el carácter indicativo del análisis (demo), (b) que la validación oficial es server-side, (c) que el cliente es sensor no confiable (RN-GLB-01), y (d) que la decisión final es siempre humana (L2.5).

#### Scenario: Disclaimer visible en toda presentación de resultados
- **WHEN** el panel de resultados está visible (estado 'preliminar_ok' o 'requiere_revision')
- **THEN** SHALL mostrarse el disclaimer completo que incluya los cuatro puntos obligatorios

#### Scenario: Disclaimer no ocultable
- **WHEN** el usuario ve el panel de resultados
- **THEN** el disclaimer SHALL estar siempre visible, sin posibilidad de colapsar ni cerrar

### Requirement: Botón Continuar tras ver resultados
El sistema SHALL ofrecer un botón "Continuar" en el panel de resultados para que el alumno avance al paso siguiente del perfil, independientemente del estado del análisis.

#### Scenario: Continuar disponible para ambos estados
- **WHEN** el análisis muestra 'preliminar_ok' o 'requiere_revision'
- **THEN** SHALL estar disponible un botón "Continuar" que llame a `onEscaneado` con el escaneo completo (incluyendo el análisis adjunto)
