## ADDED Requirements

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
