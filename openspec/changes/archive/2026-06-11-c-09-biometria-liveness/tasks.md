# Tasks — C-09 `biometria-liveness`

> Implementa la verificación biométrica de identidad **frontend (MediaPipe) + backend (FastAPI) acoplados**: liveness híbrido + detección de cámara virtual + embedding en el cliente; re-inferencia server-side, comparación 1:1 contra referencia cifrada, clave de sesión rotativa, reintentos→escalación y custodia cifrada en el backend. El Done de cada tarea es un test verde del scope. Precondición: ConsentGate (C-08) y referencia cifrada (C-07).

## 1. Captura, liveness híbrido y detección de cámara virtual — cliente (capabilities `embedding-computation`, `liveness-detection`, `virtual-camera-detection`)

- [x] 1.1 Implementar la captura de video 3–5 s con instrucciones claras (frontend React + MediaPipe); Done: captura operativa con guía al estudiante
- [x] 1.2 Implementar el liveness pasivo: parpadeo involuntario, micro-movimientos, profundidad 3D por landmarks de Face Mesh; Done: señales pasivas calculadas
- [x] 1.3 Implementar 1–2 retos activos aleatorios; el liveness es prerrequisito (sin liveness exitoso no se compara, RN-BIO-05); Done: reto activo aleatorio + gate de liveness
- [x] 1.4 Implementar la detección de cámara virtual / inyección de pipeline (heurística de integridad, DD-18) y reportar la señal al backend; Done: señal de cámara virtual reportada
- [x] 1.5 Implementar el cálculo del embedding facial (Face Mesh) sobre el clip; Done: embedding calculado en cliente
- [x] 1.6 Tests: liveness pasa/falla, reto activo aleatorio, captura sin persona viva no pasa, cámara virtual detectada se reporta, embedding calculado sobre clip; Done: tests de cliente verdes

## 2. Custodia inicial del clip (capability `biometric-custody-encryption`)

- [x] 2.1 Hashear (SHA-256) y firmar el clip con la clave de sesión; subir directo al storage por URL firmada (RN-BIO-07, RN-CC-04); Done: clip bajo custodia inicial
- [x] 2.2 Test: el clip se sube con hash + firma por URL firmada y queda registrada la custodia inicial; Done: test de custodia del clip verde

## 3. Re-inferencia server-side y comparación 1:1 (capabilities `server-side-reinference`, `identity-match-1to1`)

- [x] 3.1 Implementar `VerifyIdentity` (backend): re-inferir sobre el clip exacto; el veredicto del cliente es señal, no verdad (RN-GLB-01); Done: re-inferencia server-side operativa
- [x] 3.2 Leer el embedding de referencia cifrado de la DB (cargado en C-07) sin exponerlo en claro al cliente; Done: lectura cifrada de la referencia
- [x] 3.3 Comparar por distancia coseno con umbral conservador (RN-BIO-03); Done: match/no-match por umbral
- [x] 3.4 Tests: backend re-infiere sobre el clip; cliente "verificado" sin coincidencia real no habilita; distancia < umbral es match, ≥ umbral no; referencia leída cifrada; Done: tests de re-inferencia y 1:1 verdes

## 4. Emisión de clave de sesión rotativa (capability `session-key-issuance`)

- [x] 4.1 Emitir la clave de sesión rotativa (HMAC) en `Sesión` solo si la comparación re-inferida es exitosa (RN-BIO-02); habilitar el examen; Done: clave emitida en verificación exitosa
- [x] 4.2 Garantizar que la clave firma los eventos/evidencia posteriores (contrato para C-10/C-12); Done: clave consumible por monitoreo
- [x] 4.3 Tests: verificación exitosa emite clave y habilita; verificación fallida no emite clave; la clave firma telemetría posterior; Done: tests de clave de sesión verdes

## 5. Reintentos y escalación a proctor (capability `retry-and-escalation`)

- [x] 5.1 Implementar el contador de reintentos (máx 2) por sesión de verificación; Done: reintentos acotados
- [x] 5.2 Al 3.º fallo: emitir evento crítico + escalar a proctor humano; NUNCA abortar ni sancionar automáticamente (RN-BIO-04, RN-GLB-02, L2.5); Done: escalación sin abort/sanción
- [x] 5.3 Tests: reintento disponible tras fallo; 3.º fallo genera evento crítico + escala a proctor; no aborta ni sanciona automáticamente; Done: tests de reintentos/escalación verdes

## 6. Persistencia cifrada del embedding (capability `biometric-custody-encryption`)

- [x] 6.1 Persistir el embedding capturado cifrado at-rest (entidad `Embedding` de C-05), finalidad acotada, marcado para eliminación al egreso (RN-BIO-07/08, RN-CO-04); Done: embedding cifrado y acotado
- [x] 6.2 Tests: embedding persistido cifrado (no en claro); finalidad acotada + marca de eliminación al egreso; Done: tests de cifrado del embedding verdes

## 7. Cierre del change

- [x] 7.1 Correr `openspec validate --strict c-09-biometria-liveness`; Done: validación estricta ✓
- [x] 7.2 Verificar contratos de salida: clave de sesión rotativa (para C-10/C-12), embedding inicial (para verificación continua US-005), evento crítico de fallo (para panel C-15), clip con custodia (para C-12); Done: contratos disponibles, desbloquea C-10
