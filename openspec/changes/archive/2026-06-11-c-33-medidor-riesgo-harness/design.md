## Context

El harness de diagnóstico (`AdminDetectionHarness`, `/admin/detection-test`) emite eventos vía `LocalHarnessEventSink → VisionPipeline → StateTransitionRules` y los muestra en un log. Cada evento tiene una `severidad` (`Severidad = 'baseline' | 'baja' | 'media' | 'alta' | 'critica'`).

El modelo de score ya está implementado en producción:
- `PESO_SCORE: Record<Severidad, number>` definido localmente en `Examen.tsx:27` con valores `{ baseline:0, baja:5, media:12, alta:22, critica:30 }`.
- `store.scorePropio` + `store.addScore(delta)` (capped a 100) en `store.ts`.
- `Examen.tsx` los usa en el loop de eventos (líneas 156–157).

El harness no usa `addScore` ni muestra ningún score. El admin no tiene retroalimentación de "cuánto riesgo generaría este escenario" al hacer diagnósticos.

## Goals / Non-Goals

**Goals:**
- Mostrar un medidor de riesgo acumulado (%) en tiempo real dentro del harness, usando los mismos pesos que el examen real.
- Permitir resetear el acumulador sin interrumpir la cámara/motor.
- Agregar un input de umbral configurable (0–100 %) con feedback visual cuando el riesgo supera el umbral ("priorizaría para revisión humana").
- Extraer `PESO_SCORE` a un módulo compartido para eliminar la duplicación entre `Examen.tsx` y `AdminDetectionHarness.tsx`.

**Non-Goals:**
- Modificar la semántica de score del examen real (`store.scorePropio` ni `addScore`).
- Agregar persistencia del score del harness (es efímero — solo vale durante la sesión de diagnóstico).
- Cambiar los valores de `PESO_SCORE` (los pesos son parte del dominio y están fijos por ahora).
- Mostrar el medidor en ninguna pantalla fuera del harness.
- Emitir ningún veredicto, sanción ni acción automática (L2.5: el sistema siempre prioriza, nunca sanciona).

## Decisions

### D-1: Acumulador local vs. store global

**Decisión**: estado local del componente (`useState<number>`) en `AdminDetectionHarness`.

**Alternativa descartada**: usar `store.scorePropio` + `store.addScore`. El store es el canal de comunicación entre `Examen.tsx` (alumno) y el panel del proctor. El harness es una herramienta aislada de diagnóstico (D-4 de aislamiento), y mezclar el score de diagnóstico con el score real del alumno crearía interferencia de estado entre pantallas. Además, `store.resetSesion()` borra también `examenActivo` y `anomaliasVivo`, lo cual es demasiado destructivo para un simple reset de medidor.

**Resultado**: `const [harnessScore, setHarnessScore] = useState(0)` + `const [riskThreshold, setRiskThreshold] = useState(60)` en `AdminDetectionHarness`. El reset es trivial: `setHarnessScore(0)`. El store Zustand queda intacto.

### D-2: Punto de acumulación del score

**Decisión**: acumular en el callback `onEvent` del `LocalHarnessEventSink`, que ya recibe `severidad` como string.

`LocalHarnessEventSink.onEvent` es el punto donde el harness ya registra cada evento en `logEntries` y opcionalmente en `anomaliasVivo`. Es el lugar natural para también actualizar `harnessScore`:

```ts
setHarnessScore((prev) => Math.min(100, prev + PESO_SCORE[args.severidad as Severidad]));
```

El callback es stable (definido con `useCallback`) y el setter de estado de React garantiza updates correctos sin stale closure.

### D-3: Extracción de PESO_SCORE

**Decisión**: nuevo archivo `frontend/src/proctoring/riskWeights.ts` que exporta `PESO_SCORE`.

**Motivo**: `riskWeights.ts` pertenece semánticamente a `proctoring/` (es parte del motor de evaluación de riesgo). `Examen.tsx` importará desde allí; `AdminDetectionHarness.tsx` también. Los valores no cambian. El nombre `riskWeights` es descriptivo y no colisiona con ningún archivo existente.

**Alternativa considerada**: exportar desde `suspiciousActivityCatalog.ts`. Descartado porque el catálogo define los tipos de evento y sus severidades por defecto, no los pesos de score — son concerns distintos.

### D-4: Widget de riesgo — diseño visual

**Decisión**: widget dedicado ("Medidor de riesgo") como `<Card>` en la columna izquierda del harness (área de controles/configuración), por encima o por debajo del card de "Resetear estado".

Contiene:
- **Gauge / barra de progreso**: `<div>` con ancho `harnessScore%` y color condicional:
  - Verde (`bg-success`) cuando `harnessScore < riskThreshold`
  - Amarillo (`bg-warning`) cuando `harnessScore >= riskThreshold * 0.7` y `< riskThreshold`
  - Rojo (`bg-error`) cuando `harnessScore >= riskThreshold`
- **Porcentaje**: texto prominente `{harnessScore}%` con variante de color acorde.
- **Indicador de umbral superado**: banner/badge con `"Superaría el umbral — priorizaría para revisión humana"` visible solo cuando `harnessScore >= riskThreshold`. Usa el ícono `flag` y tono `error` para visibilidad.
- **Input de umbral**: `<input type="number" min="1" max="100">` con label "Umbral de riesgo (%)". Valor por defecto: 60.
- **Botón RESET**: `<Button variant="outline" icon="restart_alt">Resetear riesgo</Button>`. Habilitado siempre (no solo en `running`) porque resetear el score es una operación de diagnóstico válida en cualquier estado.

**Por qué no usar la barra de progreso HTML nativa (`<progress>`)**: menos control visual/de color condicional. Una `<div>` con Tailwind es consistente con el resto de la UI del harness.

### D-5: Semántica del umbral — regla L2.5

El umbral configurable en el harness es **solo diagnóstico**: ayuda al admin a calibrar qué tipo de sesión superaría el umbral institucional (y por ende iría a revisión humana en producción). El medidor nunca ejecuta ninguna acción — solo cambia el estado visual. El texto del indicador dice explícitamente "priorizaría para revisión humana" (no "sanciona", no "bloquea").

### D-6: Reset integrado vs. botón separado

**Decisión**: botón propio dentro del widget de riesgo ("Resetear riesgo"), separado del botón "Resetear estado" que ya existe para las reglas de transición.

**Motivo**: "Resetear estado" recrea el pipeline (`pipelineRef`), reseteando la máquina de estados de visión. "Resetear riesgo" solo pone `harnessScore = 0`. Son operaciones distintas: un admin puede querer resetear el score (para medir un escenario nuevo) sin reiniciar el pipeline. Tenerlos juntos causaría confusión.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| El score del harness llega a 100 rápidamente (cap) y queda estancado, haciendo el medidor poco útil para sesiones largas de diagnóstico. | El reset es siempre accesible y visible. La semántica de cap-a-100 es intencional (refleja el comportamiento real del examen). Documentado en el tooltip del widget. |
| `args.severidad` en `LocalHarnessEventSink.onEvent` es `string`, no `Severidad`. Cast a `Severidad` puede ser inseguro si llega un valor inesperado. | `PESO_SCORE[args.severidad as Severidad]` devuelve `undefined` si el valor no es una clave válida. Se resuelve con `PESO_SCORE[args.severidad as Severidad] ?? 0` para que valores inválidos no sumen nada (fail-safe). |
| Un admin con umbral en 0 vería el banner "superó el umbral" desde el primer evento. | Validar `riskThreshold >= 1` en el input; si se ingresa 0 o negativo, forzar mínimo a 1. |
| El refactor de `PESO_SCORE` puede romperse si `Examen.tsx` falla en importar desde `riskWeights.ts`. | El cambio es mecánico (mover la constante, actualizar el import). TypeScript con `tsc --noEmit` detecta cualquier error antes de merge. |

## Open Questions

- ¿Debería el umbral por defecto ser configurable vía una constante exportada (ej. `DEFAULT_RISK_THRESHOLD = 60`) en `riskWeights.ts`? Por ahora se deja hardcodeado en 60 en el componente; si el backend (C-07 `exam-config`) expone este umbral en el futuro, se puede leer desde allí.
- ¿El botón "Resetear riesgo" debería aparecer también en el panel de acciones principal (junto a Iniciar/Detener) para mayor visibilidad? Por ahora queda dentro del widget de riesgo para mantener agrupada la UX del medidor.
