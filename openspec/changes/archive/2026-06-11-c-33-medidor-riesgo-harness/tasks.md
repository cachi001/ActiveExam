## 1. Módulo compartido riskWeights

- [x] 1.1 Crear `frontend/src/proctoring/riskWeights.ts` exportando `PESO_SCORE: Record<Severidad, number>` con los valores originales `{ baseline:0, baja:5, media:12, alta:22, critica:30 }` e importando `Severidad` desde `../lib/types`
- [x] 1.2 Eliminar la definición local de `PESO_SCORE` en `Examen.tsx` (línea 27) y agregar el import desde `../proctoring/riskWeights`
- [x] 1.3 Verificar que `tsc --noEmit` pasa sin errores tras el refactor de `Examen.tsx`

## 2. Estado local del medidor en AdminDetectionHarness

- [x] 2.1 Agregar import de `PESO_SCORE` desde `../proctoring/riskWeights` en `AdminDetectionHarness.tsx`
- [x] 2.2 Agregar import de `Severidad` desde `../lib/types` si no está ya importado
- [x] 2.3 Declarar estado `const [harnessScore, setHarnessScore] = useState(0)` en el cuerpo del componente
- [x] 2.4 Declarar estado `const [riskThreshold, setRiskThreshold] = useState(60)` en el cuerpo del componente

## 3. Acumulación del score en el sink

- [x] 3.1 En el callback `onEvent` del `LocalHarnessEventSink` (dentro del `useCallback` que crea el sink), agregar la llamada a `setHarnessScore((prev) => Math.min(100, prev + (PESO_SCORE[args.severidad as Severidad] ?? 0)))` después del registro en `logEntries`
- [x] 3.2 Verificar que el tipo del callback incluye `args.severidad` como `string` (ya existe en la interfaz `SinkEventCallback`) — usar cast `as Severidad` con fallback `?? 0`
- [x] 3.3 Verificar que el `useCallback` del sink tiene `harnessScore` fuera de su closure (usa setter funcional `prev =>` para evitar stale closure — no necesita `harnessScore` como dependencia)

## 4. Helper de color del gauge

- [x] 4.1 Agregar función helper pura `gaugeColor(score: number, threshold: number): string` dentro del módulo (fuera del componente) que devuelve la clase Tailwind apropiada:
  - `score >= threshold` → `'bg-error'`
  - `score >= threshold * 0.7` → `'bg-warning'`
  - por defecto → `'bg-success'`
- [x] 4.2 Agregar función helper `gaugeTextColor(score: number, threshold: number): string` análoga para el color del texto porcentual (`text-error` / `text-warning` / `text-success`)

## 5. Widget de medidor de riesgo — JSX

- [x] 5.1 Agregar el `<Card>` del widget "Medidor de riesgo" en la columna izquierda del harness, por debajo del card de configuración de umbrales de visión (o en posición visible sin scroll extra)
- [x] 5.2 Implementar la barra de progreso: `<div>` outer con `bg-surface-container-high rounded-full h-3 overflow-hidden` y `<div>` inner con `style={{ width: harnessScore + '%' }}` y clase dinámica de color via `gaugeColor(harnessScore, riskThreshold)`
- [x] 5.3 Agregar el porcentaje numérico como `<span>` prominente con clase dinámica de texto via `gaugeTextColor(harnessScore, riskThreshold)` mostrando `{harnessScore}%`
- [x] 5.4 Agregar el banner de umbral superado: renderizar condicionalmente (`harnessScore >= riskThreshold`) un `<div>` con ícono `flag`, texto "Superaría el umbral — priorizaría para revisión humana" y estilo visual destacado (`bg-error-container text-on-error-container`)
- [x] 5.5 Agregar el input de umbral: `<input type="number" min="1" max="100" value={riskThreshold}>` con label "Umbral de riesgo (%)", con `onChange` que sanitiza al rango 1–100 antes de llamar `setRiskThreshold`
- [x] 5.6 Agregar el botón "Resetear riesgo": `<Button variant="outline" icon="restart_alt" onClick={() => setHarnessScore(0)}>Resetear riesgo</Button>` — siempre habilitado (no depende de `harnessState`)

## 6. Verificación visual y semántica L2.5

- [x] 6.1 Verificar que el banner de umbral superado incluye lenguaje explícito de "priorizar" (no "sancionar", no "bloquear")
- [x] 6.2 Verificar que el botón "Resetear riesgo" no interrumpe la sesión — el motor y el log siguen activos después del reset
- [x] 6.3 Verificar que el widget es visible en estado `idle` (score 0, barra verde vacía) para que el admin configure el umbral antes de iniciar
- [x] 6.4 Verificar que el botón "Resetear estado" existente (que recrea el pipeline) no resetea `harnessScore` — son independientes

## 7. Verificación TypeScript

- [x] 7.1 Ejecutar `tsc --noEmit` desde `frontend/` y confirmar 0 errores tras todos los cambios
- [x] 7.2 Confirmar que `PESO_SCORE` tiene exactamente una definición (en `riskWeights.ts`) y dos imports (`Examen.tsx` y `AdminDetectionHarness.tsx`) — búsqueda en el codebase
