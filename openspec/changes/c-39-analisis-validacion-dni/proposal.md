## Why

C-38 captura frente y dorso del DNI y los guarda, pero la interfaz no muestra ningún resultado: el alumno ve "DNI registrado (frente y dorso)" sin saber si el documento es legible, si los datos coinciden o si hay algún problema. Para una demo convincente del flujo de enrollment, el sistema necesita una interfaz de análisis indicativo (mock client-side con UX realista) que simule el proceso de verificación documental que en producción ocurre server-side, manteniendo el disclaimer claro de que es preliminar y sujeto a revisión humana (L2.5).

## What Changes

- **Nuevo tipo `AnalisisDNI`** en `types.ts`: resultado indicativo del análisis con checks booleanos, datos OCR mock, score de concordancia facial y estado preliminar.
- **Extensión de `EscaneDNI`**: campo opcional `analisis?: AnalisisDNI` que se completa tras el guardado.
- **Nuevo mock `api.analizarDNI()`**: simula análisis con delay realista (1.5–2s), devuelve datos coherentes con el alumno demo "Emiliano Cáceres" (FRM-23-4912), y calcula concordancia facial mock contra la `ReferenciasBiometrica` existente.
- **Fase "Analizando…" en `EnrollmentDniStep`**: tras capturar frente+dorso, spinner de análisis → panel de resultados con checks, datos extraídos, score de concordancia y estado general con disclaimer L2.5.
- **Resumen en `StudentProfile`** sección DNI: muestra el estado del análisis ("Análisis preliminar OK · pendiente de revisión") en lugar del texto estático actual.
- **Disclaimer obligatorio** en toda vista de resultados: el análisis es indicativo; la validación oficial (RENAPER, autenticidad, MRZ/PDF417) es server-side; el cliente es sensor no confiable (RN-GLB-01).

## Capabilities

### New Capabilities

- `dni-analysis-panel`: Panel de resultados del análisis indicativo del DNI: checks visuales (documento detectado, imagen legible, tipo, PDF417 leído), datos OCR mock extraídos, score de concordancia facial, estado general y disclaimer L2.5. Se muestra tras la captura en `EnrollmentDniStep` y puede consultarse desde `StudentProfile`.

### Modified Capabilities

- `dni-scanner-dual-side` (C-38): extiende el flujo post-captura con fase "Analizando…" + panel de resultados. El guardado ahora también dispara el análisis mock. Se agrega el tipo `AnalisisDNI` a `EscaneDNI`.
- `student-profile-shell` (C-37/C-38): sección DNI muestra estado del análisis cuando existe, en lugar del texto estático "DNI registrado".

## Impact

- `frontend/src/lib/types.ts` — nuevo tipo `AnalisisDNI` + extensión de `EscaneDNI` con campo `analisis?`
- `frontend/src/lib/api.ts` — nuevo mock `analizarDNI()` + `guardarEscaneDNI()` retorna análisis integrado
- `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — nueva fase 'analizando' + fase 'resultado' con panel
- `frontend/src/screens/StudentProfile.tsx` — sección DNI: mostrar estado del análisis si existe
- No afecta el motor de visión (MediaPipe), ni el pipeline de proctoring, ni ningún componente de backend.
