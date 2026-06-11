# harness-model-loader

## Purpose

Define el loader dinámico del motor real de visión usado por el harness admin y el script de descarga de modelos MediaPipe. Garantiza que los modelos `.task` vivan fuera de git (descargados con `scripts/download-mediapipe-models.{sh,ps1}` con versión fijada) y que el harness los cargue lazy desde rutas locales `/mediapipe/` cuando se entra al diagnóstico.
## Requirements
### Requirement: Loader async para el motor real
`harnessEngineLoader.ts` SHALL export an async function `loadRealEngine(): Promise<VisionEngine>` that dynamically imports `RealMediaPipeVisionEngine`, instantiates it (only on the first call per page session), calls `init()` (only once), and returns the ready instance. On subsequent calls within the same page session, `loadRealEngine()` SHALL return the cached already-initialized instance without calling `init()` again.

Additionally, `harnessEngineLoader.ts` SHALL export `disposeRealEngine(): Promise<void>` that disposes the cached engine and clears the cache, allowing future calls to `loadRealEngine()` to re-initialize.

#### Scenario: carga exitosa devuelve motor inicializado
- **WHEN** `loadRealEngine()` is called and all model files are present
- **THEN** it SHALL return a `VisionEngine` instance that is ready to process frames (i.e., `init()` already called successfully)

#### Scenario: segunda invocación reutiliza motor cacheado sin re-init
- **WHEN** `loadRealEngine()` is called a second time after a successful first call in the same page session
- **THEN** it SHALL return the same cached `VisionEngine` instance WITHOUT calling `init()` again and WITHOUT triggering any network/WASM load

#### Scenario: error de carga propaga el error original
- **WHEN** `loadRealEngine()` is called and `init()` throws (model missing, WebGL absent)
- **THEN** `loadRealEngine()` SHALL reject with the original error (NOT swallow it or return a simulated engine)
- **AND** the module cache SHALL remain empty so that a subsequent call can retry initialization

#### Scenario: disposeRealEngine limpia el cache
- **WHEN** `disposeRealEngine()` is called after a successful `loadRealEngine()`
- **THEN** the cached engine SHALL have `dispose()` called, the cache SHALL be cleared, and a subsequent `loadRealEngine()` SHALL perform a fresh initialization

### Requirement: Script de descarga de modelos MediaPipe
The project SHALL provide scripts `scripts/download-mediapipe-models.sh` (bash) and `scripts/download-mediapipe-models.ps1` (PowerShell) that download the three required `.task` model files from pinned versioned URLs at `storage.googleapis.com/mediapipe-models` and place them in `frontend/public/mediapipe/`.

#### Scenario: script descarga los tres modelos con versión fijada
- **WHEN** the script is executed in the project root
- **THEN** `frontend/public/mediapipe/face_detector_short_range.task`, `frontend/public/mediapipe/face_landmarker.task`, and `frontend/public/mediapipe/pose_landmarker_lite.task` SHALL be present after completion, at the exact version pinned in the script

#### Scenario: script verifica integridad opcional
- **WHEN** the script completes the download
- **THEN** it SHOULD print the size of each downloaded file so the operator can verify the download was not truncated

#### Scenario: modelos fuera del repositorio git
- **WHEN** the `.gitignore` is evaluated
- **THEN** `frontend/public/mediapipe/*.task` and `frontend/public/mediapipe/*.wasm` SHALL be listed in `.gitignore`, and a `frontend/public/mediapipe/.gitkeep` SHALL keep the directory tracked

### Requirement: Documentar el proceso de setup de modelos
The README or setup documentation SHALL clearly describe that running the download script is required before the harness can use the real vision engine.

#### Scenario: README indica el paso de descarga de modelos
- **WHEN** a developer sets up the project for the first time
- **THEN** the setup instructions SHALL include an explicit step: "Run `scripts/download-mediapipe-models.sh` (or `.ps1`) to download vision models required for the admin detection harness"

### Requirement: Loader lazy singleton para el enrollment (`enrollmentEngineLoader.ts`)
El sistema SHALL proveer `frontend/src/vision/enrollmentEngineLoader.ts` con las funciones `loadEnrollmentEngine(): Promise<VisionEngine>` y `disposeEnrollmentEngine(): Promise<void>`, implementando el mismo patrón singleton de `harnessEngineLoader.ts` pero con variables de módulo independientes.

#### Scenario: Carga por primera vez
- **WHEN** `loadEnrollmentEngine()` es llamada y `_cachedEnrollmentEngine` es `null`
- **THEN** el sistema hace dynamic import de `RealMediaPipeVisionEngine`, llama `init()`, guarda la instancia en cache y la retorna

#### Scenario: Doble llamada concurrente antes de resolver
- **WHEN** dos llamadas a `loadEnrollmentEngine()` ocurren antes de que la primera resuelva
- **THEN** ambas esperan la misma promesa `_enrollmentInitPromise` sin lanzar dos `init()` simultáneos

#### Scenario: Fallo de init
- **WHEN** `init()` lanza (WebGL ausente, modelo 404)
- **THEN** `_enrollmentInitPromise` se limpia a `null`, `_cachedEnrollmentEngine` permanece `null`, y la promesa rechaza con el error original

#### Scenario: Dispose libera el cache
- **WHEN** `disposeEnrollmentEngine()` es llamada
- **THEN** el sistema llama `dispose()` sobre la instancia cacheada (si existe), setea `_cachedEnrollmentEngine = null` e `_enrollmentInitPromise = null`

### Requirement: Independencia de ciclos de vida entre enrollment y harness
El sistema SHALL mantener `enrollmentEngineLoader` y `harnessEngineLoader` como módulos con variables de módulo separadas, de modo que el dispose de uno no afecte la instancia del otro.

#### Scenario: Harness y enrollment con instancias independientes
- **WHEN** tanto el harness admin como el enrollment están activos en la misma sesión (tabs distintas o rutas distintas)
- **THEN** cada loader gestiona su propia instancia de `RealMediaPipeVisionEngine`; dispose del harness no invalida el cache del enrollment y viceversa

### Requirement: Bundle split — motor WASM fuera del chunk inicial
El sistema SHALL garantizar que el dynamic import en `enrollmentEngineLoader.ts` sea la única referencia al módulo `RealMediaPipeVisionEngine` desde el enrollment, de modo que Vite emita el motor en un chunk separado del bundle inicial.

#### Scenario: No hay import estático de RealMediaPipeVisionEngine en el enrollment
- **WHEN** se analiza el bundle de producción
- **THEN** el chunk inicial del enrollment NO contiene código de `@mediapipe/tasks-vision` ni de `RealMediaPipeVisionEngine`

