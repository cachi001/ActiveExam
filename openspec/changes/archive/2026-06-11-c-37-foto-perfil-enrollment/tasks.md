## 1. Tipos y API — Cimientos de datos

- [x] 1.1 Agregar `foto_perfil?: string` a la interfaz `Principal` en `frontend/src/lib/types.ts` con comentario de privacidad Ley 25.326
- [x] 1.2 Agregar el método `guardarFotoPerfil(dataUrl: string): Promise<void>` al objeto `api` en `frontend/src/lib/api.ts` — guarda en `PRINCIPALES.estudiante.foto_perfil`, simula ~300 ms de latencia, incluye comentario de finalidad acotada Ley 25.326

## 2. Store — Acción setFotoPerfil

- [x] 2.1 Agregar la acción `setFotoPerfil: (dataUrl: string) => void` a la interfaz del store en `frontend/src/lib/store.ts`
- [x] 2.2 Implementar `setFotoPerfil` en el store: `set((s) => ({ principal: s.principal ? { ...s.principal, foto_perfil: dataUrl } : s.principal }))` — sin error si `principal` es null

## 3. Componente CameraSnapshotCapture — Estructura base

- [x] 3.1 Crear el archivo `frontend/src/ui/CameraSnapshotCapture.tsx` con la interfaz `CameraSnapshotCaptureProps` (props: `shape`, `aspectRatio`, `instruction`, `contextLabel`, `jpegQuality`, `onCapture`, `onCancel`)
- [x] 3.2 Definir el tipo de estado interno: `type Fase = 'capturando' | 'preview' | 'error'`
- [x] 3.3 Agregar refs: `videoRef`, `streamRef`, `canvasRef` (para el snapshot)
- [x] 3.4 Agregar estados: `fase`, `previewDataUrl`, `errorMsg`

## 4. CameraSnapshotCapture — Inicialización de cámara

- [x] 4.1 Implementar `useEffect` de montaje: llamar `getUserMedia({ video: { facingMode: 'user' } })`, asignar stream a `videoRef.srcObject`, guardar en `streamRef`
- [x] 4.2 Manejar error de `getUserMedia`: setear `fase='error'` y `errorMsg` con el mensaje del error
- [x] 4.3 Implementar cleanup del `useEffect`: `streamRef.current?.getTracks().forEach(t => t.stop())` al desmontar
- [x] 4.4 Implementar `handleCancel`: detener stream + llamar `onCancel()`

## 5. CameraSnapshotCapture — Snapshot y preview

- [x] 5.1 Implementar `handleCapturar`: crear canvas con `video.videoWidth × video.videoHeight`, llamar `ctx.drawImage(videoRef.current)`, obtener dataURL con `canvas.toDataURL('image/jpeg', jpegQuality ?? 0.85)`, setear `previewDataUrl` y `fase='preview'`
- [x] 5.2 Implementar `handleUsarFoto`: llamar `onCapture(previewDataUrl!)`, detener stream
- [x] 5.3 Implementar `handleRepetir`: limpiar `previewDataUrl`, setear `fase='capturando'` (el video sigue activo en el stream)

## 6. CameraSnapshotCapture — UI del overlay

- [x] 6.1 Usar `createPortal(contenido, document.body)` para el overlay — igual que `BiometricCapture`
- [x] 6.2 Contenedor raíz: `fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6`
- [x] 6.3 Botón "Cancelar" discreto: `absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900` (mismo estilo que `BiometricCapture`)
- [x] 6.4 `contextLabel` opcional encima del marco (texto pequeño en neutral-500)
- [x] 6.5 Marco oval (`shape='oval'`): contenedor `relative` con `width: 'min(80vw, 300px)'` y `drop-shadow(0 10px 24px rgba(0,0,0,0.15))`; div interior con `aspect-[3/4] overflow-hidden bg-neutral-100` y `clipPath: 'ellipse(50% 50% at 50% 50%)'`; `<video>` con `autoPlay muted playsInline className="absolute inset-0 w-full h-full object-cover"`
- [x] 6.6 Marco rect (`shape='rect'`): contenedor con el aspecto calculado (`aspectRatio ?? (85.6/54)`), borde `rounded-xl border-2 border-neutral-300`, sin clip-path
- [x] 6.7 Estado `'capturando'` — mostrar video en vivo + botón "Capturar" centrado abajo con ícono `photo_camera`
- [x] 6.8 Estado `'preview'` — ocultar video, mostrar `<img>` con `src={previewDataUrl}` y: si `shape='oval'` → `rounded-full object-cover w-full h-full`; si `shape='rect'` → `rounded-xl object-cover w-full h-full`; botones "Usar foto" y "Repetir"
- [x] 6.9 Estado `'error'` — ícono `videocam_off`, mensaje `errorMsg`, botón "Cancelar"
- [x] 6.10 Texto de instrucción `instruction` visible bajo el marco en estado `'capturando'` (text-neutral-600, text-center, max-w-xs)

## 7. StudentProfile — Nuevo paso foto_perfil

- [x] 7.1 Agregar `'foto_perfil'` al tipo `PasoEnrollment` en `StudentProfile.tsx`
- [x] 7.2 Importar `CameraSnapshotCapture` y la acción `setFotoPerfil` del store
- [x] 7.3 Implementar `handleFotoCapturada(dataUrl: string)`: llamar `await api.guardarFotoPerfil(dataUrl)`, llamar `setFotoPerfil(dataUrl)` del store, setear `paso='biometria'`
- [x] 7.4 Implementar `handleFotoCancelada()`: setear `paso='biometria'` directamente (sin guardar foto)
- [x] 7.5 Actualizar `handleConsentido`: si `via_alternativa` → `'perfil'`; si no tiene foto (`!principal?.foto_perfil`) → `'foto_perfil'`; si tiene foto pero no biometría → `'biometria'`; si tiene ambas → `'perfil'`
- [x] 7.6 Actualizar `handleIniciarEnrollment`: si no hay consentimiento → `'consentimiento'`; si no hay foto → `'foto_perfil'`; si no hay biometría → `'biometria'`; si todo completo → `'biometria'` (renovar)
- [x] 7.7 Agregar el bloque de render para `paso === 'foto_perfil'` dentro del `StudentShell`: encabezado con "Foto de perfil", contador de pasos "Paso 2 de N", nota de privacidad Ley 25.326, y `<CameraSnapshotCapture shape='oval' instruction='Posicioná tu cara dentro del óvalo' onCapture={handleFotoCapturada} onCancel={handleFotoCancelada} />`
- [x] 7.8 Actualizar el contador de pasos en el bloque `paso === 'consentimiento'`: "Paso 1 de {ENABLE_DNI_SCAN ? '4' : '3'}" (foto suma un paso)
- [x] 7.9 Actualizar el contador de pasos en el bloque `paso === 'biometria'`: "Paso 3 de {ENABLE_DNI_SCAN ? '4' : '3'}"

## 8. StudentProfile — Avatar condicional en encabezado de datos personales

- [x] 8.1 Reemplazar el `div` de la inicial en el encabezado (`StudentProfile.tsx` ~línea 302) por lógica condicional: si `principal?.foto_perfil` → `<img src={principal.foto_perfil} className="w-14 h-14 rounded-full object-cover shrink-0" alt={`Foto de perfil de ${principal.nombre}`} />`; si no → `div` con inicial (igual que antes)

## 9. StaffShell — Avatar condicional en footer del sidebar

- [x] 9.1 Reemplazar el `div` de la inicial en el footer del sidebar de `StaffShell` (`shells.tsx` ~línea 97) por lógica condicional: si `principal?.foto_perfil` → `<img src={principal.foto_perfil} className="w-9 h-9 rounded-full object-cover" alt={`Foto de ${principal?.nombre}`} />`; si no → `div` con inicial (igual que antes)

## 10. CHANGES.md — Registro del change C-37

- [x] 10.1 Agregar la entrada de `C-37` en la sección "Refinamiento post-fundación" de `CHANGES.md`, DESPUÉS de `C-36`, con scope, dependencias (`C-22`, `C-36`), governance MEDIO, caps NEW/MODIFIED, y "Leer antes"
- [x] 10.2 Actualizar el resumen al final de `CHANGES.md`: total de 37 changes, agregar C-37 al listado de refinamiento post-fundación
