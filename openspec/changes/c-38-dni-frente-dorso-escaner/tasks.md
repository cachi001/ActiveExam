## 1. Tipos y modelo de datos

- [x] 1.1 En `frontend/src/lib/types.ts`: reemplazar el campo `imagen: string | null` de `EscaneDNI` por `imagen_frente: string | null` e `imagen_dorso: string | null` — mantener `captura_completada` y `fecha_captura` sin cambio
- [x] 1.2 Actualizar el JSDoc del tipo `EscaneDNI` para mencionar que ambos campos son datos sensibles (Ley 25.326), cifrado at-rest server-side, finalidad acotada, eliminados al egreso

## 2. API mock — guardarEscaneDNI y ENABLE_DNI_SCAN

- [x] 2.1 En `frontend/src/lib/api.ts`: actualizar la firma de `guardarEscaneDNI` de `(imagen: string)` a `(frente: string, dorso: string)` y construir el `EscaneDNI` de retorno con `imagen_frente: frente` e `imagen_dorso: dorso`
- [x] 2.2 En `frontend/src/lib/api.ts`: actualizar la constante `ENABLE_DNI_SCAN` de `import.meta.env.VITE_ENABLE_DNI_SCAN === '1'` a `import.meta.env.VITE_ENABLE_DNI_SCAN !== '0'` (default `true`)
- [x] 2.3 Actualizar el JSDoc de `ENABLE_DNI_SCAN` para documentar que el default es `true` y que `VITE_ENABLE_DNI_SCAN=0` lo desactiva explícitamente

## 3. CameraSnapshotCapture — nuevas props (scannerCorners y facingMode)

- [x] 3.1 En `frontend/src/ui/CameraSnapshotCapture.tsx`: agregar prop opcional `scannerCorners?: boolean` (default `false`) a la interfaz `CameraSnapshotCaptureProps` con JSDoc
- [x] 3.2 Agregar prop opcional `facingMode?: ConstrainDOMString` (default `'user'`) a la interfaz `CameraSnapshotCaptureProps` con JSDoc
- [x] 3.3 En el `getUserMedia` del `useEffect`: pasar `facingMode` al constraint `{ video: { facingMode } }` en lugar del literal `'user'`
- [x] 3.4 Crear el componente de esquinas de escáner `ScannerCorners`: 4 divs absolutamente posicionados (top-left, top-right, bottom-left, bottom-right), cada uno con 2 segmentos CSS (pseudo-elementos o spans) de ~24px de largo y 3px de ancho en color `#FFFFFF` con `opacity-90`
- [x] 3.5 Renderizar `<ScannerCorners />` dentro del contenedor del marco `rect` cuando `scannerCorners && shape === 'rect'` — tanto en fase `capturando` como en fase `preview`
- [x] 3.6 Verificar que `scannerCorners=true` con `shape='oval'` no renderiza ningún elemento de esquina (condición `shape === 'rect'` en el guard)

## 4. Refactor EnrollmentDniStep — flujo frente→dorso con CameraSnapshotCapture

- [x] 4.1 En `frontend/src/screens/enrollment/EnrollmentDniStep.tsx`: eliminar imports de `useRef`, y los refs `videoRef`, `canvasRef`, `streamRef`
- [x] 4.2 Eliminar el estado `camaraLista` y `errorCamara` (los maneja `CameraSnapshotCapture` internamente)
- [x] 4.3 Eliminar la función `iniciarCamara` completa (getUserMedia propio)
- [x] 4.4 Eliminar la función `capturarDNI` completa (canvas drawImage propio)
- [x] 4.5 Agregar al estado local: `lado: 'frente' | 'dorso' | null` (inicializado en `null`) e `imagenFrente: string | null` e `imagenDorso: string | null`
- [x] 4.6 Actualizar el tipo `Fase` para remover `'capturando'` y `'procesando'` del estado del componente (esas fases son internas de `CameraSnapshotCapture`); el componente queda con `'inicio' | 'completado'`
- [x] 4.7 Implementar `handleFrenteCapturado(dataUrl: string)`: guarda `imagenFrente`, cierra `CameraSnapshotCapture` (`lado = null`), activa captura del dorso (`lado = 'dorso'`)
- [x] 4.8 Implementar `handleDorsoCapturado(dataUrl: string)`: guarda `imagenDorso`, cierra `CameraSnapshotCapture` (`lado = null`), llama `api.guardarEscaneDNI(imagenFrente, dataUrl)`, pasa a fase `completado` y llama `onEscaneado(escan)`
- [x] 4.9 Implementar `handleCancelarCaptura()`: cierra `CameraSnapshotCapture` (`lado = null`), vuelve a fase `inicio` sin perder imágenes ya capturadas
- [x] 4.10 En el render de fase `inicio`: mostrar dos botones cuando `lado === null` — "Escanear DNI" que activa `lado = 'frente'` y "Omitir este paso" que llama `onOmitir`
- [x] 4.11 Montar `<CameraSnapshotCapture>` cuando `lado !== null`, con props: `shape='rect'`, `scannerCorners={true}`, `aspectRatio={85.6/54}`, `facingMode='environment'`, `instruction` según `lado` (frente vs dorso), `onCapture` y `onCancel` apropiados
- [x] 4.12 En el render de fase `completado`: mostrar "DNI registrado (frente y dorso)" con la fecha de `escanActual.fecha_captura` formateada en `es-AR`; eliminar la referencia al campo `imagen` (reemplazado por `imagen_frente`/`imagen_dorso`)
- [x] 4.13 Actualizar el aviso legal para mencionar "frente y dorso del DNI" como dato sensible (Ley 25.326)
- [x] 4.14 Importar `CameraSnapshotCapture` desde `'../../ui/CameraSnapshotCapture'`

## 5. StudentProfile — contadores de paso y resumen DNI

- [x] 5.1 En `frontend/src/screens/StudentProfile.tsx`: en el encabezado del paso `'foto_perfil'`, actualizar el subtítulo a "Paso 2 de {ENABLE_DNI_SCAN ? '4' : '3'}" (hoy ya usa ENABLE_DNI_SCAN — verificar coherencia)
- [x] 5.2 En el encabezado del paso `'biometria'`, actualizar a "Paso 3 de {ENABLE_DNI_SCAN ? '4' : '3'}"
- [x] 5.3 En el encabezado del paso `'dni'`, actualizar a "Paso {ENABLE_DNI_SCAN ? '4' : '3'} de {ENABLE_DNI_SCAN ? '4' : '3'} — Opcional. El DNI refuerza la verificación pero no bloquea el perfil completo."
- [x] 5.4 En la vista principal del perfil (`paso === 'perfil'`): actualizar la tarjeta/sección de DNI para mostrar "Frente y dorso registrados" cuando `enrollment.dni?.captura_completada` es `true`, en lugar de solo "DNI registrado"

## 6. Verificación de tipos TypeScript

- [x] 6.1 Ejecutar `tsc --noEmit` en `frontend/` — corregir cualquier error residual del campo `imagen` renombrado
- [x] 6.2 Verificar que ningún archivo fuera de `api.ts` y `EnrollmentDniStep.tsx` referencia el campo `imagen` de `EscaneDNI` (búsqueda en todo el proyecto)

## 7. Validación y registro del change

- [x] 7.1 Ejecutar `openspec validate --strict --change c-38-dni-frente-dorso-escaner` — resolver cualquier error
- [x] 7.2 Actualizar `CHANGES.md`: agregar entrada `[C-38] c-38-dni-frente-dorso-escaner` en la sección "Refinamiento post-fundación" con estado `[ ]`, scope, dependencias (C-22, C-37), governance MEDIO, leer antes y actualizar el total de changes de 37 a 38
