# Tasks — c-24-evidencia-screenshots

## 1. screenshot-evidence-capture (cliente)

- [ ] 1.1 Reemplazar la captura de clip (`MediaRecorder`) por captura de **frame único** (canvas / `ImageCapture`) en el cliente. **Done**: ante un disparador, el cliente produce una imagen (no un binario de video).
- [ ] 1.2 Calcular `hash_cliente = SHA-256(screenshot)` y `firma_cliente = HMAC(clave_sesion, hash_cliente)` sobre la imagen. **Done**: la notificación de evidencia incluye hash y firma del screenshot.
- [ ] 1.3 Subir el screenshot **directo al storage por URL firmada de PUT**, sin que el binario pase por el backend. **Done**: el binario aparece en storage vía presigned URL; el backend solo recibió metadata + hash + firma.
- [ ] 1.4 Garantizar que el cliente **no graba video continuo** en ningún punto de la sesión. **Done**: revisión de código confirma ausencia de grabación de video.

## 2. evidence-capture-cadence (disparadores + config)

- [ ] 2.1 Implementar el disparador **event-driven**: capturar screenshot en el instante de un evento de severidad alta/crítica; ignorar media/baseline. **Done**: un evento severo produce exactamente un screenshot; uno no severo, ninguno.
- [ ] 2.2 Implementar el **heartbeat** periódico de baja frecuencia (línea base) siguiendo la cadena de custodia. **Done**: con heartbeat activo, se capturan screenshots al intervalo configurado.
- [ ] 2.3 Añadir configuración de cadencia **por examen** (frecuencia de heartbeat, on/off) con default conservador y tope máximo. **Done**: un examen puede ajustar/desactivar el heartbeat dentro del tope; sin config se aplica el default.
- [ ] 2.4 Validar proporcionalidad: el tope máximo impide configurar frecuencias que violen la minimización. **Done**: configurar por encima del tope es rechazado.

## 3. evidence-capture-upload (re-inferencia server-side estática)

- [ ] 3.1 Adaptar el worker de re-inferencia de pipeline temporal (clip) a **pipeline de imagen estática** (detección sobre el frame). **Done**: el worker re-infiere sobre la imagen y produce labels/confidences del frame.
- [ ] 3.2 Mantener la **cadena de custodia server-side** sobre el nuevo binario: backend valida firma + recalcula hash + audit log + WORM cifrado; worker hace 3.ª verificación de hash + firma con clave maestra. **Done**: el screenshot recorre las 3 etapas server-side y queda en bucket WORM con firma de clave maestra.
- [ ] 3.3 Comparar la re-inferencia estática con lo reportado por el cliente y registrar discrepancias como señal forense. **Done**: una discrepancia queda registrada y firmada sobre el frame; no dispara sanción automática.

## 4. Documentación y consistencia de KB

- [ ] 4.1 Reflejar en `05_reglas_de_negocio.md` que RN-CC-01 produce **screenshot** (no clip). **Done**: RN-CC-01 actualizada (vía change posterior de KB o nota de impacto).
- [ ] 4.2 Reflejar en `07_flujos_principales.md` §EVIDENCIA el paso "screenshot" en lugar de "clip 5-10s". **Done**: el flujo documenta screenshot.
- [ ] 4.3 Actualizar el **modelo de costo** en `14_observabilidad_y_devops.md`: volumen de evidencia por examen pasa de ~2,8 GB a unos pocos MB. **Done**: la sección de capacity refleja el nuevo orden de magnitud.
- [ ] 4.4 Documentar para revisores humanos (c-02) el **límite L2.5**: la evidencia es un frame, sin contexto temporal. **Done**: material de revisores incluye la limitación y cuándo escalar.
