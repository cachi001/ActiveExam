## Context

El pipeline de visión del cliente (C-11) está cableado en el flujo del alumno (`Examen.tsx`): instancia `MediaPipeVisionEngine`, lo conecta a `VisionPipeline` con un `EventSink` que envía al `StudentEventChannel` (C-10) y acumula en `store.anomaliasVivo`. No existe ninguna superficie de diagnóstico fuera de ese flujo. El equipo necesita una herramienta para verificar que los detectores funcionan en el hardware objetivo y que los eventos discretos se producen y registran correctamente.

El change es **exclusivamente frontend admin**, gobernanza MEDIA, herramienta diagnóstica. No toca backend, no emite eventos al API de producción, no genera evidencia criptográfica. Las reglas duras de dominio (sensor no confiable, no sanción automática) aplican igual: el harness es explícitamente un entorno de prueba, no proctoring real.

## Goals / Non-Goals

**Goals:**

- Reutilizar el pipeline existente (`MediaPipeVisionEngine`, `VisionPipeline`, `StateTransitionRules`) sin copiar ni reescribir lógica de visión.
- Proveer observabilidad diagnóstica: señales crudas por frame + eventos discretos + confirmación de registro en sink y store.
- Permitir ajuste en tiempo real de `TransitionConfig` para ejercitar umbrales.
- Aislar completamente el harness del flujo de producción (sin emisión al backend, sin sesión de alumno).

**Non-Goals:**

- No implementar liveness ni retos activos en el harness (eso es C-09, ya aplicado en el flujo alumno).
- No grabar evidencia ni generar clips (C-12 no aplica aquí).
- No conectar al `StudentEventChannel` real ni al WebSocket de producción.
- No implementar análisis de falsos positivos ni métricas agregadas (eso es C-20, reportes).
- No modificar el comportamiento del flujo del alumno en ningún caso.

## Decisions

### D-1: Reutilizar el pipeline sin duplicar — inyección de dependencias

**Decisión**: La pantalla `AdminDetectionHarness` instancia directamente `MediaPipeVisionEngine` y `VisionPipeline`, igual que el flujo del alumno (`Examen.tsx`), pero con un `EventSink` local (captura en array + `pushAnomalia` del store) en lugar del `StudentEventChannel`.

**Por qué**: `VisionPipeline` acepta `EventSink` como interfaz (DI). Crear un `LocalEventSink` que implemente la misma interfaz `{ sendEvent(...): Promise<void> }` es suficiente para interceptar todos los eventos sin cambiar una línea del pipeline. La abstracción `VisionEngine` (DD-17) garantiza que el motor es intercambiable.

**Alternativa descartada**: Crear un hook/composable wrapper que exponga el pipeline. Añade una capa de indirección innecesaria para una pantalla de diagnóstico.

**Alternativa descartada**: Mock del motor para el harness. Derrota el propósito: queremos testear el motor REAL con la cámara del admin, no un simulacro.

### D-2: EventSink local — LocalHarnessEventSink

**Decisión**: Implementar `LocalHarnessEventSink` (dentro de `AdminDetectionHarness.tsx`) que:
1. Llama a `store.pushAnomalia()` para reflejar en `anomaliasVivo` (igual que el flujo del alumno).
2. Acumula los eventos en un array de estado local (`useState`) para el log del harness.
3. Registra el resultado de cada `sendEvent` (ok / error) en el mismo array.

**Por qué**: El harness necesita observabilidad del sink que el flujo de producción no necesita. Separar las preocupaciones: el `StudentEventChannel` real no se contamina con lógica de diagnóstico.

**Riesgo**: El log local puede acumular muchos eventos en sesiones largas. **Mitigación**: limitar el array local a 200 entradas (configurable con constante) y mostrar un aviso cuando se trunca, independientemente del límite de 50 de `anomaliasVivo`.

### D-3: Reemplazo en caliente de StateTransitionRules

**Decisión**: Cuando el admin modifica `TransitionConfig`, el harness crea una nueva instancia de `StateTransitionRules` y la reemplaza en el `VisionPipeline` via `pipeline.replaceRules(newRules)`. Para no modificar `VisionPipeline` (cap C-11 ya aplicado y validado), el harness mantiene una referencia mutable a las reglas y crea un `EventSink` wrapper que delega al pipeline con las reglas actuales.

**Alternativa**: Exponer un setter en `VisionPipeline`. Requiere modificar C-11 (cambio de spec). **Descartado**: el harness es diagnóstico; modificar el pipeline de producción para soportarlo viola el principio de aislamiento.

**Implementación correcta**: El harness NO usa `VisionPipeline` directamente para el loop principal; en cambio, llama a `pipeline.onSignals(signals)` con las señales del motor, manteniendo control total sobre las reglas. O bien, recrea el `VisionPipeline` completo cuando cambia el config (costo bajo: las reglas son stateless en construcción, el motor persiste).

**Decisión final**: recrear `VisionPipeline` (con el mismo motor) al cambiar config. Simple, sin acoplamiento.

### D-4: Aislamiento de producción — sin StudentEventChannel

**Decisión**: El harness nunca instancia `StudentEventChannel` ni `ResilientStudentEventChannel`. El `LocalHarnessEventSink` no hace ninguna llamada HTTP/WS. Un comentario explícito en el código de la pantalla documenta esta restricción.

**Por qué**: Garantiza que ningún evento de diagnóstico contamine los datos de producción ni genere registros en el backend. El harness es "air-gapped" del transporte real.

### D-5: Ruta y navegación

**Decisión**: Ruta `/admin/detection-test`, entrada nueva en `STAFF_NAV` con ícono `bug_report` (Material Symbols), label "Test de detección". Se agrega al final de la lista de `STAFF_NAV` en `ui/nav.ts`.

**Por qué**: Coherente con el patrón existente de `STAFF_NAV`. El ícono `bug_report` comunica inmediatamente el propósito diagnóstico.

### D-6: Exportación del log

**Decisión**: Exportar vía `URL.createObjectURL(new Blob([JSON.stringify(log)], { type: 'application/json' }))` + `<a download>` — sin dependencias externas.

**Por qué**: El harness es una herramienta interna de demo/diagnóstico. Una dependencia de exportación externa (xlsx, etc.) está fuera de alcance.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|------------|
| El motor `MediaPipeVisionEngine` no soporta dos instancias simultáneas (worker compartido) | Documentar que el harness no debe estar abierto mientras un alumno está rindiendo en el mismo browser. En producción real, el admin usa un dispositivo distinto al del alumno. |
| Log local crece sin límite en sesiones largas | Límite de 200 entradas con aviso visual. |
| Admin confunde el harness con proctoring real | Header prominente con badge "MODO DIAGNÓSTICO — sin examen real" y ausencia de controles de sanción/evidencia. |
| Cambio frecuente de `TransitionConfig` recrea el pipeline y puede introducir un frame perdido | El motor (costoso) no se reinicia; solo las reglas (baratas). La ventana de pérdida es < 1 frame. Aceptable para diagnóstico. |

## Migration Plan

No hay datos de producción ni APIs afectadas. El deploy es:
1. Agregar la pantalla y la ruta.
2. Agregar la entrada en `STAFF_NAV`.
3. Verificar que la ruta está protegida por el guard de roles existente.

Rollback: eliminar la pantalla y revertir `nav.ts` — sin impacto en el resto del sistema.

## Open Questions

- ¿El guard de rutas admin actual verifica `admin_examenes` | `coordinador` o solo `admin_examenes`? Confirmar antes de implementar el guard de `/admin/detection-test`. (Resolución esperada en la task 1.2.)
- ¿El banner "MODO DIAGNÓSTICO" debe bloquearse por feature flag para que no aparezca en staging si se despliega? (Decisión del equipo; por defecto NO, el harness es siempre visible para admins.)
