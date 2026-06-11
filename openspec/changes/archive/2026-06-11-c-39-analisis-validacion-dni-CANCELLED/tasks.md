## 1. Tipos — Extender types.ts con AnalisisDNI y EscaneDNI

- [x] 1.1 Agregar el tipo `EstadoAnalisisDNI = 'preliminar_ok' | 'requiere_revision'` en `frontend/src/lib/types.ts` (NUNCA 'aprobado' ni 'rechazado')
- [x] 1.2 Definir la interfaz `DatosOCRMock` con campos: `numero_documento`, `apellido`, `nombre`, `fecha_nacimiento`, `fecha_vencimiento`, `sexo: 'M' | 'F' | 'X'`, `cuil`
- [x] 1.3 Definir la interfaz `AnalisisDNI` con los campos: checks de integridad (`documento_detectado`, `imagen_legible`, `tipo_documento: 'dni_argentino'`, `pdf417_leido`), `datos_extraidos: DatosOCRMock`, `concordancia_facial: number`, `estado: EstadoAnalisisDNI`, `timestamp_analisis: string`, `version_analisis: string`
- [x] 1.4 Extender la interfaz `EscaneDNI` con el campo opcional `analisis?: AnalisisDNI` — compatible hacia atrás con C-38

## 2. API mock — Implementar api.analizarDNI()

- [x] 2.1 Agregar la función `async analizarDNI(): Promise<AnalisisDNI>` en `frontend/src/lib/api.ts` con delay de ~1800ms (`await delay(1800)`)
- [x] 2.2 Implementar el cuerpo del mock con datos coherentes con el alumno demo "Emiliano Cáceres" (FRM-23-4912): número `'23.456.789'`, apellido `'CÁCERES'`, nombre `'EMILIANO GASTÓN'`, nacimiento `'15/08/1995'`, vencimiento `'15/08/2031'`, sexo `'M'`, CUIL `'20-23456789-4'`
- [x] 2.3 Implementar variación cosmética de `concordancia_facial` en rango 0.88–0.96 (base determinista, ej. `0.92 + (Math.sin(Date.now() / 1e8) * 0.04)`) para que no sea siempre idéntica entre corridas
- [x] 2.4 Asegurar que `api.analizarDNI()` NO realice ninguna llamada de red — todo generado localmente en memoria de sesión
- [x] 2.5 Agregar `analizarDNI` a la exportación del objeto `api` y al type de la API mock (verificar que typescript compila sin error con `tsc --noEmit`)

## 3. EnrollmentDniStep — Fases analizando y resultado

- [x] 3.1 Extender el tipo `Fase` en `EnrollmentDniStep.tsx`: `'inicio' | 'analizando' | 'resultado' | 'completado'`
- [x] 3.2 Agregar estado local `analisis: AnalisisDNI | null` inicializado con `escanActual?.analisis ?? null`; si `escanActual?.analisis` existe, inicializar `fase` en `'resultado'` en lugar de `'completado'`
- [x] 3.3 Modificar `handleDorsoCapturado`: tras `api.guardarEscaneDNI`, setear `fase('analizando')` e invocar `api.analizarDNI()`, luego setear el análisis y pasar a `fase('resultado')`
- [x] 3.4 Implementar render de fase `'analizando'`: spinner (`Icon name="progress_activity"` con clase `ae-spin`) + texto "Verificando documento…" + subtexto "Comprobando integridad y concordancia biométrica" — sin botón de cancelar
- [x] 3.5 Implementar render de fase `'resultado'` — sección 1: checks de integridad (grid 2×2 o fila horizontal) con ícono ✓ verde (`check_circle` fill) o ⚠ (`warning`) por check: Documento detectado / Imagen legible / Tipo: DNI Argentino / Código de barras (PDF417)
- [x] 3.6 Implementar sección 2 del panel: datos OCR extraídos en grid (Nombre, Apellido, N° Documento, Fecha de nacimiento, Fecha de vencimiento, CUIL) con nota "Extraídos por OCR (demo)"
- [x] 3.7 Implementar sección 3: concordancia facial con barra de progreso (`<progress>` o div con width porcentual), porcentaje en texto y nota "Comparado contra tu referencia biométrica del perfil"
- [x] 3.8 Implementar sección 4: estado general con `<Badge>` — tone `success` para `'preliminar_ok'` ("Análisis preliminar — OK") y tone `warning` para `'requiere_revision'` ("Análisis preliminar — Requiere revisión")
- [x] 3.9 Implementar el disclaimer obligatorio como `<Card>` con `Icon name="info"` y el texto completo con las cuatro partes: (a) análisis indicativo/demo, (b) validación oficial es server-side, (c) cliente = sensor no confiable (RN-GLB-01), (d) decisión siempre humana (L2.5) — inamovible y sin opción de colapsar
- [x] 3.10 Implementar el botón "Continuar" en fase `'resultado'` que llame `onEscaneado({ ...escanActual, analisis })` para pasar el escaneo completo con análisis adjunto

## 4. StudentProfile — Sección DNI con estado de análisis

- [x] 4.1 En `StudentProfile.tsx`, importar el tipo `AnalisisDNI` desde `types.ts`
- [x] 4.2 Modificar la sección DNI (`paso === 'perfil'`, card de "Verificación documental"): cuando `dniOk && enrollment?.dni?.analisis` existe, mostrar el badge de estado del análisis (`'preliminar_ok'` → tone success / `'requiere_revision'` → tone warning) en lugar del texto estático
- [x] 4.3 Agregar junto al badge la nota "· Pendiente de revisión humana" coherente con L2.5 — siempre visible cuando existe análisis
- [x] 4.4 Mantener el fallback: cuando `dniOk && !enrollment?.dni?.analisis`, mostrar el texto existente "Frente y dorso registrados el {fecha}"
- [x] 4.5 Cuando `!dniOk && ENABLE_DNI_SCAN`, mantener el botón "Escanear DNI (opcional)" sin cambios

## 5. Actualizar CHANGES.md con C-39

- [x] 5.1 Agregar la entrada `### [C-39] 'c-39-analisis-validacion-dni'` en CHANGES.md en la sección "Refinamiento post-fundación", después de C-38, con estado `[ ]` propuesto, scope, dependencias, governance MEDIO y "Leer antes"
- [x] 5.2 Actualizar el total en el resumen de CHANGES.md de 38 a **39 changes**

## 6. Verificación y validación

- [x] 6.1 Ejecutar `openspec validate --strict` y confirmar 0 errores para el change `c-39-analisis-validacion-dni`
- [x] 6.2 Ejecutar `tsc --noEmit` en el directorio `frontend/` y confirmar 0 errores de TypeScript
- [ ] 6.3 Verificar manualmente el flujo completo en el navegador: capturar frente → dorso → spinner "Verificando…" → panel con checks → badge estado → disclaimer → botón Continuar
- [ ] 6.4 Verificar que en `StudentProfile` sección DNI muestra el badge de análisis correcto tras completar el flujo
- [ ] 6.5 Verificar que omitir el DNI (botón "Omitir este paso") sigue funcionando sin error y sin disparar `analizarDNI`
- [ ] 6.6 Verificar que `concordancia_facial` varía levemente entre corridas (no es siempre idéntica) pero siempre permanece en rango 0.88–0.96 y el estado sigue siendo `'preliminar_ok'`
