## Why

El harness de diagnóstico (`/admin/detection-test`) emite eventos con severidad pero no acumula ningún score de riesgo: el admin no puede calibrar cómo un escenario de prueba se traduce en riesgo porcentual, ni saber cuándo una sesión real superaría el umbral institucional de revisión humana. El modelo de pesos (`PESO_SCORE`) ya existe en `Examen.tsx` y el store ya tiene `addScore`/`scorePropio`, pero el harness no los usa.

## What Changes

- **Medidor de riesgo en vivo**: barra/gauge dentro del harness que acumula el peso (`PESO_SCORE`) de cada evento emitido durante la sesión de diagnóstico y muestra el % resultante con color escalado (verde → amarillo → rojo).
- **Botón RESET del medidor**: resetea el score acumulado del harness a 0 sin interrumpir la cámara ni el motor. Se integra junto al "Resetear estado" existente o como acción propia del widget de riesgo.
- **Umbral configurable**: input numérico (0–100 %) que define el umbral de riesgo institucional. Cuando el score acumulado supera el umbral, el medidor se destaca visualmente con un indicador "Superaría el umbral — priorizaría para revisión humana" (semántica L2.5 — prioriza, no sanciona).
- **Extracción de `PESO_SCORE` a módulo compartido**: mover la constante de `Examen.tsx:27` a `frontend/src/proctoring/riskWeights.ts` (o al catálogo de actividad) para que tanto `Examen.tsx` como `AdminDetectionHarness.tsx` la importen desde el mismo lugar. Los valores NO cambian.
- **Banner diagnóstico intacto**: el banner existente de modo diagnóstico (C-29/C-30) se mantiene sin modificación; el medidor de riesgo se agrega como widget adicional en la UI del harness.

## Capabilities

### New Capabilities
- `harness-risk-meter`: Medidor de riesgo en vivo en el harness de diagnóstico — acumulador de score, gauge visual, reset y umbral configurable.

### Modified Capabilities
- `admin-detection-test-harness`: Integración del widget de riesgo y extracción de `PESO_SCORE` compartido. El harness ahora muestra el score acumulado y el umbral institucional configurable.

## Impact

- `frontend/src/proctoring/riskWeights.ts` — **archivo nuevo**: exporta `PESO_SCORE` (mismos valores, mismo tipo `Record<Severidad, number>`).
- `frontend/src/screens/Examen.tsx` — importa `PESO_SCORE` desde `riskWeights.ts` en lugar de definirlo localmente (sin cambio de valores ni comportamiento).
- `frontend/src/screens/AdminDetectionHarness.tsx` — agrega estado local `harnessScore` (número, inicia en 0), `riskThreshold` (número, por defecto 60), widget de riesgo con gauge + reset + umbral. Acumula score en el callback del sink al recibir cada evento.
- No se toca el flujo real de examen (`Examen.tsx`) más allá del import de `PESO_SCORE`.
- No se modifica `store.ts` ni `scorePropio` del alumno — el medidor del harness usa estado local del componente, aislado del store real.
