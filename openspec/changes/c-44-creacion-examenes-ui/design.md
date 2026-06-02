## Context

`ConfigureExam.tsx` (103 líneas tras C-40) es el formulario de creación/edición de exámenes para el rol `admin_examenes`. Actualmente usa las primitivas del design system (FormField, RangeInput, Button, Card, SectionTitle) instaladas por C-40, pero la lógica de validación es un único `alert()` para el nombre faltante y no hay feedback previo a guardar. El componente es un único archivo monolítico sin sub-componentes. La lógica de guardado vive en `api.saveExam()` (mock) y el modelo de datos es `Examen` de `types.ts` — ambos fuera del alcance de este change.

C-43 estableció el patrón de colocalización de componentes admin en `frontend/src/screens/admin/components/`. Este change sigue ese mismo patrón.

## Goals / Non-Goals

**Goals:**
- Reemplazar `alert()` por validación inline usando el slot `error` de `FormField`
- Mostrar un preview/resumen del examen antes de confirmar (componente `ExamenResumenCard`)
- Extraer `DetectoresSelector` como componente reutilizable
- Feedback de guardado (spinner loading + mensaje de éxito)
- Botón Guardar deshabilitado mientras el form es inválido
- Layout en tres secciones con `SectionTitle`
- Semántica L2.5 en el resumen (detectores priorizan, no sancionan; retención Ley 25.326)

**Non-Goals:**
- No modificar `api.saveExam()` ni el modelo `Examen`
- No agregar nuevos campos al formulario
- No cambiar el flujo de navegación post-guardado
- No agregar validación server-side (ese scope es del backend C-07)
- No modificar `store.ts` ni la lógica de estado global

## Decisions

### Decisión 1: Validación inline con estado derivado, sin librería externa

**Elección**: Un objeto de errores `Record<string, string>` calculado como estado derivado via `useMemo` desde el estado del form. Cada campo que falla produce una clave con su mensaje de error. El slot `error` de `FormField` lo consume directamente.

**Alternativas consideradas**:
- React Hook Form / Zod: overhead innecesario para un formulario de ~7 campos con reglas simples y sin integración de backend en este change.
- `useState` para errores manuales (set por campo): requiere sincronizar manualmente con el estado del form, propenso a estados inconsistentes.

**Reglas de validación**:
| Campo | Regla | Mensaje de error |
|---|---|---|
| `nombre` | No vacío (trim) | "El nombre del examen es requerido" |
| `catedra` | No vacía (trim) | "La cátedra es requerida" |
| `inicio` | Fecha futura (> now + 5 min) | "El inicio debe ser en el futuro" |
| `duracion_min` | Entre 30 y 180 | "La duración debe estar entre 30 y 180 minutos" |
| `umbral_score` | Entre 30 y 90 | "El umbral debe estar entre 30 y 90" |
| `retencion_dias` | Entre 7 y 90 | "La retención debe estar entre 7 y 90 días" |

El botón Guardar queda `disabled` si `Object.keys(errors).length > 0`. Mientras `guardando === true`, el botón muestra spinner (comportamiento ya existente).

### Decisión 2: Preview como componente `ExamenResumenCard` siempre visible bajo el form

**Elección**: La card de resumen se renderiza siempre visible bajo las secciones del form (antes de los botones), no como modal ni paso separado. Se actualiza en tiempo real mientras el admin escribe. Si el form es inválido, la card muestra un indicador de campos pendientes en vez de los valores erróneos.

**Alternativas consideradas**:
- Modal de confirmación: agrega un paso extra de interacción; innecesario para un form con preview siempre visible.
- Layout lateral (grid 2 cols): complica la responsividad en móvil; el admin de exámenes trabaja típicamente en desktop pero el patrón del proyecto es mobile-first.
- Preview solo al hacer submit: pierde el valor de feedback en tiempo real.

**Contenido del resumen** (texto en lenguaje humano):
```
Examen: {nombre || "—"}
Cátedra: {catedra || "—"}
Inicio: {fecha formateada en español, ej. "2 jun 2026, 09:00"}
Duración: {duracion_min} minutos
Detectores activos: {detectores.length} de {DETECTORES.length} (priorizan para revisión humana, no sancionan)
Umbral de cola de revisión: {umbral_score}%
Retención de evidencia: {retencion_dias} días (Ley 25.326)
```

### Decisión 3: `DetectoresSelector` como componente extraído, colocado en `screens/admin/components/`

**Elección**: El grupo de checkboxes de detectores activos se extrae a `DetectoresSelector.tsx`. Props: `value: TipoEvento[]`, `onChange: (detectores: TipoEvento[]) => void`. Muestra internamente el resumen "N de M detectores activos" para orientar al admin. La lista `DETECTORES` se importa desde el screen padre o se define localmente en el componente.

**Alternativas consideradas**:
- Mantener los checkboxes inline en ConfigureExam: el componente ya tiene 103 líneas y crece con validación + preview; extracción mejora la legibilidad.
- Extraer como un hook + render prop: over-engineering para el caso de uso actual.

### Decisión 4: Layout en secciones con `SectionTitle`

Tres secciones delimitadas por `SectionTitle`:
1. **"Información del examen"** (`sub="Datos generales"`): nombre, cátedra, inicio, duración.
2. **"Parámetros de proctoring"** (`sub="Política de priorización y privacidad"`): umbral, detectores, retención.
3. **"Resumen del examen"** (`sub="Revisá la configuración antes de guardar"`): `ExamenResumenCard`.

Botones Cancelar/Guardar debajo de la tercera sección.

### Decisión 5: Feedback de éxito

Tras un guardado exitoso, mantener el `navigate('/admin/examenes')` existente (redirige a la lista). No agregar un toast o banner de éxito en pantalla — la navegación ya comunica el éxito. Si en el futuro se implementa un sistema de notificaciones global, este screen puede adoptarlo sin cambiar la lógica.

## Risks / Trade-offs

- **Validación de fecha futura con offset de 5 min**: si el reloj del cliente está desincronizado, el admin podría ver un falso error. Mitigación: el backend valida server-side (C-07); el frontend solo da feedback orientativo.
- **`ExamenResumenCard` siempre visible**: el form crece en altura. En pantallas pequeñas puede requerir scroll extra. Mitigación: aceptable — el admin de exámenes opera en desktop; el preview aporta más valor que el espacio que ocupa.
- **Detectores en `DETECTORES` hardcodeados**: la lista de detectores disponibles no viene del backend en este change (igual que el estado actual). Si se agrega un detector nuevo al backend, el frontend requiere actualización manual. Mitigación: fuera del scope de este change; es una limitación conocida del mock.
