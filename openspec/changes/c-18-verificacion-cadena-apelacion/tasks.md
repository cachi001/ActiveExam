# Tasks — C-18 `verificacion-cadena-apelacion`

> Backend FastAPI, Clean/Hexagonal. Solo lectura sobre evidencia WORM. TDD.

## 1. Endpoint y verificación por etapas (capability `evidence-chain-verification`)

- [ ] 1.1 Definir el adaptador HTTP `POST /api/v1/evidence/{id}/verify-chain` y el caso de uso `VerifyChainUseCase`; Done: endpoint resuelve la evidencia por id y responde 404 si no existe
- [ ] 1.2 Verificar etapa 1 (cliente): `hash_cliente` + `firma_cliente` HMAC con la clave de sesión cuando esté disponible; Done: estado de etapa 1 reportado (verificada / material no disponible)
- [ ] 1.3 Verificar etapa 2 (backend): recalcular `hash_backend` y validar la firma del backend; Done: estado de etapa 2 reportado
- [ ] 1.4 Verificar etapa 3 (worker/clave maestra): validar `firma_maestra` contra la clave pública maestra (RSA-2048 / Ed25519); Done: estado de etapa 3 reportado
- [ ] 1.5 Verificar etapa 4 (re-inferencia): validar la coherencia del `output_reinferencia` firmado sobre el clip; Done: estado de etapa 4 reportado
- [ ] 1.6 Emitir el certificado de verificación con el resultado por etapa y el veredicto global; Done: certificado con 4 etapas + veredicto
- [ ] 1.7 Garantizar que la verificación es de SOLO LECTURA y no muta la evidencia (WORM); Done: la evidencia y su cadena permanecen intactas tras verificar

## 2. Verificación independiente por perito (capability `independent-expert-verification`)

- [ ] 2.1 Incluir en el certificado, por etapa, el hash, la firma, el algoritmo y la clave pública necesaria (maestra para etapa 3) e identificadores de la evidencia; Done: certificado autoportante
- [ ] 2.2 Garantizar que un perito puede recomputar hashes y verificar las firmas con herramientas estándar SIN llamar a la API; Done: verificación independiente reproducible con la clave pública
- [ ] 2.3 Asegurar que el certificado NO contiene el contenido del clip ni PII (solo hashes/firmas/claves públicas); Done: certificado sin PII

## 3. Detección de cadena rota (capability `broken-chain-detection`)

- [ ] 3.1 Detectar discrepancia de hash o firma inválida en cualquier etapa (RN-CC-03); Done: la etapa de ruptura se identifica
- [ ] 3.2 Declarar en el certificado que la cadena está rota y que la evidencia NO se sostiene; Done: veredicto = no sostenida cuando hay ruptura
- [ ] 3.3 Registrar la cadena rota en el audit log append-only; Done: el hecho queda registrado y encadenado

## 4. Trazabilidad de la verificación

- [ ] 4.1 Registrar cada invocación de `verify-chain` en el audit log (actor, propósito=apelación, evidencia_id, timestamp, resultado), encadenada por hash; Done: cada verificación deja rastro
- [ ] 4.2 Documentar que `verify-chain` informa al proceso humano y NUNCA sanciona ni decide automáticamente (L2.5); Done: nota en el contrato del endpoint

## 5. Tests

- [ ] 5.1 Test: certificado válido — cadena íntegra produce certificado con las 4 etapas verificadas y veredicto sostenido; Done: test verde
- [ ] 5.2 Test: detección de cadena rota — hash/firma alterados en una etapa producen veredicto "no sostenida" y registro en audit log; Done: test verde
- [ ] 5.3 Test: verificación independiente — un verificador externo valida las firmas del certificado con la clave pública maestra, sin la API; Done: test verde
- [ ] 5.4 Test: la verificación es de solo lectura — la evidencia y la cadena no se modifican; Done: test verde
- [ ] 5.5 Test: el certificado no contiene PII ni el contenido del clip; Done: test verde
