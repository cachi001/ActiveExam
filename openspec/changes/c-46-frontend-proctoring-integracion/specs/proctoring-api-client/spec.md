## ADDED Requirements

### Requirement: Tipos TypeScript de proctoring alineados con el backend C-45
El sistema SHALL definir en `frontend/src/lib/types.ts` los siguientes tipos TypeScript que espejean exactamente el contrato del backend slim C-45: `SesionProctoringResumen` (id, modo, etiqueta, creada_en, total_eventos, total_discrepancias, score), `SesionProctoringDetalle` (todos los campos del resumen + eventos[] + biometria + score), `EventoProctoringDetalle` (evento_id, tipo, severidad, ts_cliente, payload, screenshot_base64, screenshot_sha256, face_count_cliente, veredicto_reinferencia, face_count_servidor), `BiometriaDetalle` (liveness_ok, retos_resueltos, resultado), `VeredictoReinferencia` (tipo literal: 'coincide' | 'discrepancia' | 'sin_referencia' | 'error').

#### Scenario: Tipos disponibles para importación
- **WHEN** un componente importa desde `types.ts`
- **THEN** puede usar `SesionProctoringResumen`, `SesionProctoringDetalle`, `EventoProctoringDetalle`, `BiometriaDetalle` y `VeredictoReinferencia` sin errores de TypeScript

### Requirement: `crearSesionProctoring` — dual-mode
El sistema SHALL exponer `api.crearSesionProctoring(modo: string, etiqueta?: string, examId?: string): Promise<{ id: string; creada_en: string }>`. Con `USE_REAL_BACKEND=1`: POST a `/proctoring/sessions` con body `{modo, exam_id?, etiqueta?}` y devuelve la respuesta del backend. Con `USE_REAL_BACKEND=0`: devuelve un objeto mock `{ id: 'mock-session-' + timestamp, creada_en: now }` con delay ~200ms. En ambos modos, si la llamada real falla, cae al mock silenciosamente.

#### Scenario: Modo real exitoso
- **WHEN** `USE_REAL_BACKEND=1` y el backend responde 200
- **THEN** `crearSesionProctoring` devuelve `{ id, creada_en }` del backend

#### Scenario: Fallback mock si el backend falla
- **WHEN** `USE_REAL_BACKEND=1` pero el backend devuelve error o no está disponible
- **THEN** `crearSesionProctoring` devuelve un objeto mock sin propagar el error

#### Scenario: Modo mock sin backend
- **WHEN** `USE_REAL_BACKEND=0`
- **THEN** `crearSesionProctoring` devuelve un objeto mock con delay simulado y sin llamada HTTP

### Requirement: `enviarEventoProctoring` — dual-mode
El sistema SHALL exponer `api.enviarEventoProctoring(sessionId: string, payload: { tipo: string; severidad: string; ts_cliente: string; payload?: Record<string,unknown>; screenshot_base64?: string; face_count_cliente?: number }): Promise<{ evento_id: string; veredicto_reinferencia: VeredictoReinferencia; face_count_servidor: number; screenshot_sha256: string } | null>`. Devuelve `null` en modo mock o si la llamada real falla. El campo `screenshot_base64` es opcional; si está presente, el backend re-infiere sobre él.

#### Scenario: Evento enviado con screenshot
- **WHEN** se llama con `screenshot_base64` no nulo y `USE_REAL_BACKEND=1`
- **THEN** el backend recibe el screenshot y devuelve `veredicto_reinferencia` y `face_count_servidor`

#### Scenario: Fallo de red silencioso
- **WHEN** la llamada HTTP falla (timeout, 5xx)
- **THEN** `enviarEventoProctoring` devuelve `null` sin propagar la excepción

### Requirement: `enviarBiometriaProctoring` — dual-mode
El sistema SHALL exponer `api.enviarBiometriaProctoring(sessionId: string, bio: { liveness_ok: boolean; retos_resueltos: string[]; embedding?: number[]; resultado: string }): Promise<{ ok: boolean }>`. Con `USE_REAL_BACKEND=1`: POST a `/proctoring/sessions/{sessionId}/biometria`. Con `USE_REAL_BACKEND=0` o en caso de error: devuelve `{ ok: true }` (fire-and-forget mock).

#### Scenario: Biometría enviada al backend
- **WHEN** `USE_REAL_BACKEND=1` y el backend responde 200
- **THEN** devuelve `{ ok: true }`

#### Scenario: Mock transparente
- **WHEN** `USE_REAL_BACKEND=0`
- **THEN** devuelve `{ ok: true }` con delay simulado, sin llamada HTTP

### Requirement: `listarSesionesProctoring` — dual-mode
El sistema SHALL exponer `api.listarSesionesProctoring(): Promise<SesionProctoringResumen[]>`. Con `USE_REAL_BACKEND=1`: GET a `/proctoring/sessions`. Con `USE_REAL_BACKEND=0` o en caso de error: devuelve un array de dos sesiones mock con datos plausibles (modos 'diagnostico' y 'examen', distintos scores y totales).

#### Scenario: Lista real desde backend
- **WHEN** `USE_REAL_BACKEND=1` y el backend responde 200
- **THEN** devuelve el array de `SesionProctoringResumen` del backend

#### Scenario: Lista mock sin backend
- **WHEN** `USE_REAL_BACKEND=0`
- **THEN** devuelve array mock con al menos dos sesiones de ejemplo

### Requirement: `getSesionProctoring` — dual-mode
El sistema SHALL exponer `api.getSesionProctoring(id: string): Promise<SesionProctoringDetalle>`. Con `USE_REAL_BACKEND=1`: GET a `/proctoring/sessions/{id}`. Con `USE_REAL_BACKEND=0` o en caso de error: devuelve un objeto mock que incluya al menos tres eventos con distintas severidades, un veredicto de re-inferencia variado y campos de biometría.

#### Scenario: Detalle real desde backend
- **WHEN** `USE_REAL_BACKEND=1` y el backend responde 200
- **THEN** devuelve el `SesionProctoringDetalle` completo del backend con eventos y biometría

#### Scenario: Detalle mock sin backend
- **WHEN** `USE_REAL_BACKEND=0`
- **THEN** devuelve detalle mock con eventos, veredictos y biometría simulada
