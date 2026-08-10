## 1. Migración y modelos

- [ ] 1.1 Migración `lti_deployment_confiable` (iss, deployment_id, client_id, jwks_uri, context_id→comision_id nullable, activo)
- [ ] 1.2 Migración `lti_nonce` (nonce, state, iss, expira_en) — mismo patrón TTL que `refresh_tokens`
- [ ] 1.3 Modelo SQLAlchemy `LtiDeploymentConfiableModel` + `LtiNonceModel`
- [ ] 1.4 Generación y persistencia cifrada del par de claves RS256 del Tool (reusar mecanismo de cifrado de `moodle_credencial`)

## 2. JWKS y registro dinámico (lti-tool-provider)

- [ ] 2.1 Test: `GET /lti/jwks` devuelve un JWK Set válido con la clave pública vigente
- [ ] 2.2 Implementar `GET /lti/jwks`
- [ ] 2.3 Test: `GET /lti/dynamic-registration` devuelve la config IMS esperada (initiate_login_uri, redirect_uris, jwks_uri)
- [ ] 2.4 Implementar `GET /lti/dynamic-registration`

## 3. Login OIDC (lti-tool-provider)

- [ ] 3.1 Test: login desde deployment confiable genera state+nonce persistidos y redirige a Moodle
- [ ] 3.2 Test: login desde deployment NO confiable se rechaza sin generar state/nonce
- [ ] 3.3 Implementar `GET /lti/login` (RED→GREEN de 3.1 y 3.2)
- [ ] 3.4 Job/limpieza de nonces expirados (TTL 5 min)

## 4. Validación de launch (lti-tool-provider)

- [ ] 4.1 Test: launch con id_token válido (firma+nonce+aud+exp correctos) se acepta
- [ ] 4.2 Test: firma inválida → rechazo, sin crear/loguear usuario
- [ ] 4.3 Test: nonce reusado (replay) → rechazo
- [ ] 4.4 Test: token expirado → rechazo
- [ ] 4.5 Test: audiencia (aud) no coincide con client_id registrado → rechazo
- [ ] 4.6 Implementar `GET /lti/launch` + validación de id_token (RED→GREEN de 4.1-4.5)

## 5. JIT provisioning (lti-jit-provisioning)

- [ ] 5.1 Test: primer launch de un sub nuevo crea usuario con roles=["alumno"], auth_provider="lti", debe_cambiar_password=true, datos SOLO del id_token
- [ ] 5.2 Test: segundo launch del mismo sub NO duplica la cuenta, reusa la existente
- [ ] 5.3 Test: el JIT ignora cualquier dato de identidad que no venga del id_token validado (intento de inyección vía query param adicional)
- [ ] 5.4 Implementar servicio de JIT provisioning (RED→GREEN de 5.1-5.3)
- [ ] 5.5 Test: tras JIT/login exitoso se emite JWT de sesión propio (mismo emisor que /auth/login) sin pedir password
- [ ] 5.6 Implementar emisión de sesión + redirect al frontend con el token
- [ ] 5.7 Test: context_id con mapeo configurado matricula al alumno en la comisión mapeada
- [ ] 5.8 Test: context_id sin mapeo crea/loguea igual pero sin matricular
- [ ] 5.9 Implementar resolución de mapeo context_id→comision_id (RED→GREEN de 5.7-5.8)

## 6. Allowlist admin (lti-trust-config)

- [ ] 6.1 Test: tabla vacía rechaza cualquier login/launch (falla cerrado)
- [ ] 6.2 Test: admin_sistema puede crear/editar/borrar filas de lti_deployment_confiable
- [ ] 6.3 Test: usuario sin rol admin_sistema recibe 403 al intentar gestionar el allowlist
- [ ] 6.4 Implementar endpoints CRUD admin-only para `lti_deployment_confiable` (RED→GREEN de 6.1-6.3)

## 7. Frontend

- [ ] 7.1 Landing que recibe access_token/refresh_token por redirect post-launch y los persiste (mismo mecanismo que login normal)
- [ ] 7.2 Verificar que el dashboard alumno muestra el aviso de "fijá tu contraseña" para debe_cambiar_password=true (ya existente — solo confirmar que el flujo LTI lo dispara igual)

## 8. Prueba en vivo contra campustest (ZZ Test)

- [ ] 8.1 Exponer el backend local vía `cloudflared` (URL HTTPS temporal)
- [ ] 8.2 Registrar ActiveExam como herramienta externa en campustest (registro dinámico) — admin `emiliano_caceres`
- [ ] 8.3 Dar de alta el deployment resultante en `lti_deployment_confiable` (con mapeo a materia/comisión de prueba)
- [ ] 8.4 Agregar la actividad "Herramienta externa" en el curso ZZ Test
- [ ] 8.5 Probar el flujo end-to-end como alumno: clic en Moodle → cuenta creada → dashboard → fijar contraseña — capturas de cada paso
- [ ] 8.6 Documentar resultado (éxito/hallazgos) y decidir si el túnel se reemplaza por un deploy real más adelante

## 9. Gobernanza y cierre

- [ ] 9.1 Revisión de seguridad del endpoint público antes de considerar el change listo para algo más que `ZZ Test` (dominio CRÍTICO — Auth)
- [ ] 9.2 `openspec archive` una vez todas las tasks estén en verde y la prueba en vivo (sección 8) esté documentada
