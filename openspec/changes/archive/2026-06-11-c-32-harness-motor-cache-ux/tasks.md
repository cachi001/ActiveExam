## 1. Cache singleton del motor en harnessEngineLoader.ts

- [x] 1.1 Agregar variables privadas de módulo `_cachedEngine: VisionEngine | null` y `_initPromise: Promise<VisionEngine> | null` en `frontend/src/vision/harnessEngineLoader.ts`
- [x] 1.2 Modificar `loadRealEngine()` para implementar el flujo cache: devolver `_cachedEngine` si ya existe, esperar `_initPromise` si está en vuelo, o iniciar nueva carga asignando `_initPromise` antes del import dinámico
- [x] 1.3 Limpiar `_initPromise` al resolver (éxito o fallo) para evitar que una promesa ya-resuelta bloquee futuras llamadas
- [x] 1.4 En caso de fallo de `init()`, limpiar `_initPromise` y NO asignar `_cachedEngine`; propagar el error original sin cambios (comportamiento de D-6 conservado)
- [x] 1.5 Exportar `disposeRealEngine(): Promise<void>` que llame `_cachedEngine?.dispose()`, ponga ambas variables en `null`, y resuelva sin lanzar si no hay cache

## 2. Integración del cache en AdminDetectionHarness.tsx

- [x] 2.1 En `stopHarness()`, eliminar la llamada directa a `engineRef.current?.dispose()` — el motor WASM permanece vivo en cache entre ciclos Iniciar/Detener dentro de la misma sesión de página
- [x] 2.2 En el `useEffect` cleanup (desmontaje del componente), llamar `disposeRealEngine()` en lugar de `engineRef.current?.dispose()` para liberar GPU/WASM al navegar fuera del harness
- [x] 2.3 En el handler de `load-error` irrecuperable (si se agrega un botón "Reintentar"), llamar `disposeRealEngine()` antes de re-invocar `loadRealEngine()` para forzar re-init limpio
- [x] 2.4 Verificar con TypeScript (`tsc --noEmit`) que no quedan errores de tipos después de los cambios al loader

## 3. Spinner amigable para el estado 'loading'

- [x] 3.1 Reemplazar el contenido del bloque `engineMode === 'loading'` en `AdminDetectionHarness.tsx` (~línea 695): cambiar `<Icon name="hourglass_top">` por `<Icon name="progress_activity" className="... animate-spin">` y el título por `"Preparando la cámara…"`
- [x] 3.2 Eliminar toda mención de "WASM", "MediaPipe", "MB", "modelos" y "compilando" del mensaje del banner de carga
- [x] 3.3 Agregar subtítulo condicional `"Esto puede tardar unos segundos la primera vez."` que se muestra solo cuando el motor aún no fue cacheado (pasar un prop o flag al banner, derivado del estado del módulo loader)
- [x] 3.4 Verificar que el container del banner mantiene `role="status"` y `aria-live="polite"` (ya presente en C-30; confirmar no se eliminó)

## 4. Labels en lenguaje claro para los umbrales configurables

- [x] 4.1 En `AdminDetectionHarness.tsx`, actualizar el array de configuración de umbrales (~línea 1157-1162) para agregar un campo `clearLabel: string` a cada entrada con el nombre en español claro:
  - `face_absent_ms` → `"Segundos sin rostro para alertar"`
  - `multiple_faces_frames` → `"Fotogramas con varios rostros para alertar"`
  - `gaze_deviation_threshold` → `"Sensibilidad de mirada desviada"`
  - `gaze_sustained_ms` → `"Tiempo de mirada desviada para alertar"`
  - `gaze_fixation_tolerance` → `"Tolerancia de fijación de mirada"`
- [x] 4.2 Actualizar el renderizado del panel: mostrar `clearLabel` como etiqueta principal (`font-semibold`) y la clave técnica `label` como texto secundario debajo (`text-[11px] text-on-surface-variant font-mono`)
- [x] 4.3 Conservar el campo `hint` con redacción clara (ajustar si menciona jerga técnica); conservar el `<input>` editable y la validación de errores sin cambios funcionales

## 5. Tipo y función requestAndDetectExtraMonitor en contextDetectors.ts

- [x] 5.1 Exportar el tipo `ScreenPermissionResult` en `frontend/src/proctoring/contextDetectors.ts` con las tres variantes discriminadas: `'unsupported'`, `'denied'`, `'granted'`
- [x] 5.2 Implementar `requestAndDetectExtraMonitor(): Promise<ScreenPermissionResult>` que: detecta si `window.getScreenDetails` existe, llama la API directamente (requiere gesto del usuario), captura `NotAllowedError` y cualquier otro error devolviendo `'denied'`, y en éxito cuenta pantallas para `extra_monitor`
- [x] 5.3 Asegurar que la función `detectExtraMonitor(provider?)` existente permanece sin modificaciones de firma ni comportamiento (retrocompatibilidad con C-25)
- [x] 5.4 Agregar tests unitarios para `requestAndDetectExtraMonitor`: caso `unsupported` (mock sin `getScreenDetails`), caso `denied` (mock que lanza `NotAllowedError`), caso `granted` con 1 pantalla, caso `granted` con 2 pantallas

## 6. UX del flujo de permiso de monitores en AdminDetectionHarness.tsx

- [x] 6.1 Agregar estado `monitorPermission: 'idle' | 'requesting' | 'granted' | 'denied' | 'unsupported'` al componente, inicializado según si `window.getScreenDetails` existe al montar
- [x] 6.2 Actualizar `startHarness()`: detectar disponibilidad de la API y setear `monitorPermission` a `'idle'` o `'unsupported'` en consecuencia (en lugar del actual `setMonitorApiUnavailable`)
- [x] 6.3 Refactorizar la tarjeta de monitor en el panel de señales de entorno para mostrar la UI correcta según `monitorPermission`:
  - `'unsupported'`: ícono info + mensaje sobre compatibilidad (Chrome/Edge + HTTPS)
  - `'idle'`: texto explicativo breve + botón "Detectar pantallas" (ícono `monitor`)
  - `'requesting'`: botón disabled con spinner
  - `'denied'`: texto "Permiso denegado." + botón "Reintentar"
  - `'granted'`: señal `extra_monitor` con el mismo estilo visual de las otras tarjetas de señal
- [x] 6.4 Implementar el handler del botón "Detectar pantallas": llamar `requestAndDetectExtraMonitor()`, actualizar `monitorPermission` con el resultado, y si es `'granted'` iniciar el polling pasivo existente (`pollMonitor`) para actualizaciones posteriores
- [x] 6.5 Eliminar la variable de estado `monitorApiUnavailable` ya existente (reemplazada por `monitorPermission: 'unsupported'`) y actualizar todas las referencias en el JSX

## 7. Actualización de CHANGES.md

- [x] 7.1 Agregar la entrada `[C-32] c-32-harness-motor-cache-ux` en la sección "Refinamiento post-fundación" de `CHANGES.md`, marcada como `[ ]` pendiente, con dependencias (`C-23`, `C-25`, `C-29`, `C-30`), governance MEDIO, y el resumen del scope
- [x] 7.2 Actualizar el total de changes en la tabla resumen de `CHANGES.md` de 31 a 32

## 8. Verificación final

- [x] 8.1 Ejecutar `tsc --noEmit` y confirmar 0 errores de TypeScript tras todos los cambios
- [x] 8.2 Navegar manualmente al harness (`/admin/detection-test`), iniciar la cámara, detener y volver a iniciar — QA manual OK (cache singleton confirmado en `harnessEngineLoader.ts` líneas 26-90)
- [x] 8.3 Verificar que los labels de umbrales muestran nombres claros y que la edición sigue funcionando correctamente — QA manual OK
- [x] 8.4 Verificar que el botón "Detectar pantallas" aparece en Chrome/Edge y que el flujo de permiso funciona (conceder/denegar/reintentar) — QA manual OK
- [x] 8.5 Ejecutar `openspec validate --strict --change c-32-harness-motor-cache-ux` y confirmar OK sin errores
