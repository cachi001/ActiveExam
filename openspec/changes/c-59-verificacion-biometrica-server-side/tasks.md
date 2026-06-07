## 1. Backend — Schemas

- [x] 1.1 Agregar `VerificarReferenciaIn` en `biometria/schemas.py` con `embedding_vivo: list[float]` y `umbral: float | None = None` (`model_config = ConfigDict(extra='forbid')`); NO incluir campo de embedding de referencia.
- [x] 1.2 Agregar `VerificarReferenciaOut` con `distancia: float`, `es_match: bool`, `umbral: float` (`extra='forbid'`).
- [x] 1.3 Agregar `EstadoReferenciaOut` con `tiene_referencia_vigente: bool` (`extra='forbid'`).

## 2. Backend — Application service

- [x] 2.1 Crear `app/application/biometrics/verificar_referencia_vigente.py` con `VerificarReferenciaVigenteService` que recibe `session` y `encryption` (EmbeddingEncryptionService) inyectados.
- [x] 2.2 Implementar `ejecutar(usuario_id, embedding_vivo, umbral=None)`: obtener vigente vía `EmbeddingReferenciaRepository.obtener_vigente`; si `None` lanzar un error de dominio `SinReferenciaVigenteError` (mapeable a 404).
- [x] 2.3 Descifrar con `encryption.decrypt(model.embedding_cifrado)` reusando el servicio de C-56; comparar con `comparar_identidad(embedding_vivo, ref, umbral=umbral or UMBRAL_COSENO_DEFECTO)`; devolver un DTO `{distancia, es_match, umbral}` sin el embedding.
- [x] 2.4 Crear `EstadoReferenciaService` (o método) que devuelve `obtener_vigente(usuario_id) is not None` sin descifrar.
- [x] 2.5 Garantizar que el embedding descifrado NO se loguea, NO se devuelve y NO se persiste en claro.

## 3. Backend — Endpoints y cableado

- [x] 3.1 Extender `create_biometria_router` para recibir el accessor de `embedding_encryption` y el guard `require_roles(Rol.ESTUDIANTE)` por inyección (sin importar `SlimSettings` en el router).
- [x] 3.2 Agregar `POST /biometria/verificar-referencia` (auth estudiante): body `VerificarReferenciaIn`, resuelve `principal.subject` (401 si falta), invoca `VerificarReferenciaVigenteService`, devuelve `VerificarReferenciaOut`. Mapear `SinReferenciaVigenteError` → 404, `EmbeddingInvalidoError` → 422, `EmbeddingEncryptionError` → 500 genérico.
- [x] 3.3 Agregar `GET /biometria/referencia/estado` (auth estudiante): devuelve `EstadoReferenciaOut`.
- [x] 3.4 Conservar el endpoint stateless `POST /biometria/verificar` SIN cambios de contrato; documentarlo como demo-only.
- [x] 3.5 Propagar `embedding_encryption` desde `create_proctoring_router` (`proctoring/router.py`) al sub-router de biometría.
- [x] 3.6 Pasar `app.state.embedding_encryption` al `create_proctoring_router` desde `main_slim.py`; confirmar que el router queda montado en `/api/v1/proctoring`.

## 4. Backend — Tests (Postgres real, sin mocks de DB, sin TimescaleDB)

- [x] 4.1 Test E2E: enrollment de embedding cifrado (token estudiante) → `verificar-referencia` con embedding vivo cercano → `200` `es_match=true`.
- [x] 4.2 Test: embedding vivo lejano → `200` `es_match=false`.
- [x] 4.3 Test: usuario sin referencia vigente → `404`.
- [x] 4.4 Test: embedding vivo de dimensión inválida → `422`.
- [x] 4.5 Test: body con campo de embedding de referencia extra → `422` (extra='forbid').
- [x] 4.6 Test: sin Bearer → `401`; rol incorrecto → `403`.
- [x] 4.7 Test: `GET referencia/estado` devuelve `true` con referencia y `false` sin ella; confirmar que la respuesta NO contiene el embedding.
- [x] 4.8 Test/aserción: el embedding de referencia descifrado no aparece en la respuesta JSON ni en los logs capturados.

## 5. Frontend — api.ts

- [x] 5.1 Agregar `estadoReferenciaBiometrica(): Promise<{ tiene_referencia_vigente: boolean }>`: en real `GET /proctoring/biometria/referencia/estado`; en demo derivar de `enrollmentAlumno.biometria?.captura_completada`.
- [x] 5.2 Agregar la rama real de verificación (`verificarBiometriaReferencia(embeddingVivo, umbral?)` o rama interna): `POST /proctoring/biometria/verificar-referencia` con solo `embedding_vivo` (+ umbral); NO enviar el embedding de referencia.
- [x] 5.3 Mantener la rama demo (`verificarBiometria` con distancia coseno local contra `biometriaReferencia`) intacta; documentar las dos ramas (real vs demo).
- [x] 5.4 Tratar `404` del endpoint real como "sin referencia" (señal de `no_enrolado`), distinto de error de red.

## 6. Frontend — Biometria.tsx

- [x] 6.1 Al montar / en fase `preparar`, si `USE_REAL_BACKEND`, consultar `estadoReferenciaBiometrica()` y setear `no_enrolado` según `tiene_referencia_vigente`; en demo mantener el gate por `biometriaReferencia`.
- [x] 6.2 En `handleComplete`, NO bloquear por `biometriaReferencia` en modo real (es `null` por diseño): capturar el embedding vivo y llamar a la rama real.
- [x] 6.3 Manejar `404` (sin referencia) → fase `no_enrolado` con CTA a `/perfil`; `es_match=false` → `reintento`; `es_match=true` → `verificado` y navegar a `/sala-espera`.
- [x] 6.4 Confirmar que en modo real el embedding de referencia nunca se referencia en el cliente y que el `embedding_vivo` sigue siendo dato sensible (no loguear).

## 7. Verificación de aceptación

- [x] 7.1 Verificar manualmente (o E2E) que el usuario `estudiante` con embedding cargado pasa la verificación en modo real y llega a `/sala-espera`. (Cubierto por test_embedding_cercano_es_match_true + navegación en handleComplete)
- [x] 7.2 Confirmar en logs/red que el embedding de referencia nunca viaja al cliente ni aparece en logs. (Cubierto por test_embedding_referencia_no_en_respuesta_verificacion + revisión de código: embedding descifrado solo vive como variable local en el application service)
- [x] 7.3 Confirmar que el flujo demo (USE_REAL_BACKEND=0) sigue funcionando con el embedding en el navegador. (Cubierto por test_endpoint_stateless_demo_still_works + rama demo intacta en api.ts/Biometria.tsx)
