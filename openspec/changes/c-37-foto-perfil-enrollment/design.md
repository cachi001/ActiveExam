## Context

**Estado actual**: El tipo `Principal` en `types.ts` no tiene campo de foto de perfil. El avatar del alumno se muestra con la inicial del nombre en dos lugares: `StudentProfile.tsx:302-304` (encabezado de datos personales) y `shells.tsx:97-99` (StaffShell sidebar). El `StudentShell` header muestra nombre+legajo pero no avatar. El flujo de enrollment de `StudentProfile.tsx` tiene pasos: `cargando → perfil → consentimiento → biometria → dni → renovar_biometria`.

**Restricciones clave**:
- No hay método de foto en `api.ts`. Existe `const FOTOS` (Unsplash/demo para sesiones de proctoring) — no relacionado, no tocar.
- `BiometricCapture.tsx` (C-36) está acoplado a retos de liveness / loop RAF / MediaPipe — no reutilizable para snapshot simple.
- La foto de perfil es **dato personal** (Ley 25.326), no biométrico en sentido estricto, pero con las mismas reglas de finalidad acotada y eliminación al egreso.
- No se requiere MediaPipe. La captura es un snapshot estático de un frame del video.
- C-38 (DNI) reutilizará `CameraSnapshotCapture` con `shape='rect'` sin modificarlo.

## Goals / Non-Goals

**Goals:**
- Componente genérico `CameraSnapshotCapture` parametrizable por forma y aspecto, reutilizable para foto de perfil (C-37) y DNI (C-38).
- Paso `'foto_perfil'` en el enrollment de `StudentProfile.tsx`, ANTES de `'biometria'`, DESPUÉS de `'consentimiento'`.
- Campo `foto_perfil?: string` en `Principal` + método mock `api.guardarFotoPerfil`.
- Avatar condicional en `StudentProfile` encabezado y `StaffShell` sidebar.
- El paso NO bloquea `perfil_completo` (el gate sigue siendo consentimiento + biometría vigente).

**Non-Goals:**
- Implementar el paso de DNI (lo hace C-38, que reutilizará el componente).
- Subir la foto a un servidor real (demo mock en memoria).
- Análisis de visión de la foto (eso es C-09/C-12 en producción real).
- Modificar `EnrollmentDniStep.tsx` para usar `CameraSnapshotCapture` (queda para C-38).
- Mostrar avatar en el `AlumnoDashboard` (decisión diferida — pantalla muy distinta; puede ser C-38 o posterior).

## Decisions

### D-1: Componente compartido `CameraSnapshotCapture` — API de props

```typescript
interface CameraSnapshotCaptureProps {
  /** Forma del marco-guía. 'oval' para foto de perfil; 'rect' para DNI. */
  shape: 'oval' | 'rect';
  /** Ratio ancho/alto del marco (default oval: 3/4, rect: 85.6/54 ≈ CR80). */
  aspectRatio?: number;
  /** Texto de instrucción principal mostrado bajo el marco (configurable). */
  instruction: string;
  /** Label opcional del overlay/contexto (e.g., "Foto de perfil"). */
  contextLabel?: string;
  /** Calidad JPEG del snapshot (0.0–1.0, default: 0.85). */
  jpegQuality?: number;
  /** Callback al confirmar la foto. Recibe dataURL JPEG. */
  onCapture: (dataUrl: string) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
}
```

**Por qué no reusar `BiometricCapture`**: está acoplado a retos de liveness, loop RAF, motor MediaPipe y métricas de challenge. `CameraSnapshotCapture` es un componente independiente, sin RAF, sin motor de visión.

**Por qué `aspectRatio` numérico y no preset**: permite que C-38 defina el aspecto del DNI (CR80: 85.6mm × 54mm ≈ 1.586) sin modificar el componente. Valor default distinto según `shape`.

### D-2: Flujo interno de `CameraSnapshotCapture`

```
montar → getUserMedia → mostrar video en vivo con marco-guía
  → usuario hace clic en "Capturar"
  → canvas.drawImage(video) → toDataURL('image/jpeg', quality)
  → mostrar preview con clip-path para la forma
  → "Usar foto" → onCapture(dataUrl)
  → "Repetir" → vuelve al video en vivo
```

Estados internos: `'capturando'` (video en vivo) | `'preview'` (foto tomada, pendiente confirmación) | `'error'` (sin permiso de cámara).

**Por qué no RAF**: no hay análisis frame-a-frame. El snapshot se toma solo cuando el usuario hace clic en "Capturar". Un RAF desperdiciaría CPU sin beneficio.

**Cleanup en desmontaje**: `stream.getTracks().forEach(t => t.stop())` al desmontar o al llamar `onCancel`.

### D-3: Estilo visual — referencia `BiometricCapture`

Portal a `document.body` con `createPortal`. Overlay `fixed inset-0 z-[60] bg-white` (igual que `BiometricCapture`). Botón "Cancelar" discreto `absolute top-4 right-4`.

Marco-guía:
- `shape='oval'`: `aspect-[3/4]`, `clipPath: 'ellipse(50% 50% at 50% 50%)'`. Ancho: `min(80vw, 300px)` (igual que `BiometricCapture`). Drop-shadow.
- `shape='rect'`: `rounded-xl`, aspecto según `aspectRatio` (C-38 puede pasar 1.586). Sin clip-path en el video; solo un borde redondeado como marco.

Para el **preview** en modo oval: `<img>` con `border-radius: 50%` y `object-fit: cover`. En modo rect: `<img>` con `border-radius: 12px`.

### D-4: Campo `foto_perfil` en `Principal` y método mock

```typescript
// types.ts — MODIFICADO
export interface Principal {
  // ... campos existentes ...
  /** dataURL JPEG de la foto de perfil (dato personal, finalidad acotada, eliminado al egreso). Demo: en memoria. */
  foto_perfil?: string;
}
```

```typescript
// api.ts — NUEVO método en el objeto `api`
async guardarFotoPerfil(dataUrl: string): Promise<void> {
  await delay(300);
  // Actualiza el registro in-memory del principal de estudiante
  PRINCIPALES.estudiante = { ...PRINCIPALES.estudiante, foto_perfil: dataUrl };
  // Nota Ley 25.326: dato personal, finalidad acotada. Server-side: cifrado AES-256-GCM,
  // eliminado al egreso. Demo: solo en memoria de la sesión.
}
```

**Por qué no actualizar el store directamente desde `api.ts`**: el store (Zustand) vive en la capa de presentación; la capa de API no debería importarlo. `StudentProfile.tsx` llama `api.guardarFotoPerfil`, luego llama `api.login(rol)` o actualiza el estado local del principal para reflejar el cambio en el store. Alternativa más limpia: `guardarFotoPerfil` solo guarda en `PRINCIPALES` y el componente re-hace login para sincronizar. Ver D-5.

### D-5: Sincronización del store tras guardar foto

Después de `api.guardarFotoPerfil(dataUrl)`, `StudentProfile.tsx` llama `useApp.getState().setPrincipal({ ...principal, foto_perfil: dataUrl })` (si el store lo expone) o usa el `principal` local con el campo inyectado. Opción más simple: `StudentProfile` tiene acceso al `principal` del store; llama `setFotoPerfil(dataUrl)` como acción del store (acción nueva en `store.ts`). Esto es lo recomendado — la acción es trivial.

```typescript
// store.ts — NUEVA acción
setFotoPerfil: (dataUrl: string) => void;
// implementación: set((s) => ({ principal: s.principal ? { ...s.principal, foto_perfil: dataUrl } : s.principal }))
```

### D-6: Integración del paso en `StudentProfile.tsx`

Nuevo tipo de paso:
```typescript
type PasoEnrollment =
  | 'cargando'
  | 'perfil'
  | 'consentimiento'
  | 'foto_perfil'   // ← NUEVO — entre consentimiento y biometria
  | 'biometria'
  | 'dni'
  | 'renovar_biometria';
```

Cambio en `handleConsentido`: si `acuse.via_alternativa` → `'perfil'`; si no tiene foto (`!principal?.foto_perfil`) → `'foto_perfil'`; si ya tiene foto pero no biometría → `'biometria'`; si tiene ambas → `'perfil'`.

Nuevo handler:
```typescript
const handleFotoCapturada = async (dataUrl: string) => {
  await api.guardarFotoPerfil(dataUrl);
  setFotoPerfil(dataUrl); // acción del store
  setPaso('biometria');
};
```

Contador de pasos actualizado: "Paso 2 de 3" (sin DNI) / "Paso 2 de 4" (con `ENABLE_DNI_SCAN`). Consentimiento = 1, Foto = 2, Biometría = 3, DNI = 4 (opcional).

### D-7: Dónde se muestra el avatar (alcance C-37)

| Lugar | Archivo | Antes | Después |
|-------|---------|-------|---------|
| Encabezado datos personales (StudentProfile) | `StudentProfile.tsx:302-304` | `div` con inicial | `<img>` circular si foto_perfil; inicial si no |
| StaffShell sidebar footer | `shells.tsx:97-99` | `div` con inicial | `<img>` circular si foto_perfil; inicial si no |
| StudentShell header (info nombre/legajo) | `shells.tsx:33-37` | sin avatar | sin cambio (solo texto) — se puede agregar en C-38 |

**Por qué no agregar en AlumnoDashboard**: la pantalla del dashboard tiene un layout distinto y no tiene bloque "datos del alumno" claro. Se difiere a C-38 o una tarea de UX posterior. No afecta funcionalidad.

### D-8: Nota de privacidad Ley 25.326

El paso `'foto_perfil'` incluye una nota breve de privacidad visible en la fase de instrucciones:
- "La foto de perfil es un dato personal (Ley 25.326): finalidad acotada, eliminada al egreso de la institución. En esta demo se guarda solo en memoria de la sesión."

No se agrega `<Term>` específico para foto (no es dato biométrico en sentido técnico). El glosario existente cubre los términos necesarios.

## Risks / Trade-offs

- **[Riesgo] `getUserMedia` en contexto no-HTTPS** → el componente maneja el error en la fase `'error'` con mensaje claro, igual que `BiometricCapture`. Mitigación: el entorno de demo ya corre en localhost o TLS.
- **[Riesgo] El campo `foto_perfil` en `Principal` persiste solo en memoria de la sesión demo** → esperado para MVP demo. En producción requeriría endpoint real y cifrado at-rest.
- **[Riesgo] C-38 reutiliza `CameraSnapshotCapture` sin modificarlo** → el contrato de props es estable (shape='rect' + aspectRatio configurable). Si C-38 necesita lógica adicional (e.g., guía de posición del DNI con texto adicional), puede extender con props opcionales sin breaking change.
- **[Trade-off] No se muestra avatar en `AlumnoDashboard`** → simplifica C-37 y evita layout changes en una pantalla no prioritaria. Diferido a C-38.
- **[Trade-off] El paso de foto NO bloquea `perfil_completo`** → si el alumno cancela la foto, puede continuar al paso de biometría y completar el enrollment. La foto es un "nice to have" para el avatar, no un requisito de habilitación. Esto simplifica el gate y evita bloqueos innecesarios.

## Open Questions

- **¿Debe la foto de perfil bloquear el inicio del enrollment biométrico?** Decisión tomada: NO (paso sugerido pero no obligatorio; si cancela se salta al paso biometría). Puede revisarse con UX.
- **¿El `StudentShell` header debe mostrar mini-avatar junto al nombre?** Diferido — solo se actualiza el bloque de datos existente (nombre+legajo), no se agrega avatar al header de navegación en esta iteración.
