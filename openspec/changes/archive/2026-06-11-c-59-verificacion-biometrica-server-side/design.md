## Context

La verificación biométrica 1:1 nació stateless (C-45/demo): el endpoint `POST /api/v1/proctoring/biometria/verificar` recibe `{embedding_vivo, embedding_referencia, umbral}` del cliente, compara con `comparar_identidad` (distancia coseno, `UMBRAL_COSENO_DEFECTO=0.35`) y devuelve `{distancia, es_match, umbral}`. No toca la DB ni descifra nada.

En C-56 el enrollment cambió: el embedding de referencia se persiste **cifrado** en la tabla `embedding_referencia` (Fernet, `EmbeddingEncryptionService`), y el cliente solo retiene un `referencia_id` opaco (`embedding: null` en el store). Esto es correcto por Ley 25.326 (regla dura #7): el embedding es dato sensible, no debe viajar al cliente ni loguearse.

El problema: nadie cableó la verificación server-side. En modo real el frontend (`Biometria.tsx`) hace `if (!biometriaReferencia || biometriaReferencia.length === 0) setFase('no_enrolado')` y `api.verificarBiometria(vivo, biometriaReferencia)` exige el embedding de referencia local — que es `null` por diseño. Resultado: gate siempre en "no_enrolado". Un alumno con embedding cifrado en la DB (verificado: usuario `estudiante` tiene embeddings=2) no puede rendir.

Restricciones del entorno:
- Módulo slim en Railway (`Dockerfile.slim`, `app.main_slim`) contra Postgres estándar (sin TimescaleDB). Frontend en Vercel, modo real (`VITE_USE_REAL_BACKEND=1`, `VITE_AUTH_PROVIDER=jwt`).
- Reglas duras de dominio: #5 nunca sancionar automático (la verificación prioriza, no es veredicto), #6 cliente = sensor no confiable (comparación server-side), #7 embedding = dato sensible, cifrado at-rest, nunca crudo al cliente ni en logs.
- Reglas duras de código: snake_case Python, PascalCase React, Pydantic `extra='forbid'`, tests sin mocks de DB (Postgres real/efímero), Conventional Commits sin Co-Authored-By.

## Goals / Non-Goals

**Goals:**
- Un alumno con embedding cifrado en la DB puede pasar la verificación biométrica en producción (modo real) y rendir.
- La comparación 1:1 se ejecuta server-side: el backend identifica al usuario por su JWT, busca el embedding vigente, lo descifra y compara. El embedding de referencia NUNCA viaja al cliente ni aparece en logs.
- El frontend distingue claramente las dos ramas (real vs demo) y deriva el gate `no_enrolado` de la verdad del backend en modo real.
- Tests backend con Postgres real cubren match cercano, no-match lejano y ausencia de referencia.

**Non-Goals:**
- Re-inferencia server-side del embedding vivo (re-computar el descriptor a partir del frame en el backend). El cliente sigue computando el `embedding_vivo` (face-api en el navegador); este change solo mueve la **comparación contra la referencia** al server. La re-inferencia plena es C-09/C-12 — fuera de alcance.
- Liveness / anti-deepfake server-side (C-54/biometric-liveness ya existen).
- Cambios en el flujo de enrollment (C-56 ya persiste cifrado).
- Migraciones de esquema (se reusa `embedding_referencia`).
- Eliminar el endpoint stateless (se conserva para demo/retrocompat).

## Decisions

### D1 — Nuevo endpoint stateful autenticado, conservando el stateless

`POST /api/v1/proctoring/biometria/verificar-referencia`
- Auth: `require_roles(Rol.ESTUDIANTE)` (Bearer JWT propio HS256, `app.state.jwt_validator`).
- Body: `VerificarReferenciaIn { embedding_vivo: list[float], umbral: float | None }` (`extra='forbid'`). NO recibe `embedding_referencia`.
- Identidad: `principal.subject` (el `sub` del JWT = `str(usuario.id)`, el mismo UUID que usa enrollment en C-56). Si falta el subject → `401`.
- Respuesta: `VerificarReferenciaOut { distancia, es_match, umbral }` (idéntico shape al stateless, para minimizar el cambio en el frontend).

Alternativas consideradas:
- *Modificar el endpoint stateless existente para que sea stateful*: rompería la demo (que manda el embedding de referencia) y el contrato C-45. Descartado: el stateless se conserva tal cual, marcado demo-only.
- *Reusar la ruta `/biometria/verificar` con body opcional*: ambigüedad de contrato (`extra='forbid'` no admite "a veces con referencia, a veces sin"). Descartado por claridad.

**Por qué `404` y no `422` cuando no hay referencia**: distinguir semánticamente "no tenés referencia cargada" (recurso ausente → el frontend manda a `/perfil`) de "el embedding vivo es inválido / dimensión incorrecta" (`422`) y de "match fallido" (`200` con `es_match=false`). Esto es lo que arregla la UX rota: el gate `no_enrolado` se vuelve una señal explícita del backend, no una inferencia frágil del cliente.

### D2 — Reuso del descifrado existente (NO reimplementar cripto)

El descifrado se hace con `EmbeddingEncryptionService.decrypt(ciphertext) -> list[float]` (C-56, `app/infrastructure/crypto/embedding_encryption.py`), que ya está cableado en `app.state.embedding_encryption` en `main_slim.py` (línea 77, clave `SlimSettings.embedding_encryption_key`).

Flujo del nuevo endpoint:
1. `EmbeddingReferenciaRepository(session).obtener_vigente(usuario_id)` → `EmbeddingReferenciaModel | None`. Si `None` → `404`.
2. `embedding_encryption.decrypt(model.embedding_cifrado)` → `list[float]` (el plaintext vive solo en memoria, en el scope del request).
3. `comparar_identidad(embedding_vivo, embedding_referencia_descifrado, umbral=umbral or UMBRAL_COSENO_DEFECTO)` → `ResultadoComparacion`.
4. Devolver `{distancia, es_match, umbral}`. El embedding descifrado NO se loguea, NO se incluye en la respuesta, NO se persiste.

La lógica se encapsula en un **application service** nuevo (`app/application/biometrics/verificar_referencia_vigente.py` — `VerificarReferenciaVigenteService`, o un método en `application/biometrics/service.py` existente) que recibe `session`, `encryption` y devuelve un DTO puro. Esto mantiene el router fino (igual que el patrón de enrollment) y testeable sin FastAPI.

Alternativa: descifrar en el router. Descartado — viola separación de capas; el patrón del repo (C-56) ya delega a un application service.

**Manejo de error de descifrado**: si `decrypt` lanza `EmbeddingEncryptionError` (clave rotada sin re-encriptación / ciphertext corrupto) → `500` con mensaje genérico (NO exponer detalle de cripto). Es un fallo de operación, no del usuario.

### D3 — Endpoint de estado para el gate del frontend

`GET /api/v1/proctoring/biometria/referencia/estado`
- Auth: `require_roles(Rol.ESTUDIANTE)`.
- Respuesta: `EstadoReferenciaOut { tiene_referencia_vigente: bool }`.
- Implementación: `obtener_vigente(usuario_id) is not None`. NO descifra, NO devuelve el embedding ni el `referencia_id` (basta el booleano).

**Por qué un endpoint dedicado y no reusar `getEnrollment`**: en el frontend `getEnrollment()` (api.ts:590) es demo-only — devuelve el `enrollmentAlumno` en memoria, no consulta el backend. En modo real no hay forma de saber el estado de enrollment server-side. Un endpoint chico y barato resuelve el gate sin tocar el flujo de enrollment ni filtrar el embedding.

Alternativa: inferir el gate del `404` del endpoint de verificación. Descartado — obliga a capturar el frame y computar el embedding vivo solo para descubrir que no hay referencia; mala UX. El estado se chequea al montar la pantalla, antes de capturar.

### D4 — Cableado del router de biometría (DI desde el state)

Hoy `create_biometria_router(get_db)` solo recibe `get_db`. Pasa a recibir además el guard de auth y un accessor del `embedding_encryption`:
- `create_biometria_router(get_db, get_embedding_encryption, require_estudiante)` (firma a definir en apply; la decisión es que el router NO importe `SlimSettings` — recibe dependencias inyectadas, como el resto del slim).
- `proctoring/router.py` (`create_proctoring_router`) recibe el `embedding_encryption` y lo propaga al sub-router de biometría.
- `main_slim.py` ya tiene `app.state.embedding_encryption` y el `jwt_validator` cableados; pasa el `embedding_encryption` al `create_proctoring_router`.

El endpoint stateless `POST /biometria/verificar` queda **sin auth** (demo, como hoy). Los dos nuevos endpoints stateful exigen `Rol.ESTUDIANTE`.

### D5 — Frontend: dos ramas explícitas (real vs demo)

`api.ts`:
- Nuevo método `estadoReferenciaBiometrica(): Promise<{ tiene_referencia_vigente: boolean }>`. En real: `GET /proctoring/biometria/referencia/estado`. En demo: deriva de `enrollmentAlumno.biometria?.captura_completada`.
- Verificación: en real, llamar al endpoint stateful (`verificar-referencia`) mandando solo `embedding_vivo` (+ umbral opcional); en demo, mantener la comparación coseno local contra `biometriaReferencia`. Se puede hacer con una nueva función `verificarBiometriaReferencia(embeddingVivo, umbral?)` para la rama real y dejar `verificarBiometria` para demo, o ramificar dentro del método existente. La decisión de design: **ramas separadas y documentadas**, sin mezclar el contrato (real no manda referencia, demo sí).

`Biometria.tsx`:
- Al montar (o en `preparar`), si `USE_REAL_BACKEND`, consultar `estadoReferenciaBiometrica()` y setear `no_enrolado` según `tiene_referencia_vigente`. En demo, mantener el gate basado en `biometriaReferencia`.
- En `handleComplete`, el gate de enrolamiento (`if (!biometriaReferencia...)`) NO aplica en modo real (en real `biometriaReferencia` es `null` por diseño): en real se procede a capturar el embedding vivo y llamar al endpoint stateful, que responde `404` si no hay referencia (defensa en profundidad) o `{distancia, es_match}` si la hay.

### D6 — Umbral

El cliente puede no mandar `umbral`; el backend usa `UMBRAL_COSENO_DEFECTO` (0.35). El umbral operativo definitivo lo fija la config del examen (C-07, fuera de alcance). Para este change, default conservador server-side (RN-BIO-03).

## Risks / Trade-offs

- [El `embedding_vivo` sigue computándose en el cliente (face-api)] → Mitigación: aceptable para este change (cliente = sensor no confiable solo para la **referencia**, que es lo sensible); la re-inferencia plena del vivo es C-09/C-12. Documentado como Non-Goal.
- [El embedding descifrado vive en memoria del proceso durante el request] → Mitigación: scope acotado al request, nunca se loguea ni se serializa en la respuesta; es inevitable para comparar. No se persiste plaintext.
- [Dimensión del `embedding_vivo` distinta de la referencia (128-d)] → `comparar_identidad` lanza `EmbeddingInvalidoError` → `422` con mensaje claro. Cubierto por test.
- [El `sub` del JWT no coincide con el `usuario_id` de enrollment] → enrollment (C-56) persiste con `principal.subject`; este endpoint busca con `principal.subject`. Misma fuente, consistente. Cubierto por test E2E (enrollment → verificación con el mismo token).
- [Error de descifrado por clave rotada] → `500` genérico, sin filtrar detalle de cripto; alerta de operación (runbook: re-encriptar embeddings).
- [El endpoint stateless sin auth sigue expuesto] → se conserva por retrocompat/demo, marcado demo-only; no procesa datos sensibles del backend (recibe ambos embeddings del cliente). Sin regresión de privacidad.

## Migration Plan

1. Backend: agregar schemas + application service + dos endpoints + cableado del router. Sin migración de DB (reusa `embedding_referencia`).
2. Tests backend con Postgres real (sin mocks): enrollment cifrado → verificar-referencia cercano/lejano/ausente; estado con/sin referencia.
3. Frontend: agregar `estadoReferenciaBiometrica`, rama real de verificación, recablear el gate en `Biometria.tsx`.
4. Deploy: backend slim a Railway (el endpoint queda montado en `main_slim`), frontend a Vercel. El endpoint stateless sigue vivo → sin downtime ni breaking.
5. Rollback: revertir el deploy del frontend deja el backend con endpoints nuevos sin uso (inertes); revertir el backend no afecta enrollment (tabla intacta). Rollback independiente por capa.

## Open Questions

- ¿El umbral operativo definitivo debe venir de la config del examen (C-07) ya en este change, o se deja el default conservador 0.35? (Asumido: default 0.35 server-side; C-07 lo parametriza después.)
- ¿Conviene unificar el método del frontend (`verificarBiometria` con rama interna) o exponer `verificarBiometriaReferencia` separado? (Asumido: rama separada documentada; la decisión final es de apply, sin impacto en el contrato del backend.)
- ¿El endpoint stateless demo-only debería deprecarse formalmente (header/Sunset) o solo documentarse? (Asumido: solo documentar como demo-only en este change.)
