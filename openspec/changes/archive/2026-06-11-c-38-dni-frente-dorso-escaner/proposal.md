## Why

El paso de escaneo de DNI existe desde C-22 pero está gateado por `ENABLE_DNI_SCAN` (default `false`) y muestra "Próximamente" — bloqueando cualquier demo del flujo de identidad documental. Además, solo captura UN lado del DNI con su propio `getUserMedia`, duplicando lógica ya extraída en el componente `CameraSnapshotCapture` (C-37). Para que el escaneo sea demostrable y correcto (frente + dorso, estilo escáner ID-1), se necesita: (1) activar el flag para demo, (2) refactorizar `EnrollmentDniStep` para reusar `CameraSnapshotCapture` con flujo secuencial frente→dorso, (3) extender el tipo `EscaneDNI` y `api.guardarEscaneDNI` para representar los dos lados, y (4) agregar el marco visual escáner (corners de DNI, aspecto CR80/ID-1).

## What Changes

- **Activar escaneo de DNI para demo**: `VITE_ENABLE_DNI_SCAN` default `true` (o constante `ENABLE_DNI_SCAN = true` en `api.ts`) para que el paso sea accesible en la demo sin configuración adicional. El escaneo sigue siendo OPCIONAL — no bloquea el perfil.
- **Extender `EscaneDNI`** en `types.ts`: reemplaza `imagen: string | null` por `imagen_frente: string | null` + `imagen_dorso: string | null`, manteniendo `captura_completada` y `fecha_captura`. **BREAKING** para los consumidores del campo `imagen` (solo `api.ts` y `EnrollmentDniStep.tsx`).
- **Actualizar `api.guardarEscaneDNI(frente, dorso)`**: firma de dos parámetros; construye el `EscaneDNI` con `imagen_frente` e `imagen_dorso`. Mock client-side (demo).
- **Refactorizar `EnrollmentDniStep`**: eliminar `useRef<HTMLVideoElement>`, `useRef<HTMLCanvasElement>`, `useRef<MediaStream>` y todo el `getUserMedia` propio. Reusar `CameraSnapshotCapture` con `shape='rect'`, `aspectRatio=85.6/54` (tarjeta ID-1/CR80). Flujo secuencial: captura FRENTE → preview/confirmar → captura DORSO → preview/confirmar → guardar. Estado interno `lado: 'frente' | 'dorso'`.
- **Marco escáner ID-1**: agregar prop opcional `scannerCorners?: boolean` a `CameraSnapshotCapture` para renderizar esquinas tipo escáner (4 corners en SVG/CSS) sobre el marco `rect`. No afecta el modo `oval` (C-37 intacto).
- **Instrucción contextual por lado**: "Colocá el FRENTE de tu DNI dentro del marco" / "Ahora girá el DNI y colocá el DORSO".
- **Contador de pasos en `StudentProfile`**: el paso `'dni'` pasa a ser "Paso 4 de 4" cuando `ENABLE_DNI_SCAN` está activo (hoy dice "Paso 3 de 3").
- **Nota legal actualizada**: el texto de dato sensible menciona frente + dorso, finalidad acotada, cifrado at-rest, eliminación al egreso.

## Capabilities

### New Capabilities

- `dni-scanner-dual-side`: Escaneo secuencial frente + dorso del DNI argentino con marco estilo ID-1/CR80, reutilizando `CameraSnapshotCapture` y el flujo de preview/confirmar ya probado en C-37.

### Modified Capabilities

- `exam-enrollment`: `EscaneDNI` extiende `imagen` a `imagen_frente` + `imagen_dorso`; `api.guardarEscaneDNI` acepta dos parámetros; `ENABLE_DNI_SCAN` pasa a `true` por defecto.
- `camera-snapshot-capture`: nueva prop opcional `scannerCorners?: boolean` para renderizar esquinas de escáner en modo `rect`. Compatible hacia atrás: si se omite, comportamiento actual inalterado.
- `student-profile-shell`: contador de pasos actualizado (4 de 4 cuando DNI activo); paso `'dni'` muestra FRENTE y DORSO completados en el resumen del perfil.

## Impact

- `frontend/src/lib/types.ts` — `EscaneDNI` (campo `imagen` → `imagen_frente` + `imagen_dorso`)
- `frontend/src/lib/api.ts` — `ENABLE_DNI_SCAN` default, `guardarEscaneDNI(frente, dorso)`
- `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — refactor completo (eliminar getUserMedia propio, reusar CameraSnapshotCapture, flujo frente→dorso)
- `frontend/src/ui/CameraSnapshotCapture.tsx` — nueva prop `scannerCorners?: boolean`
- `frontend/src/screens/StudentProfile.tsx` — contadores de paso, resumen DNI frente+dorso
- Sin cambios en rutas, auth, lógica de examen ni backend
