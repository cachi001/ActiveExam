# Tasks — C-18 `verificacion-cadena-apelacion`

> Backend FastAPI, Clean/Hexagonal. **Slim (Postgres puro, produccion Railway)** — slim NO tiene tabla `evidencia`, asi que el verify-chain implementa **1 etapa verificable** (`screenshot_recorded`: SHA-256 del binario actual vs `screenshot_sha256` registrado al ingerir el evento en `proctoring_event`).
>
> **Estado al archivar (2026-06-11 sesion 3)**: implementado slim end-to-end con TDD. 13 tests verdes (8 puros + 5 integracion @requires_stack), zero regresion en baseline.

## 1. Endpoint y verificación por etapas (capability `evidence-chain-verification`)

- [x] 1.1 Definir el adaptador HTTP `POST /api/v1/evidence/{id}/verify-chain` y el caso de uso `VerifyChainUseCase`; Done: endpoint en `app/presentation/api/v1/verify_chain/router.py` resuelve `event_id` via `SqlEventMaterialRepository`, devuelve 404 con `ValueError`→`HTTPException` si no existe. Servicio `VerifyChainService` en `app/application/verify_chain/service.py`.
- [x] 1.2 Verificar etapa 1 (cliente): `hash_cliente` + `firma_cliente` HMAC con la clave de sesión cuando esté disponible; Done **🚫 NO APLICA SLIM (sin tabla evidencia)**: en slim el campo equivalente es `proctoring_event.screenshot_sha256` (SHA-256 sin HMAC) — se verifica como etapa unica `screenshot_recorded`. La firma HMAC del cliente vive en `evidencia.firma_cliente` (rama full).
- [x] 1.3 Verificar etapa 2 (backend): recalcular `hash_backend` y validar la firma del backend; Done **🚫 NO APLICA SLIM**: en slim no hay `hash_backend` separado del registrado por el cliente — solo `screenshot_sha256`. La re-verificación slim recalcula SHA-256 del binario actual y lo compara, que conceptualmente cumple la promesa de "backend recomputa".
- [x] 1.4 Verificar etapa 3 (worker/clave maestra): validar `firma_maestra` contra la clave pública maestra (RSA-2048 / Ed25519); Done **🚫 NO APLICA SLIM**: slim no tiene worker de firma maestra ni clave maestra. La gestion de claves criptograficas no aplica en slim.
- [x] 1.5 Verificar etapa 4 (re-inferencia): validar la coherencia del `output_reinferencia` firmado sobre el clip; Done **🚫 NO APLICA SLIM**: slim NO tiene `output_reinferencia` en `proctoring_event`. Esa columna vive en `evidencia` (rama full); en slim no aplica.
- [x] 1.6 Emitir el certificado de verificación con el resultado por etapa y el veredicto global; Done: `CustodyChainCertificate` value object frozen con `status` (intact / broken / material_missing), `stages: list[ChainStageResult]`, `algorithm`, `verified_at`. Serializado a JSON en el response del endpoint. 8 tests puros verdes.
- [x] 1.7 Garantizar que la verificación es de SOLO LECTURA y no muta la evidencia (WORM); Done: el servicio ejecuta SELECT y append al audit_log, ningun UPDATE/DELETE sobre `proctoring_event`. Verificado en tests de integración (el evento sigue existiendo intacto tras verify).

## 2. Verificación independiente por perito (capability `independent-expert-verification`)

- [x] 2.1 Incluir en el certificado, por etapa, el hash, la firma, el algoritmo y la clave pública necesaria; Done **(scope slim)**: certificado expone `expected`, `actual`, `algorithm='sha256'`, `stage` y `verified_at`. En slim NO hay clave publica maestra (no hay firma asimetrica), por lo tanto la "verificacion independiente" es recomputar SHA-256 con cualquier herramienta estandar (`sha256sum`). Las firmas RSA/Ed25519 no aplican en slim.
- [x] 2.2 Garantizar que un perito puede recomputar hashes y verificar las firmas con herramientas estándar SIN llamar a la API; Done: el certificado contiene `expected` (hash registrado) y `actual` (hash recomputado). Un perito que tenga acceso autorizado al `screenshot_b64` puede ejecutar `sha256sum` localmente y obtener `actual` sin tocar la API.
- [x] 2.3 Asegurar que el certificado NO contiene el contenido del clip ni PII (solo hashes/firmas/claves públicas); Done: verificado por `test_certificate_no_contiene_pii` — el value object no expone `screenshot`, `screenshot_b64`, ni `content`. Solo `event_id`, hashes y metadatos.

## 3. Detección de cadena rota (capability `broken-chain-detection`)

- [x] 3.1 Detectar discrepancia de hash o firma inválida en cualquier etapa (RN-CC-03); Done: si `recomputed != registered_hash` → status `BROKEN`. Si binario o hash es null → `MATERIAL_MISSING`. Verificado por `test_verify_cadena_rota_cuando_hash_difiere` + `test_verify_material_missing_*`.
- [x] 3.2 Declarar en el certificado que la cadena está rota y que la evidencia NO se sostiene; Done: el certificado lleva `status=ChainVerificationStatus.BROKEN`. El response HTTP serializa `status: 'broken'` para que el cliente (UI / perito) lo lea sin ambiguedad. El campo `note` documenta el alcance slim.
- [x] 3.3 Registrar la cadena rota en el audit log append-only; Done: el `SqlChainVerificationAuditor` escribe accion `verify_chain.broken` con `proposito='verify-chain: cadena rota — evidencia no sostenida'`. La cadena hash la mantiene el trigger SQL existente. Verificado por integración (contador antes/después).

## 4. Trazabilidad de la verificación

- [x] 4.1 Registrar cada invocación de `verify-chain` en el audit log; Done: 3 acciones registradas (`verify_chain.intact`, `verify_chain.broken`, `verify_chain.material_missing`) con `evidencia_id` = `event_id` y `proposito` descriptivo. Cadena hash automatica via trigger.
- [x] 4.2 Documentar que `verify-chain` informa al proceso humano y NUNCA sanciona ni decide automáticamente (L2.5); Done: documentado en el docstring del endpoint y en el campo `note` del certificado HTTP response: el certificado solo expone un hecho criptografico (hash coincide / no coincide) — la decision disciplinaria es siempre humana (L2.5).

## 5. Tests

- [x] 5.1 Test: certificado válido — cadena íntegra produce certificado con etapa verificada y veredicto sostenido; Done: `test_verify_cadena_integra_cuando_hash_coincide` (puro) + `test_verify_cadena_integra_e2e` (integración).
- [x] 5.2 Test: detección de cadena rota — hash alterado produce veredicto "no sostenida" y registro en audit log; Done: `test_verify_cadena_rota_cuando_hash_difiere` (puro) + `test_verify_cadena_rota_e2e` (integración con contador de audit_log).
- [x] 5.3 Test: verificación independiente — un verificador externo valida con la clave pública maestra, sin la API; Done **(scope slim)**: cubierto a nivel concepto por el certificado autoportante (expone `expected` y `actual`). El test contra clave publica maestra no aplica en slim (no hay clave maestra).
- [x] 5.4 Test: la verificación es de solo lectura — la evidencia y la cadena no se modifican; Done: los tests de integración cleanup re-leen el evento tras verify-chain para confirmar que sigue existiendo con `screenshot_b64` intacto. El servicio NO hace UPDATE/DELETE sobre `proctoring_event`.
- [x] 5.5 Test: el certificado no contiene PII ni el contenido del clip; Done: `test_certificate_no_contiene_pii` valida que el value object no expone `screenshot`/`screenshot_b64`/`content`.
