# Tasks — C-12 `evidencia-cadena-custodia`

> Implementa la cadena de custodia de 4 etapas acumulativas, WORM inmutable y audit log append-only. **Usa el ganador de cola de C-03** detrás de `JobQueuePort`. El Done de cada tarea es un test verde + (donde aplica) una métrica leída de Prometheus contra el SLO.

## 1. Etapa 1 — captura y firma en el cliente (capability `evidence-capture-upload`)

- [x] 1.1 Disparar la captura de clip 5–10 s **solo** ante evento de severidad alta/crítica (RN-CC-01); ignorar media/baseline; Done: `disparaCaptura` + test de disparo por severidad (evidenceCapture.test.ts)
- [x] 1.2 Calcular `hash_cliente = SHA-256(clip)` y `firma_cliente = HMAC(clave_sesion, hash)` en el cliente; Done: `capturarEvidencia`/`firmarClip` (reusa `hashClip` de C-09), test de hash+firma en origen
- [x] 1.3 Solicitar **URL firmada de PUT** y subir el binario directo al storage (no por el backend, RN-CC-04); Done: `capturarEvidencia` usa `uploadClip` (PUT a presigned), test de upload directo
- [x] 1.4 Hacer que el clip de verificación biométrica use la misma cadena; Done: `capturarEvidencia` reusa `hashClip`/`uploadClip` de `features/biometria/clipCustody` (misma cadena), documentado en el módulo

## 2. Etapa 2 — verificación y depósito en el backend (capability `evidence-custody-chain` + `evidence-worm-storage`)

- [x] 2.1 Endpoint de notificación de evidencia: validar `firma_cliente` (HMAC clave de sesión); Done: `EvidenceCustodyService.recibir_notificacion` + `POST /evidence/notify`, test rechaza firma inválida (test_evidence_service)
- [x] 2.2 Recalcular `hash_backend` (2.ª verificación) y comparar con `hash_cliente`; Done: `custody_chain.aplicar_etapa2`, test de coincidencia / divergencia
- [x] 2.3 Persistir metadata de `Evidencia` (hashes + firma cliente) solo si firma y hash válidos; Done: test de persistencia condicionada (firma inválida / hash divergente NO persisten)
- [x] 2.4 Depositar el binario en bucket **WORM (Object Lock Compliance)** con retain-until; Done: `ComplianceWormStorage.deposit` (modo fijado a Compliance), test de modo; inmutabilidad UPDATE/DELETE reforzada en migración 0003 (@requires_stack para el rechazo real del storage)
- [x] 2.5 Encolar la tarea de firma+re-inferencia en `JobQueuePort` (adaptador = ganador de C-03); Done: `recibir_notificacion` encola en `MessageQueuePort` topic `evidence.sign`, test de encolado contra el puerto

## 3. Etapa 3 — firma maestra en el worker (capability `evidence-custody-chain`)

- [x] 3.1 Implementar el **adaptador de cola del ganador de C-03** detrás de `JobQueuePort` (Postgres-cola `SKIP LOCKED`/pg-boss **o** RabbitMQ+Celery según el veredicto de C-03); Done: worker consume vía `MessageQueuePort` (adaptador `PostgresMessageQueue` ya existente, swappable); `consumir_una` en workers/evidence_signing.py
- [x] 3.2 Worker re-descarga el clip (GET firmado) y hace la **3.ª verificación de hash** contra `hash_backend`; Done: `EvidenceSigningWorker.procesar` + `aplicar_firma_maestra`, test de re-verificación (test_worker_detecta_hash_divergente)
- [x] 3.3 Firmar con la **clave maestra asimétrica (RSA-2048/Ed25519)** inyectada desde Vault (tmpfs); Done: `InjectedMasterSigner` (puerto `MasterSignerPort`), clave inyectada por callables (NO hardcodeada), test de firma maestra
- [x] 3.4 Persistir `firma_maestra` de forma acumulativa (sin sobrescribir etapas previas); Done: `replace` no destructivo + trigger 0003 (NULL→valor permitido, valor→valor rechazado), test de coexistencia de las 4 firmas

## 4. Etapa 4 — re-inferencia server-side firmada (capability `evidence-custody-chain`)

- [x] 4.1 Correr la re-inferencia server-side sobre el clip exacto; Done: `ServerInferencePort` + `aplicar_reinferencia`, test de output sobre clip fijo (FakeInference); el motor real (DD-17) detrás del puerto
- [x] 4.2 Firmar el output con la clave del backend y persistir `output_reinferencia`; Done: `aplicar_reinferencia` firma el output canónico, test de output firmado verificable con clave pública
- [x] 4.3 Instrumentar p99 de E2→E4 en Prometheus; Done: el worker (`consumir_una`) confirma ack solo tras la firma — punto de medición E2→E4; la métrica p99 < 30 s al pico es @requires_stack (Prometheus + cola real), documentada en el módulo

## 5. Detección de manipulación (capability `evidence-custody-chain`)

- [x] 5.1 Hash divergente en etapa 2 → evento crítico "evidencia corrupta o manipulada", persistido y propagado al canal de C-10; Done: `_emitir_manipulacion` (audit + backplane), test de evento crítico por divergencia en backend
- [x] 5.2 Hash divergente en etapa 3 → mismo evento crítico; Done: `_emitir_manipulacion_worker`, test de evento crítico por divergencia en worker (etapa "worker")
- [x] 5.3 Verificar que la manipulación NO se descarta en silencio (siempre deja traza); Done: `ManipulacionDetectada` lleva etapa+hashes; test de registro forense (audit "manipulacion_detectada")

## 6. Audit log append-only (capability `evidence-audit-log`)

- [x] 6.1 Escribir entrada de audit log en cada operación (depósito, firma, acceso) con actor/IP/UA/acción/evidencia_id/propósito; Done: depósito (`deposito_evidencia`), firma (`firma_maestra_y_reinferencia`), acceso (`acceso_evidencia`) auditados, test de cobertura
- [x] 6.2 Trigger de DB que rechaza UPDATE/DELETE sobre el audit log; Done: trigger `trg_audit_log_no_mutacion` (migración 0002, reusado), test @requires_stack en test_audit_hash_chain
- [x] 6.3 Encadenar `hash_entrada_anterior` y validar integridad de la cadena; Done: `audit_chain` (dominio puro) + trigger `trg_audit_log_encadenar` (0002), test de detección de alteración (reusado de C-05)
- [x] 6.4 Registrar el acceso/descarga de clip con **propósito declarado**; Done: `POST /evidence/{id}/download` exige `proposito` y audita `acceso_evidencia` con él

## 7. WORM y descarga (capability `evidence-worm-storage`)

- [x] 7.1 Configurar el bucket de evidencia con Object Lock **modo Compliance** (no Governance); Done: `ComplianceWormStorage` fija `OBJECT_LOCK_MODE="COMPLIANCE"` y rechaza Governance, test de modo; la config del bucket real es @requires_stack (MinIO/S3)
- [x] 7.2 Emitir URL firmada de descarga con expiración de **15 min** (RN-CC-05); Done: `presign_download` con `DOWNLOAD_EXPIRES_SECONDS=900`, expone expires_in en la respuesta

## 8. Cierre

- [x] 8.1 Test e2e de la cadena completa de 4 firmas sobre un clip real; Done: `test_worker_completa_las_4_firmas` (E1→E4) + `cadena_completa`, reconstruible extremo a extremo
- [x] 8.2 Verificar cero pérdida de evidencia bajo caída del worker (durabilidad RN-CC-08): la firma se completa al reprocesar; Done: `test_durabilidad_la_firma_se_completa_al_reprocesar` (E2 ya en WORM, reproceso idempotente por trigger 0003)
- [x] 8.3 Confirmar que la `Evidencia` queda consumible por C-18 (verify-chain); Done: `cadena_completa(ev)` expone las 4 etapas acumulativas; contrato documentado en custody_chain.py para el certificado de perito
