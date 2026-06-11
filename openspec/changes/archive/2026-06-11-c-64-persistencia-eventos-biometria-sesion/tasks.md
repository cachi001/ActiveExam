## 1. Backend — Aceptar screenshot_sha256_cliente en IngestEventoIn

- [x] 1.1 En `backend/app/presentation/api/v1/proctoring/events/schemas.py`, agregar el campo `screenshot_sha256_cliente: str | None = Field(None, ...)` a `IngestEventoIn`, con descripción "Hash SHA-256 del screenshot calculado por el cliente (cadena de custodia C-49, D5). Opcional — no bloquea la ingestión si está ausente."
- [x] 1.2 Verificar que `backend/app/application/proctoring/event_service.py` recibe el campo `screenshot_sha256_cliente` desde el router y decidir: (a) ignorarlo si `ProctoringEventModel` no tiene la columna (sin migración), o (b) agregar la columna con una nueva migración. Elegir (a) si la columna no existe — el campo se acepta en el schema, se loguea en el payload, pero no se persiste en DB. Documentar la decisión como comentario en el servicio.
- [x] 1.3 Actualizar el router `backend/app/presentation/api/v1/proctoring/events/router.py` para pasar `screenshot_sha256_cliente=body.screenshot_sha256_cliente` al servicio si se decidió persistirlo, o para no pasarlo si se ignoró.

## 2. Backend — Endpoint PATCH /sessions/{id}/finalizar

- [x] 2.1 En `backend/app/infrastructure/persistence/repositories/proctoring.py`, agregar el método `finalizar_sesion(session_id: str) -> ProctoringSessionModel | None` que setea `finalizada_en = datetime.utcnow()` si y solo si `finalizada_en IS NULL`. Si la sesión no existe, devuelve `None`. Si ya está finalizada, devuelve la sesión sin modificar (idempotente).
- [x] 2.2 En `backend/app/application/proctoring/session_service.py`, agregar la función `finalizar_sesion(db: AsyncSession, session_id: str) -> ProctoringSessionModel | None` que delega al repo.
- [x] 2.3 En `backend/app/presentation/api/v1/proctoring/sessions/schemas.py`, agregar el schema `FinalizarSesionOut(BaseModel)` con campos `id: str` y `finalizada_en: Any`, con `model_config = ConfigDict(extra="forbid")`.
- [x] 2.4 En `backend/app/presentation/api/v1/proctoring/sessions/router.py`, agregar el endpoint `PATCH /sessions/{session_id}/finalizar` dentro de `create_sessions_router`. Responde 200 con `FinalizarSesionOut` si la sesión existe, 404 si no.

## 3. Backend — Tests de integración

- [x] 3.1 En `backend/tests/proctoring/test_session_api.py` (o nuevo archivo `test_finalizar.py`), agregar tests para `PATCH /sessions/{id}/finalizar`: (a) sesión existente → 200 con `finalizada_en` seteado; (b) sesión inexistente → 404; (c) sesión ya finalizada → 200 idempotente. Tests deben correr contra `app.main_slim` con `postgres:16-alpine`, sin mocks de DB.
- [x] 3.2 En `backend/tests/proctoring/test_event_ingestion.py`, agregar test que verifica que `POST /sessions/{id}/events` con el campo `screenshot_sha256_cliente` presente en el body responde 201 (no 422). El campo puede ser ignorado por el servicio — lo importante es que el schema lo acepte.

## 4. Frontend — Crear sesión anticipada en Consent.tsx

- [x] 4.1 En `frontend/src/screens/Consent.tsx`, en el handler de "Aceptar y continuar" (función que navega a `/biometria`), agregar la llamada a `api.crearSesionProctoring('examen', examen?.nombre, examen?.id)` ANTES de navegar, condicionada a `!proctoringSessionId` (idempotencia). Guardar el resultado con `setProctoringSessionId(s.id)`. Si la llamada falla, continuar igual (degradación silenciosa — el flujo no se bloquea por el proctoring).
- [x] 4.2 Importar `useApp` en `Consent.tsx` para leer `proctoringSessionId` y `setProctoringSessionId` si no están importados ya. Verificar que el store tiene ambos selectores (ya existen en `store.ts`).
- [x] 4.3 Verificar que `useExamProctoring` (usado en `Examen.tsx`) NO crea la sesión nuevamente si `proctoringSessionId` ya existe en el store. Si hoy siempre crea una nueva, agregar la condición: si `proctoringSessionId` ya está en el store al inicio del efecto, usarlo directamente en `sessionIdRef` sin llamar `api.crearSesionProctoring`.

## 5. Frontend — Loguear errores en handleEvent

- [x] 5.1 En `frontend/src/proctoring/useExamProctoring.ts`, en el catch de `api.enviarEventoProctoring` (~línea 225), agregar `console.error('[proctoring] POST evento falló:', err)` ANTES del cierre del catch. El comportamiento de resiliencia NO cambia (el buffer retiene el evento, el examen continúa).

## 6. Frontend — Cierre.tsx: finalizar sesión y mostrar conteos reales

- [x] 6.1 En `frontend/src/lib/api.ts`, agregar el método `finalizarSesionProctoring(sessionId: string): Promise<{ id: string; finalizada_en: string } | null>` que llama `PATCH /proctoring/sessions/{sessionId}/finalizar`. En modo mock o si falla, retorna null sin propagar. Seguir el mismo patrón fire-and-forget que los demás métodos de proctoring.
- [x] 6.2 En `frontend/src/lib/api.ts`, agregar el método `obtenerSesionProctoring(sessionId: string): Promise<SesionProctoringDetalle | null>` que llama `GET /proctoring/sessions/{sessionId}`. Si falla, retorna null. Agregar el tipo `SesionProctoringDetalle` con al menos `{ id: string; total_eventos?: number; score?: number; biometria?: { liveness_ok: boolean; resultado: string } | null }` o reutilizar un tipo existente si ya está definido en `api.ts`.
- [x] 6.3 En `frontend/src/screens/Cierre.tsx`, al montar el componente (useEffect), llamar en secuencia: (1) `api.finalizarSesionProctoring(proctoringSessionId)` para setear `finalizada_en`; (2) `api.obtenerSesionProctoring(proctoringSessionId)` para obtener los conteos reales. Almacenar en estado local (`useState`) los valores `totalEventos` y `scoreBackend`. Si cualquier llamada falla, usar valores de fallback (score del store, "—" para eventos).
- [x] 6.4 En `frontend/src/screens/Cierre.tsx`, actualizar la fila "Señales registradas" para mostrar `totalEventos` del backend (si disponible) en lugar de `anomalias.length`. Actualizar "Score de prioridad" para mostrar `scoreBackend` si disponible, o `score` del store como fallback.

## 7. Verificación E2E manual

- [x] 7.1 En Railway (prod): rendir un examen completo (login → consent → biometría → sala espera → examen → cierre). Verificar en la DB de Railway que: (a) `proctoring_event` tiene filas; (b) `proctoring_biometria` tiene 1 fila; (c) `proctoring_session.finalizada_en` no es null. Verificar en la pantalla de Cierre que los conteos muestran los valores reales (no 0).
