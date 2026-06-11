# 🚫 CANCELADO 2026-06-11

> **Razón**: el producto NO crea exámenes en la plataforma. Lo único que existe es `Configuracion.tsx` (4 tabs: Proctoring/Scoring/Detección/Consentimiento) con umbrales, scores y consentimiento globales — `admin_sistema`. `ConfigureExam.html` quedó como mockup huérfano en `frontend/src/screens/html/` y ninguna ruta lo monta.
>
> **Componentes ya extraídos** (DetectoresSelector, ExamenResumenCard) están en uso en otros lados del producto (Configuración del sistema), no se pierden.
>
> **Decisión del dueño**: Active Exam consume exámenes via integración LMS (LTI 1.3 + plugin Moodle, ver DD-20). La creación es responsabilidad del LMS, no de la plataforma.

---

## Why (original)

`ConfigureExam.tsx` es el último formulario del área admin sin validación inline: sigue usando `alert()` para errores, no tiene feedback de estado mientras guarda, y ofrece cero visibilidad del resultado antes de confirmar. C-40 modernizó el form (FormField/RangeInput, Button proporcional, sin "Ej:"), pero la experiencia de creación aún es frágil e improfesional para un admin que configura un examen con consecuencias legales (retención Ley 25.326, detectores L2.5).

## What Changes

- **Validación inline sin alert()**: cada campo requerido (nombre, cátedra, inicio) y cada campo con rango (duración 30–180, umbral 30–90, retención 7–90) muestra el mensaje de error directamente bajo el control vía el slot `error` de `FormField`. El botón Guardar refleja el estado de validez del formulario (deshabilitado si hay errores bloqueantes; spinner + "Guardando…" durante el guardado).
- **Preview/resumen del examen**: tarjeta `ExamenResumenCard` (lateral o al pie, antes de guardar) que muestra en lenguaje claro lo que se va a crear: nombre, cátedra, fecha/hora de inicio, duración en minutos, cantidad de detectores activos, umbral de revisión y días de retención. El admin ve de un vistazo qué configuró antes de confirmar.
- **Componente `DetectoresSelector`**: extrae el grupo de checkboxes de detectores activos a un componente reutilizable. Muestra un resumen ("N detectores activos") y es compatible con la interfaz actual de `toggleDet`.
- **Layout en secciones**: el form se divide en tres secciones con `SectionTitle` ("Información del examen", "Parámetros de proctoring", "Resumen y confirmación"). Los botones Cancelar/Guardar se ubican al final, después del resumen.
- **Semántica L2.5**: el preview menciona que los detectores "priorizan sesiones para revisión humana" (no sancionan) y que la retención se rige por Ley 25.326. Sin texto demo/stub.

## Capabilities

### New Capabilities

- `exam-creation-ui`: Formulario de creación/edición de examen con validación inline, preview del examen antes de guardar, componentes `DetectoresSelector` y `ExamenResumenCard`, layout en secciones, y feedback de guardado con estado loading/éxito.

### Modified Capabilities

- `exam-enrollment`: Delta — `ConfigureExam.tsx` incorpora validación inline y preview; el contrato con `api.saveExam()` y el modelo `Examen` NO cambia (solo la UI/presentación de configuración).

## Impact

- Archivo principal modificado: `frontend/src/screens/ConfigureExam.tsx`
- Archivos nuevos (componentes extraídos, colocalización en `screens/admin/components/` según patrón C-43):
  - `frontend/src/screens/admin/components/DetectoresSelector.tsx`
  - `frontend/src/screens/admin/components/ExamenResumenCard.tsx`
- Sin cambios en `api.ts` (lógica de guardado mock), `types.ts` (modelo `Examen`), `store.ts`
- Dependencias: C-40 (Button/FormField/RangeInput/SectionTitle/Card), C-43 (patrón de colocalización `screens/admin/components/`)
