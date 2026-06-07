## 1. Fix bug bloqueante — examenActivo null (D1)

- [x] 1.1 En `frontend/src/screens/AlumnoMisExamenes.tsx`, importar `setExamenActivo` desde el store (`useApp`) y resolver el `Examen` en `handleRendir` antes de `navigate('/requisitos')`.
- [x] 1.2 Obtener el examen con `await api.getExam(inscripcion.examen_id)`; si retorna `undefined`, construir un `Examen` mínimo desde la `Inscripcion` (id, nombre desde `nombre_examen`, `estado: 'en_curso'`, defaults seguros para el resto) y llamar `setExamenActivo(examen)`.
- [x] 1.3 Verificar el flujo completo: "Rendir" → `/requisitos` → `/consentimiento`, que `examenActivo` ya no sea null y que `Consent.aceptar()` avance a `/biometria`.
- [x] 1.4 Mantener el guard defensivo `if (!acepto || !examen) return;` en `Consent.tsx` (caso deep-link directo), sin que dispare en el flujo normal.

## 2. Consentimiento del examen liviano (D2)

- [x] 2.1 En `frontend/src/screens/Consent.tsx`, cargar el estado de enrollment (`api.getEnrollment()`) además del texto, para conocer `estado.consentimiento` (acuse de perfil).
- [x] 2.2 Derivar `yaConsintioPerfil = consentimiento != null && (consentimiento.via_alternativa || consentimiento.version === texto.version)`.
- [x] 2.3 Si `yaConsintioPerfil`: renderizar la rama liviana — tarjeta corta con la fecha del acuse de perfil + casilla afirmativa NO pre-marcada ("Confirmo que acepto ser supervisado en esta evaluación") + botón "Confirmar y continuar".
- [x] 2.4 Si NO `yaConsintioPerfil`: renderizar el consentimiento completo (bloques + texto) como hoy.
- [x] 2.5 En ambas ramas, al confirmar, llamar `await api.recordConsent(examen.id)` y navegar a `/biometria` (preservar acuse por-rendición, RN-CC).
- [x] 2.6 (Open question) Agregar enlace discreto "ver texto completo" en la rama liviana si el dueño lo confirma; sin bloquear el 1 click.

## 3. Consentimiento sin spinner intermedio (D3)

- [x] 3.1 En `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx`, eliminar el estado `cargandoTexto` y la rama `if (cargandoTexto) return <spinner/>`; renderizar el layout de una y dejar que los bloques salgan de `texto?.bloques ?? []`.
- [x] 3.2 En `frontend/src/screens/Consent.tsx`, reemplazar el texto inline "Cargando texto de consentimiento…" (grilla vacía) por render progresivo sin jerga de carga.
- [x] 3.3 Verificar que no haya salto de layout disruptivo durante el fetch (~300ms) en ambas pantallas.

## 4. Liveness — limpieza visual (D4)

- [x] 4.1 En `frontend/src/ui/biometric/CaptureProgress.tsx`, eliminar el bloque `{!enExito && !cooldownActivo && turnDirection && (...)}` (flecha `←`/`→` + texto direccional).
- [x] 4.2 En `frontend/src/ui/biometric/CaptureOverlay.tsx`, eliminar el `<p>` con `contextLabel` de la barra superior y alinear el botón "Cancelar" a la derecha.
- [x] 4.3 Grep de los callers de `turnDirection` y `contextLabel` (p. ej. `BiometricCapture`); si ningún consumidor las usa con sentido, eliminar las props de `CaptureProgressProps`/`CaptureOverlayProps` y actualizar el caller en el mismo paso. Si hay duda, eliminar solo el render.
- [x] 4.4 Verificar que la detección de giro y el resto de la captura siguen funcionando sin cambios.

## 5. Login — toggle de contraseña + inputs del sistema (D5)

- [x] 5.1 En `frontend/src/screens/Login.tsx` (`FormularioJwt`), agregar estado `verPassword` y cambiar el input a `type={verPassword ? 'text' : 'password'}`.
- [x] 5.2 Agregar botón de ojo dentro del campo (contenedor `relative`, botón `absolute` a la derecha), `type="button"`, `aria-label` "Mostrar/Ocultar contraseña", con `<Icon name="visibility" />` / `visibility_off` según el estado.
- [x] 5.3 Migrar los campos usuario y contraseña a `FormField` (de `ui/components.tsx`) + clase global `.input` (de `index.css`), reemplazando las clases hardcodeadas inline.
- [x] 5.4 Preservar accesibilidad: `id`/`htmlFor`, `autoComplete` (`username` / `current-password`), `required`, `disabled={loading}`.
- [x] 5.5 Confirmar que `SelectorRolDemo` y `LoginKeycloak` no se tocan (no tienen inputs de texto).

## 6. Mis Exámenes — responsive (D6)

- [x] 6.1 En `frontend/src/screens/alumno/components/InscripcionCard.tsx`, hacer responsive la fila principal (badge que pueda bajar en mobile) y agregar `truncate`/`line-clamp` a `nombre_examen` y `nombre_materia`.
- [x] 6.2 En la fila de acción de `InscripcionCard`, pasar a `flex-col sm:flex-row` para que el `<p>` de razón y el `Button` no compriman en pantallas chicas.
- [x] 6.3 En `frontend/src/screens/alumno/components/ExamenCard.tsx`, pasar el `Card` a `flex-col sm:flex-row`, agregar `min-w-0`/`truncate` al nombre y `flex-wrap`/`shrink-0` al cluster de badge + botón.
- [x] 6.4 Verificar a 360px de ancho que ningún texto ni control se desborde en ambas tarjetas; nombres largos truncan con elipsis.

## 7. Verificación final

- [x] 7.1 Revisar que se respeten las reglas duras: PascalCase en componentes, sin backend nuevo, sin migraciones, ambos consentimientos conservados, acuse por-rendición intacto (RN-CC), casillas nunca pre-marcadas (RN-CO-02).
- [x] 7.2 Confirmar que NO se incluyó nada de gestión de usuarios (alcance de C-59).
- [x] 7.3 No buildear ni commitear sin pedido explícito del usuario.
