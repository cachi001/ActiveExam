# harness-engine-cache Specification

## Purpose
TBD - created by archiving change c-32-harness-motor-cache-ux. Update Purpose after archive.
## Requirements
### Requirement: Cache singleton del motor de visión a nivel módulo
`harnessEngineLoader.ts` SHALL maintain a module-level singleton of the initialized `VisionEngine` instance so that `loadRealEngine()` does NOT call `init()` more than once per page session regardless of how many times it is invoked.

#### Scenario: segunda llamada reutiliza el motor cacheado
- **WHEN** `loadRealEngine()` has already been called once and resolved successfully
- **THEN** a second call to `loadRealEngine()` SHALL return the same already-initialized `VisionEngine` instance WITHOUT calling `init()` again and WITHOUT triggering a network request for WASM/model files

#### Scenario: llamadas concurrentes no producen doble init
- **WHEN** two calls to `loadRealEngine()` are made before the first one has resolved
- **THEN** only ONE `init()` call SHALL occur; both callers SHALL receive the same resolved instance

#### Scenario: fallo de init limpia el cache para permitir reintento
- **WHEN** `loadRealEngine()` is called and `init()` throws
- **THEN** the module-level cache SHALL remain empty (no partial engine stored), and a subsequent call to `loadRealEngine()` SHALL attempt a fresh initialization

### Requirement: Función disposeRealEngine para limpieza explícita
`harnessEngineLoader.ts` SHALL export `disposeRealEngine(): Promise<void>` that calls `dispose()` on the cached engine (if any), clears both the instance cache and any in-flight init promise, and allows future calls to `loadRealEngine()` to re-initialize from scratch.

#### Scenario: dispose libera el motor cacheado
- **WHEN** `disposeRealEngine()` is called after a successful `loadRealEngine()`
- **THEN** the cached engine SHALL have `dispose()` called on it, the module cache SHALL be cleared, and a subsequent `loadRealEngine()` SHALL trigger a new `init()`

#### Scenario: dispose es seguro cuando no hay cache
- **WHEN** `disposeRealEngine()` is called before any `loadRealEngine()` invocation
- **THEN** it SHALL resolve successfully without error

#### Scenario: componente llama disposeRealEngine al desmontarse
- **WHEN** `AdminDetectionHarness` unmounts (user navigates away)
- **THEN** `disposeRealEngine()` SHALL be called in the `useEffect` cleanup to release GPU/WASM resources

