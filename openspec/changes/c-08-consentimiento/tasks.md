# Tasks — C-08 `consentimiento`

> Implementa el consentimiento informado (base legal del tratamiento biométrico, Ley 25.326) como gate previo a C-09: pantalla dedicada, captura por acción afirmativa, acuse inmutable con hash, y vía alternativa sin biometría. El Done de cada tarea es un test verde del scope. El contenido legal del texto deriva de C-01.

## 1. Pantalla dedicada de consentimiento (capability `informed-consent-presentation`)

- [x] 1.1 Implementar la pantalla de consentimiento (frontend React) con lenguaje claro: qué/cómo/dónde/cuánto/derechos del titular; texto versionado derivado del marco de C-01; Done: `frontend/src/features/consentimiento/ConsentScreen.tsx` (cinco bloques + versión)
- [x] 1.2 Exponer el texto versionado vigente desde el backend (por examen) para que la pantalla lo muestre y el acuse lo referencie; Done: `GET /api/v1/consent/text` + `domain/consent_flow/text_catalog.py` (versionado + hash del texto)
- [x] 1.3 Tests: la pantalla muestra los cinco bloques informativos y la versión vigente; el acuse referencia esa versión; Done: `test_get_text_cinco_bloques`, `test_texto_vigente_tiene_cinco_bloques`; el acuse referencia la versión (`record_consent` usa `texto.version`)

## 2. Captura por acción afirmativa (capability `affirmative-consent-capture`)

- [x] 2.1 Implementar la acción afirmativa explícita en la UI, sin casillas premarcadas ni consentimiento por defecto; Done: `ConsentScreen.tsx` — checkbox con estado inicial `false`, botón "Acepto" deshabilitado hasta marcar
- [x] 2.2 Implementar `RecordConsent` (application) con validación server-side de la acción afirmativa → 422 si falta (el cliente es sensor no confiable, RN-GLB-01); Done: `domain/consent_flow/rules.validar_accion_afirmativa` + `application/consent/service.record_consent`
- [x] 2.3 Tests: consentimiento con acción afirmativa aceptado; registro sin acción afirmativa rechazado (422); sin casillas premarcadas; Done: `test_consent_con_accion_afirmativa_201`, `test_consent_sin_accion_afirmativa_422`, `test_record_consent_sin_accion_afirmativa_no_persiste`

## 3. Acuse inmutable con hash (capability `immutable-consent-record`)

- [x] 3.1 Implementar la persistencia de `Consentimiento{user_id, exam_id, versión_texto, timestamp, hash}` sobre la entidad inmutable de C-05; calcular hash del texto exacto + acuse; Done: `record_consent` + `rules.hash_acuse` (sella `texto.hash_texto()` + acuse)
- [x] 3.2 Garantizar inmutabilidad: el repositorio/entidad rechaza UPDATE y DELETE (consistente con el patrón inmutable del proyecto); Done: `ConsentRepository` (C-05) no expone update/delete (puerto) + trigger anti-UPDATE/DELETE de la migración 002 (C-05); `test_consent_repo_no_expone_update_ni_delete`
- [x] 3.3 Tests: acuse con timestamp+hash; UPDATE rechazado; DELETE rechazado; hash verifica el texto exacto consentido; Done: `test_record_consent_persiste_con_hash`, `test_hash_acuse_sella_texto_exacto`; el rechazo de UPDATE/DELETE en motor lo cubre `test_db_invariants.py` (`@requires_stack`, trigger de C-05)

## 4. Vía alternativa sin biometría (capability `no-biometric-alternative-path`)

- [x] 4.1 Implementar `ChooseAlternativeVerification`: registrar la elección de la vía alternativa y escalar a proctor humano (RN-CO-05); Done: `service.choose_alternative` — traza inmutable en audit log + `enqueue` a `consent.alternative.proctor` (cola = puerto `MessageQueuePort`; el transporte concreto es C-10)
- [x] 4.2 Garantizar que no consentir NO aborta el examen (RN-GLB-02): se ofrece la vía alternativa; Done: `choose_alternative` no lanza ni bloquea; `ConsentScreen.tsx` muestra el botón de vía alternativa; el gate avanza con `VIA_ALTERNATIVA`
- [x] 4.3 Tests: no consentir ofrece la alternativa; la elección escala a proctor; la falta de consentimiento no aborta; Done: `test_choose_alternative_audita_y_escala_sin_abortar`, `test_alternativa_escala_sin_abortar`, `test_gate_con_alternativa_avanza_sin_biometria`

## 5. Gate de consentimiento previo a la biometría (capability `consent-gate`)

- [x] 5.1 Implementar `ConsentGate` consumible por C-09: habilita biometría solo con consentimiento válido o vía alternativa elegida (D4, DD-03); Done: `service.evaluate_gate`/`resolve`/`biometria_habilitada` + `rules.evaluar_gate` + `GET /api/v1/consent/gate`
- [x] 5.2 Tests: con consentimiento válido se habilita biometría; sin consentimiento ni alternativa no se habilita; con vía alternativa no se exige biometría; Done: `test_gate_con_consentimiento_habilita_biometria`, `test_gate_sin_resolucion_bloquea_biometria`, `test_gate_con_alternativa_avanza_sin_biometria`, `test_gate_flujo_completo`

## 6. Cierre del change

- [x] 6.1 Correr `openspec validate --strict c-08-consentimiento`; Done: validación estricta ✓
- [x] 6.2 Verificar que el gate de consentimiento es consumible por C-09 (precondición legal de la captura biométrica); Done: `ConsentService.evaluate_gate`/`biometria_habilitada` (contrato de salida), desbloquea C-09
