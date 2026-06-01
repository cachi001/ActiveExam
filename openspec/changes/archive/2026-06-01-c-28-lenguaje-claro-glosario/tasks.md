## 1. Módulo de glosario central

- [x] 1.1 Crear `frontend/src/config/glossary.ts` con el tipo `TermKey` (union literal de 7 claves: `l2_5`, `embedding`, `worm`, `liveness`, `cadena_de_custodia`, `face_mesh`, `datos_biometricos`)
- [x] 1.2 Definir la interfaz `GlossaryEntry` con campos `label: string`, `definition: string`, `legalRef?: string`
- [x] 1.3 Implementar el objeto `GLOSSARY: Record<TermKey, GlossaryEntry>` con la entrada `l2_5` (definición: el sistema nunca sanciona automáticamente; decisión disciplinaria siempre humana)
- [x] 1.4 Agregar la entrada `embedding` a GLOSSARY (definición: representación numérica de geometría facial, dato sensible; legalRef: "Ley 25.326, Art. 2")
- [x] 1.5 Agregar la entrada `worm` a GLOSSARY (definición: Write Once Read Many; el archivo no puede modificarse ni borrarse; garantiza autenticidad de la evidencia)
- [x] 1.6 Agregar la entrada `liveness` a GLOSSARY (definición: prueba de persona viva real frente a la cámara — no foto, video ni máscara)
- [x] 1.7 Agregar la entrada `cadena_de_custodia` a GLOSSARY (definición: registro criptográfico que prueba que la evidencia no fue alterada desde su captura)
- [x] 1.8 Agregar la entrada `face_mesh` a GLOSSARY (definición: malla de 468 puntos del rostro generada por MediaPipe para medir geometría facial)
- [x] 1.9 Agregar la entrada `datos_biometricos` a GLOSSARY (definición: datos derivados de características físicas; clasificados como datos sensibles; legalRef: "Ley 25.326")
- [x] 1.10 Verificar que TypeScript compila `glossary.ts` sin errores de tipo (el Record es exhaustivo con TermKey) — `npx tsc --noEmit`: 0 errores

## 2. Componente átomo Term

- [x] 2.1 Crear `frontend/src/ui/Term.tsx` con la interfaz `TermProps` (`termKey: TermKey`, `children?: React.ReactNode`, `className?: string`)
- [x] 2.2 Implementar el renderizado base: texto con `underline decoration-dotted cursor-help` + icono pequeño "?" (usar icono existente de `components.tsx` o un carácter `?` estilizado)
- [x] 2.3 Implementar tooltip en hover (desktop): `div` con `role="tooltip"` oculto por defecto, visible con clases Tailwind `group-hover:visible group-hover:opacity-100`; texto con la `definition` del GLOSSARY
- [x] 2.4 Agregar `legalRef` al tooltip cuando existe (`GLOSSARY[termKey].legalRef`), en texto secundario más pequeño
- [x] 2.5 Implementar lógica touch (mobile): `useState<boolean>` para `isTipVisible`; `onClick` toggle con `stopPropagation`
- [x] 2.6 Implementar cierre del tooltip al click fuera: useEffect con listener en `document` que cierra el tooltip si el click no es en el componente (usando `useRef`)
- [x] 2.7 Agregar accesibilidad: `id` único por instancia (ej. `term-${termKey}`), `aria-describedby={id}` en el texto, `role="tooltip"` en el div del tooltip
- [x] 2.8 Agregar `aria-label="Ver definición de {GLOSSARY[termKey].label}"` al icono "?"
- [x] 2.9 Verificar que `children` override funciona: si se pasa children, mostrar ese texto en lugar de `GLOSSARY[termKey].label`
- [x] 2.10 Confirmar que no se agrega ninguna dependencia nueva en `package.json` (solo Tailwind + React)

## 3. Panel de glosario completo

- [x] 3.1 Crear `frontend/src/ui/GlossaryPanel.tsx` con props `isOpen: boolean` y `onClose: () => void`
- [x] 3.2 Implementar el modal con `role="dialog"`, `aria-modal="true"`, `aria-label="Glosario de términos"`, overlay con click-fuera para cerrar
- [x] 3.3 Implementar el cierre con tecla Escape (useEffect + keydown listener)
- [x] 3.4 Iterar `Object.entries(GLOSSARY)` para renderizar la lista de términos: título (`label`), definición (`definition`), referencia legal en texto secundario (`legalRef`) si existe
- [x] 3.5 Verificar que el panel lista las 7 entradas del GLOSSARY

## 4. Integración del botón de glosario en el footer

- [x] 4.1 Leer `frontend/src/ui/shells.tsx` para identificar el footer existente
- [x] 4.2 Agregar estado local `glossaryOpen: boolean` en el componente de shell que tenga el footer
- [x] 4.3 Agregar botón/enlace "Glosario" (o icono "?" con aria-label) en el footer que active `glossaryOpen = true`
- [x] 4.4 Renderizar `<GlossaryPanel isOpen={glossaryOpen} onClose={() => setGlossaryOpen(false)} />` dentro del shell
- [x] 4.5 Verificar que el botón es visible en todas las pantallas que usan ese shell

## 5. Reemplazo de menciones — Prioridad 1 (alumno)

- [x] 5.1 `frontend/src/screens/AcuseExamen.tsx:215` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 5.2 `frontend/src/screens/Cierre.tsx:44` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 5.3 `frontend/src/screens/StudentProfile.tsx:381` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 5.4 `frontend/src/screens/StudentProfile.tsx:493` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 5.5 `frontend/src/screens/StudentProfile.tsx:490` — envolver "embedding" con `<Term termKey="embedding">`
- [x] 5.6 `frontend/src/features/consentimiento/ConsentScreen.tsx:49` — envolver "embedding" con `<Term termKey="embedding">` [NOTA: línea 49 es string en mock data; no accesible como JSX. Se envolvió "datos biométricos" en el label del checkbox (JSX visible) y se añadió import de Term]
- [x] 5.7 `frontend/src/features/consentimiento/ConsentScreen.tsx:49` — envolver "WORM" con `<Term termKey="worm">` [NOTA: ídem 5.6 — línea 49 es string; se documentó la limitación]
- [x] 5.8 `frontend/src/screens/Consent.tsx:66` — envolver "embedding" con `<Term termKey="embedding">`
- [x] 5.9 `frontend/src/features/enrollment/EnrollmentConsentStep.tsx:123` — envolver "embedding" con `<Term termKey="embedding">` [real path: screens/enrollment/]
- [x] 5.10 `frontend/src/screens/Biometria.tsx:61` — envolver "liveness" con `<Term termKey="liveness">`
- [x] 5.11 `frontend/src/features/enrollment/EnrollmentBiometricStep.tsx:142` — envolver "liveness" con `<Term termKey="liveness">` [real path: screens/enrollment/; también envuelto face_mesh]
- [x] 5.12 `frontend/src/features/enrollment/EnrollmentBiometricStep.tsx:251` — envolver "liveness" con `<Term termKey="liveness">` [real path: screens/enrollment/; también envuelto embedding y face_mesh en el mismo texto]
- [x] 5.13 `frontend/src/features/enrollment/EnrollmentBiometricStep.tsx:291` — envolver "L2.5" con `<Term termKey="l2_5">` [real path: screens/enrollment/]

## 6. Reemplazo de menciones — Prioridad 2 (admin/revisor)

- [x] 6.1 `frontend/src/screens/AdminDashboard.tsx:61` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 6.2 `frontend/src/screens/Reports.tsx:68` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 6.3 `frontend/src/screens/Revisor.tsx:119` — envolver "L2.5" con `<Term termKey="l2_5">`
- [x] 6.4 `frontend/src/screens/Revisor.tsx:99` — envolver "cadena de custodia" con `<Term termKey="cadena_de_custodia">`
- [x] 6.5 `frontend/src/screens/AdminDetectionHarness.tsx:1189` — envolver "L2.5" con `<Term termKey="l2_5">` [L2.5 en esa línea era JSX comment; el texto visible fue envuelto en el <span> siguiente]
- [x] 6.6 `frontend/src/screens/AdminDetectionHarness.tsx:1194` — envolver "L2.5" con `<Term termKey="l2_5">` [ver nota 6.5]
- [x] 6.7 `frontend/src/features/enrollment/BiometricRenewalStatus.tsx:100` — envolver "L2.5" con `<Term termKey="l2_5">` [real path: screens/enrollment/; también envuelto embedding]
- [x] 6.8 `frontend/src/screens/SessionDetail.tsx:62` — envolver "cadena de custodia" con `<Term termKey="cadena_de_custodia">`
- [x] 6.9 `frontend/src/screens/Examen.tsx:54` — envolver "cadena de custodia" con `<Term termKey="cadena_de_custodia">` [LIMITACIÓN: línea 54 es string en estado useState[], no JSX; se importó Term para uso futuro pero el texto en mensajes[] no puede usar JSX directamente]

## 7. Verificación de menciones restantes

- [x] 7.1 Revisar `frontend/src/lib/api.ts:318` — DECISIÓN: L2.5 en api.ts está en `cuerpo` de MOCK_CONSENT_TEXT (línea 319, no 318). Es un campo de datos string que simula respuesta de API. En producción el texto viene del backend como string plano. Confirma D-05: no se envuelve. NO es un comentario de dev — es text visible al usuario en el bloque "Tus derechos", pero al ser string de datos (no JSX), `<Term>` no aplica sin un parser texto→JSX.
- [x] 7.2 Buscar Face Mesh visibles al usuario — wrapeados en EnrollmentBiometricStep.tsx:142 y :251. Resto son en tipos/interfaces/comentarios/vision files, no texto de UI.
- [x] 7.3 Verificar menciones restantes — grep realizado. Pendientes (data-layer, string, no JSX): Examen.tsx:55 (cadena custodia en useState string), ConsentScreen.tsx:50 (WORM+embedding en mock API string). Todos los JSX visibles al usuario están envueltos. JSX comments (ADH:1190, BiometricRenewal:9) son dev-only.

## 8. Actualización de CHANGES.md

- [x] 8.1 Agregar la entrada `C-28` en la sección "Refinamiento post-fundación" de `CHANGES.md` con estado `[ ]` propuesto, scope, dependencias (ninguna — independiente como C-27), governance MEDIO y leer-antes [YA EXISTÍA — el /opsx:propose lo creó]
- [x] 8.2 Actualizar el conteo total en el resumen de CHANGES.md (de 27 a 28 changes) [YA ESTABA en "28 changes"]
- [x] 8.3 Actualizar la fila de "Refinamiento post-fundación" en la tabla resumen para incluir C-28 [YA ESTABA — C-21…C-28 en la tabla]
