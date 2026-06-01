## Context

Desde C-22, el paso de DNI en `EnrollmentDniStep.tsx` es un formulario con su propio `getUserMedia` y un solo frame capturado. El flag `ENABLE_DNI_SCAN` (default `false`) lo oculta en la demo detrás de un banner "Próximamente". El tipo `EscaneDNI` modela una sola imagen (`imagen: string | null`). En C-37 se introdujo `CameraSnapshotCapture` —un componente genérico de captura estática con `shape: 'oval' | 'rect'`— concebido explícitamente para ser reutilizado por C-38 con `shape='rect'`. Esta change completa ese diseño: (a) activa el DNI para la demo, (b) convierte el flujo a frente→dorso secuencial usando `CameraSnapshotCapture`, y (c) extiende el modelo de datos para los dos lados.

**Archivos clave del estado actual:**
- `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — paso de DNI con getUserMedia propio, un solo lado
- `frontend/src/ui/CameraSnapshotCapture.tsx` — componente de captura, shape `oval|rect`, ya listo para rect
- `frontend/src/lib/types.ts:230` — `EscaneDNI { captura_completada, imagen, fecha_captura }`
- `frontend/src/lib/api.ts:167` — `ENABLE_DNI_SCAN = import.meta.env.VITE_ENABLE_DNI_SCAN === '1'`
- `frontend/src/lib/api.ts:626` — `guardarEscaneDNI(imagen: string)`
- `frontend/src/screens/StudentProfile.tsx:329` — paso `'dni'`

## Goals / Non-Goals

**Goals:**

- Reusar `CameraSnapshotCapture` sin duplicar lógica de cámara en `EnrollmentDniStep`
- Capturar FRENTE y DORSO del DNI de forma secuencial, con preview/confirmar por lado
- Marco visual estilo escáner ID-1 (aspecto CR80 85.6×54 mm, esquinas tipo "corners")
- Activar el flujo para demo sin configuración extra (`ENABLE_DNI_SCAN` default `true`)
- Extender `EscaneDNI` y `api.guardarEscaneDNI` para los dos lados
- Mantener el DNI como OPCIONAL (no bloquea `perfil_completo`)
- Cumplimiento Ley 25.326: dato sensible, finalidad acotada, cifrado at-rest server-side, eliminación al egreso

**Non-Goals:**

- Validación del documento (OCR, NFC, verificación del chip): scope server-side futuro
- Backend real o persistencia fuera de la sesión de demo
- Cambio en el gate `puedeRendir` — el DNI sigue sin afectarlo
- Soporte para CUIT/pasaporte u otros documentos
- Avatar del alumno en el dashboard (diferido, si no es trivial en esta sesión)

## Decisions

### D1 — Reusar `CameraSnapshotCapture` con `shape='rect'` y `scannerCorners` (no crear otro componente)

`CameraSnapshotCapture` fue diseñado en C-37 con la props `shape: 'oval' | 'rect'` explícitamente para DNI. En lugar de un nuevo componente, se agrega la prop opcional `scannerCorners?: boolean` que, cuando es `true`, superpone 4 esquinas SVG sobre el marco `rect` (estilo escáner). El modo `oval` (C-37) queda 100% intacto.

**Alternativa descartada**: crear un `DniScannerCapture` separado. Duplicaría getUserMedia, cleanup, preview/preview-buttons. No justificado.

### D2 — Estado `lado: 'frente' | 'dorso'` en `EnrollmentDniStep` (no en CameraSnapshotCapture)

El flujo secuencial vive en `EnrollmentDniStep`. `CameraSnapshotCapture` sigue siendo stateless respecto al concepto de "lado": recibe `instruction` e `onCapture` distintos según el lado activo. Esto mantiene `CameraSnapshotCapture` genérico y reutilizable.

```
EnrollmentDniStep state:
  lado: 'frente' | 'dorso' | null  (null = no capturando)
  imagenFrente: string | null
  imagenDorso: string | null
  fase: 'inicio' | 'capturando' | 'procesando' | 'completado'
```

Cuando `lado !== null`, se monta `<CameraSnapshotCapture shape="rect" scannerCorners aspectRatio={85.6/54} ... />`.

### D3 — `EscaneDNI`: campo `imagen` reemplazado por `imagen_frente` + `imagen_dorso`

```ts
// Antes (C-22):
export interface EscaneDNI {
  captura_completada: boolean;
  imagen: string | null;
  fecha_captura: string;
}

// Después (C-38):
export interface EscaneDNI {
  captura_completada: boolean;
  imagen_frente: string | null;
  imagen_dorso: string | null;
  fecha_captura: string;
}
```

Consumidores afectados: `api.ts` (construcción del objeto) y `EnrollmentDniStep.tsx` (display del estado completado). No hay consumidor de `imagen` fuera de estos dos archivos.

### D4 — `api.guardarEscaneDNI(frente: string, dorso: string)`: dos parámetros explícitos

La firma pasa de un string a dos strings nombrados semánticamente. Mock demo: construye `EscaneDNI` con `imagen_frente` e `imagen_dorso`, delay de 400ms.

```ts
async guardarEscaneDNI(frente: string, dorso: string): Promise<EscaneDNI>
```

### D5 — `ENABLE_DNI_SCAN` default `true` para demo

Se cambia de `import.meta.env.VITE_ENABLE_DNI_SCAN === '1'` a:

```ts
export const ENABLE_DNI_SCAN: boolean =
  import.meta.env.VITE_ENABLE_DNI_SCAN !== '0';
```

Esto activa el flag por defecto. Para apagarlo explícitamente en cualquier entorno: `VITE_ENABLE_DNI_SCAN=0`. La lógica de "Próximamente" queda disponible pero ya no visible en demo.

**Alternativa**: hardcodear `true`. Descartada porque elimina la posibilidad de desactivar en staging/producción sin cambio de código.

### D6 — Marco escáner: prop `scannerCorners?: boolean` en `CameraSnapshotCapture`

Cuando `shape='rect'` y `scannerCorners=true`, se renderizan 4 esquinas absolutas sobre el contenedor del marco: 2 líneas por esquina (horizontal + vertical) en color primario/blanco, realizadas en CSS puro (pseudo-elementos o divs). No requiere SVG externo.

```
┌──┐          ┌──┐
│              │
│   [VIDEO]    │
│              │
└──┘          └──┘
```

Longitud de cada tramo: `min(20%, 28px)`. Grosor: 3px. Color: `#FFFFFF` sobre fondo oscuro del video / esquinas sobre `border-neutral-300`.

### D7 — Contador de pasos en `StudentProfile`: "Paso 4 de 4" cuando DNI activo

El paso `'dni'` actualiza el subtítulo de `<header>` a `Paso {ENABLE_DNI_SCAN ? '4' : '3'} de {ENABLE_DNI_SCAN ? '4' : '3'}`. El paso `'foto_perfil'` ya usa `{ENABLE_DNI_SCAN ? '4' : '3'}` — ajustar para consistencia.

### D8 — Nota legal actualizada en `EnrollmentDniStep`

El aviso de dato sensible menciona explícitamente "frente y dorso del DNI", finalidad de verificación de identidad, cifrado AES-256-GCM server-side, eliminación al egreso, holds disciplinarios.

## Risks / Trade-offs

- **[Risk] `imagen` renombrado a `imagen_frente`/`imagen_dorso` es BREAKING**: ningún consumidor externo (solo `api.ts` + `EnrollmentDniStep.tsx`), pero hay que migrar ambos en la misma tarea para evitar errores de TypeScript. → Mitigation: task explícita de migración de tipo + validación `tsc --noEmit`.
- **[Risk] `scannerCorners` en modo `oval` (accidental)**: la prop se silencia (no renderiza nada) cuando `shape='oval'`. → Mitigation: prop solo se aplica cuando `shape === 'rect'` en la lógica del componente.
- **[Risk] getUserMedia en mobile con cámara trasera**: el DNI se captura mejor con cámara trasera. `CameraSnapshotCapture` hoy usa `facingMode: 'user'`. → Mitigation: para C-38, se puede pasar `facingMode?: 'environment'` como prop opcional a `CameraSnapshotCapture` (o hardcodear `environment` solo para shape `rect`). Documenta como mejora futura si no entra en las tasks.
- **[Risk] `ENABLE_DNI_SCAN` default `true` en producción**: la activación por negación (`!== '0'`) activa el flag en producción si no se configura la variable. → Mitigation: documentar en el comentario del código y en el README de variables que `VITE_ENABLE_DNI_SCAN=0` es requerido en producción hasta que el backend esté listo.
- **[Risk] Demo guarda dataURLs en memoria**: dos imágenes JPEG ~200–400 KB cada una en el estado de la sesión. Aceptable para demo; no bloquea. → Mitigation: las imágenes se descartan al recargar la página (estado efímero del mock).

## Migration Plan

1. Actualizar `EscaneDNI` en `types.ts` (campo `imagen` → `imagen_frente` + `imagen_dorso`)
2. Actualizar `api.guardarEscaneDNI` para la nueva firma y el nuevo tipo
3. Actualizar `ENABLE_DNI_SCAN` a default `true` (`!== '0'`)
4. Agregar prop `scannerCorners` a `CameraSnapshotCapture` (compatible hacia atrás — default `false`)
5. Refactorizar `EnrollmentDniStep` completo: eliminar getUserMedia propio, flujo frente→dorso con `CameraSnapshotCapture`
6. Actualizar `StudentProfile` (contadores de paso, resumen DNI con frente+dorso)
7. `tsc --noEmit` — 0 errores

**Rollback**: si `VITE_ENABLE_DNI_SCAN=0`, el banner "Próximamente" vuelve a aparecer. No hay migración de datos persistentes (todo es mock in-memory).

## Open Questions

- **¿Cámara trasera para DNI en mobile?**: ¿Agregar `facingMode?: ConstrainDOMString` como prop a `CameraSnapshotCapture` en esta misma change, o diferir? Recomendación: agregar la prop en esta change (trivial, no rompe C-37).
- **¿Avatar en `AlumnoDashboard`?**: Diferido a una task OPCIONAL al final — si el implementador lo considera trivial (leer `foto_perfil` del store y mostrarlo en el header), que lo incluya. Si no, se registra como C-39 o tech debt.
