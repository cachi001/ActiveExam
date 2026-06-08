## 1. Dominio backend — entidad y reglas

- [x] 1.1 Crear `backend/app/domain/entities/alternative_request.py` con la entidad `SolicitudViaAlternativa` (frozen dataclass: `id`, `user_id`, `exam_id`, `estado: EstadoViaAlternativa`, `timestamp_solicitud`, `timestamp_habilitacion: str | None`, `habilitado_por: str | None`)
- [x] 1.2 Crear `EstadoViaAlternativa(str, enum.Enum)` con valores `pendiente_proctor` y `habilitado_por_proctor` en el mismo archivo o en un módulo de enums de dominio
- [x] 1.3 Extender `ResolucionConsentimiento` en `backend/app/domain/consent_flow/rules.py` con `VIA_ALTERNATIVA_PENDIENTE = "via_alternativa_pendiente"` y `VIA_ALTERNATIVA_HABILITADA = "via_alternativa_habilitada"`
- [x] 1.4 Actualizar `evaluar_gate()` en `rules.py`: `VIA_ALTERNATIVA_PENDIENTE` levanta `ConsentNotResolvedError`; `VIA_ALTERNATIVA_HABILITADA` retorna `True`; `VIA_ALTERNATIVA` existente se trata como `HABILITADA` (retrocompatibilidad)
- [x] 1.5 Actualizar `biometria_habilitada()` en `rules.py`: `VIA_ALTERNATIVA_HABILITADA` retorna `False` (verificación fue humana)

## 2. Puerto de repositorio — SolicitudViaAlternativa

- [x] 2.1 Definir `AlternativeRequestRepository` en `backend/app/domain/repositories/ports.py` con métodos: `add(solicitud) → SolicitudViaAlternativa`, `get_by_user_exam(user_id, exam_id) → SolicitudViaAlternativa | None`, `list_pending() → list[SolicitudViaAlternativa]`, `update_estado(id, estado, habilitado_por, timestamp) → SolicitudViaAlternativa`

## 3. Persistencia — ORM y migración Alembic

- [x] 3.1 Crear modelo SQLAlchemy `SolicitudViaAlternativaModel` en `backend/app/infrastructure/persistence/models/alternative_request.py` con el ENUM `estado` y columnas del diseño D-01
- [x] 3.2 Crear migración Alembic (no destructiva): `CREATE TYPE estado_via_alternativa AS ENUM ('pendiente_proctor', 'habilitado_por_proctor')` + `CREATE TABLE solicitudes_via_alternativa`
- [x] 3.3 Implementar `AlternativeRequestRepositoryImpl` en `backend/app/infrastructure/persistence/repositories/alternative_request.py` con los 4 métodos del puerto

## 4. Capa de aplicación — ConsentService

- [x] 4.1 Inyectar `AlternativeRequestRepository` en `ConsentService.__init__`
- [x] 4.2 Implementar `registrar_solicitud_alternativa(user_id, exam_id, timestamp) → SolicitudViaAlternativa` en `ConsentService` — crea la solicitud con estado `pendiente_proctor` y registra en audit log (preservando el append existente de `ACCION_VIA_ALTERNATIVA`)
- [x] 4.3 Implementar `habilitar_alternativa(user_id, exam_id, habilitado_por, timestamp) → SolicitudViaAlternativa` — valida que exista y esté `pendiente_proctor`, transiciona a `habilitado_por_proctor`
- [x] 4.4 Implementar `listar_pendientes() → list[SolicitudViaAlternativa]`
- [x] 4.5 Actualizar `resolve(user_id, exam_id)` en `ConsentService`: consultar la tabla nueva primero; retornar `VIA_ALTERNATIVA_PENDIENTE` o `VIA_ALTERNATIVA_HABILITADA` según el estado; mantener fallback al audit log para retrocompatibilidad

## 5. Presentación backend — endpoints REST

- [x] 5.1 Agregar schemas Pydantic en `backend/app/presentation/api/v1/consent/schemas.py`: `HabilitarAlternativaRequest` (exam_id: str), `HabilitarAlternativaResponse` (user_id, exam_id, estado, habilitado_por, timestamp_habilitacion), `PendienteItem` (user_id, exam_id, timestamp_solicitud), `PendientesResponse` (items: list[PendienteItem]). Todos con `model_config = ConfigDict(extra='forbid')`
- [x] 5.2 Agregar endpoint `POST /alternative/{user_id}/habilitar` en `router.py` — auth: verificar rol proctor o admin; llama `service.habilitar_alternativa`; retorna 404 si no existe
- [x] 5.3 Agregar endpoint `GET /alternative/pendientes` en `router.py` — auth: proctor o admin; llama `service.listar_pendientes`
- [x] 5.4 Actualizar el endpoint `POST /alternative` existente (choose_alternative) para llamar `service.registrar_solicitud_alternativa` además del audit log/cola existentes — incluir `estado: "pendiente_proctor"` y `puede_rendir: false` en la respuesta `AlternativeResponse`
- [x] 5.5 Actualizar `AlternativeResponse` schema para incluir `estado: str` y `puede_rendir: bool`

## 6. Frontend — eliminar bypass y tipos

- [x] 6.1 Eliminar la línea `e.consentimiento?.via_alternativa === true ||` de `recalcularPerfilCompleto()` en `frontend/src/lib/api.ts` (línea ~165)
- [x] 6.2 Agregar método `solicitarViaAlternativa(examId: string): Promise<{ estado: string; puede_rendir: boolean }>` en `api.ts` que llama `POST /api/v1/consent/alternative`
- [x] 6.3 Agregar método `estadoViaAlternativa(examId: string): Promise<{ estado: string } | null>` en `api.ts`
- [x] 6.4 Actualizar `puedeRendir()` en `api.ts` para reconocer código `via_alternativa_pendiente` y retornar `{ puede: false, codigo: "via_alternativa_pendiente", razon: "Tu verificación alternativa está pendiente de aprobación de un proctor." }`
- [x] 6.5 Actualizar `puedeRendir()` para reconocer `via_alternativa_habilitada` → `{ puede: true }` (perfil completo via habilitación humana)
- [x] 6.6 Actualizar el mock en `enrollmentAlumno` / `recalcularPerfilCompleto` para simular los nuevos estados en desarrollo local

## 7. Frontend — Consent.tsx

- [x] 7.1 Reemplazar la función `alternativa()` (toast vacío + navigate) en `Consent.tsx` por una función `async alternativa()` que llame `api.solicitarViaAlternativa(examen.id)` y actualice estado local a `pendiente`
- [x] 7.2 Agregar estado local `estadoAlternativa: 'idle' | 'solicitando' | 'pendiente'` en `Consent.tsx`
- [x] 7.3 Agregar Card informativo que se muestra cuando `estadoAlternativa === 'pendiente'`: mensaje "Tu solicitud quedó registrada. Un proctor verificará tu identidad antes de habilitarte. No podés rendir hasta entonces." con icono `support_agent`
- [x] 7.4 Cuando `yaConsintioPerfil && acusePerfil?.via_alternativa && estadoAlternativa !== 'habilitado'` mostrar el card de espera en lugar del flujo normal de confirmación

## 8. Frontend — EnrollmentConsentStep.tsx

- [x] 8.1 Actualizar `handleViaAlternativa` en `EnrollmentConsentStep.tsx` para llamar `api.solicitarViaAlternativa("perfil")` (exam_id sentinel = "perfil") y agregar estado local `solicitandoAlternativa`
- [x] 8.2 Mostrar card informativo "Tu solicitud quedó registrada. Un proctor verificará tu identidad." cuando la solicitud fue enviada, en lugar de llamar `onConsentido` inmediatamente
- [x] 8.3 Ajustar el callback `onConsentido` para el caso de alternativa: pasar el acuse con `via_alternativa: true` solo cuando el proctor habilite (o diferir la notificación — ver Open Question sobre exam_id sentinel)

## 9. Frontend — Mis Exámenes (badge de estado)

- [x] 9.1 Identificar el componente de lista de inscripciones que corresponde a Mis Exámenes (verificar si existe; si no, anotar la ruta esperada)
- [x] 9.2 Consultar `api.estadoViaAlternativa(examenId)` al renderizar cada inscripción
- [x] 9.3 Mostrar badge "Verificación alternativa pendiente" cuando el estado es `pendiente_proctor`
- [x] 9.4 Deshabilitar el botón "Rendir" con texto explicativo "Pendiente de habilitación por proctor" cuando `puedeRendir` retorna `via_alternativa_pendiente`

## 10. Tests backend (módulo slim, postgres:16-alpine)

- [x] 10.1 Test unitario puro de `rules.py`: `evaluar_gate(VIA_ALTERNATIVA_PENDIENTE)` levanta `ConsentNotResolvedError`; `evaluar_gate(VIA_ALTERNATIVA_HABILITADA)` retorna `True`; retrocompatibilidad `VIA_ALTERNATIVA` → habilitado
- [x] 10.2 Test de repositorio (`AlternativeRequestRepositoryImpl`) contra postgres real: crear solicitud pendiente, listar pendientes, actualizar a habilitado
- [x] 10.3 Test de `ConsentService.registrar_solicitud_alternativa` con repositorios reales: verifica persistencia y audit log
- [x] 10.4 Test de `ConsentService.habilitar_alternativa`: transición de estado, registro de `habilitado_por`; error si solicitud inexistente
- [x] 10.5 Test de `ConsentService.resolve` con estados nuevos: `pendiente_proctor → VIA_ALTERNATIVA_PENDIENTE`; `habilitado_por_proctor → VIA_ALTERNATIVA_HABILITADA`; fallback audit log
- [x] 10.6 Test de endpoint `POST /alternative/{user_id}/habilitar`: 200 con proctor auth, 403 sin rol, 404 si no existe
- [x] 10.7 Test de endpoint `GET /alternative/pendientes`: lista correcta, 403 sin rol
- [x] 10.8 Test de `puedeRendir` backend (gate vía api/service): bloquea con pendiente, permite con habilitado

## 11. Validación integración frontend

- [x] 11.1 Verificar manualmente (o con playwright si disponible) que el flujo normal (aceptar + biometría) no se rompe
- [x] 11.2 Verificar que al elegir vía alternativa en `Consent.tsx` NO se navega a `/sala-espera` y aparece el card de espera
- [x] 11.3 Verificar que `puedeRendir()` retorna el código `via_alternativa_pendiente` con el mensaje correcto en el mock de desarrollo
