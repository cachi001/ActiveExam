## ADDED Requirements

### Requirement: Acumulador de score de riesgo en el harness
El harness de diagnóstico SHALL mantener un acumulador local de score de riesgo (`harnessScore`, entero 0–100) que se incrementa con el peso `PESO_SCORE[severidad]` de cada evento emitido durante la sesión activa. El acumulador es local al componente (no usa `store.scorePropio`) y se initializa en 0 al montar el componente.

#### Scenario: score se incrementa por cada evento emitido
- **WHEN** el pipeline emite un evento con severidad `media` (peso 12)
- **THEN** `harnessScore` SHALL aumentar en 12 (o hasta el cap de 100 si ya está cerca)

#### Scenario: cap a 100
- **WHEN** `harnessScore` ya es 90 y llega un evento con peso 22 (alta)
- **THEN** `harnessScore` SHALL ser 100 (no superar el cap)

#### Scenario: valor inválido de severidad no rompe el acumulador
- **WHEN** el sink recibe un evento cuya `severidad` no es una clave válida de `PESO_SCORE`
- **THEN** `harnessScore` SHALL permanecer sin cambios (delta = 0, fail-safe con `?? 0`)

### Requirement: Medidor visual de riesgo con color escalado
El harness SHALL mostrar un widget "Medidor de riesgo" con una barra de progreso cuyo color escala según el nivel relativo al umbral configurado.

#### Scenario: barra verde cuando riesgo bajo el umbral
- **WHEN** `harnessScore < riskThreshold`
- **THEN** la barra SHALL mostrar color verde (`bg-success` o equivalente Tailwind del sistema de diseño)

#### Scenario: barra amarilla en zona de advertencia
- **WHEN** `harnessScore >= riskThreshold * 0.7` y `harnessScore < riskThreshold`
- **THEN** la barra SHALL mostrar color amarillo (`bg-warning` o equivalente)

#### Scenario: barra roja al superar el umbral
- **WHEN** `harnessScore >= riskThreshold`
- **THEN** la barra SHALL mostrar color rojo (`bg-error` o equivalente)

#### Scenario: porcentaje numérico visible
- **WHEN** el medidor es visible
- **THEN** SHALL mostrar `{harnessScore}%` como texto prominente junto a la barra

### Requirement: Indicador de umbral superado (semántica L2.5)
Cuando el score supera el umbral configurado, el medidor SHALL mostrar un banner/badge de advertencia indicando que la sesión priorizaría para revisión humana. Este indicador NO implica sanción ni decisión automática.

#### Scenario: banner visible al superar el umbral
- **WHEN** `harnessScore >= riskThreshold`
- **THEN** SHALL aparecer un indicador con el texto "Superaría el umbral — priorizaría para revisión humana" (o equivalente en lenguaje claro)

#### Scenario: banner oculto por debajo del umbral
- **WHEN** `harnessScore < riskThreshold`
- **THEN** el indicador de umbral superado NO SHALL ser visible

#### Scenario: el indicador no ejecuta ninguna acción
- **WHEN** el indicador de umbral superado está visible
- **THEN** SHALL ser solo informativo — no bloquea la sesión, no envía alertas, no modifica el estado del motor

### Requirement: Umbral de riesgo configurable
El widget SHALL incluir un input numérico para configurar el umbral de riesgo (1–100 %). El valor por defecto SHALL ser 60.

#### Scenario: input acepta valores entre 1 y 100
- **WHEN** el admin ingresa un valor entre 1 y 100 en el input de umbral
- **THEN** `riskThreshold` SHALL actualizarse al nuevo valor y el color de la barra SHALL recalcularse inmediatamente

#### Scenario: input rechaza valores menores a 1
- **WHEN** el admin ingresa 0 o un valor negativo
- **THEN** el umbral SHALL forzarse al mínimo 1 (sanitización en el onChange)

#### Scenario: input rechaza valores mayores a 100
- **WHEN** el admin ingresa un valor mayor a 100
- **THEN** el umbral SHALL forzarse al máximo 100 (sanitización en el onChange)

### Requirement: Botón RESET del medidor de riesgo
El widget SHALL incluir un botón "Resetear riesgo" que pone `harnessScore` a 0 sin detener la cámara, el motor ni el pipeline.

#### Scenario: reset en estado running
- **WHEN** el harness está en estado `running` y el admin presiona "Resetear riesgo"
- **THEN** `harnessScore` SHALL volver a 0 y la barra SHALL reflejar el nuevo valor inmediatamente, sin interrumpir el procesamiento de frames

#### Scenario: reset disponible en estado stopped
- **WHEN** el harness está en estado `stopped` o `idle`
- **THEN** el botón "Resetear riesgo" SHALL estar habilitado (a diferencia del botón "Resetear estado" que está deshabilitado en este estado)

#### Scenario: reset no afecta el log de eventos
- **WHEN** el admin presiona "Resetear riesgo"
- **THEN** el log de eventos (`logEntries`) y las anomalías del store (`anomaliasVivo`) SHALL permanecer sin cambios

### Requirement: PESO_SCORE en módulo compartido
Los pesos de score (`PESO_SCORE`) SHALL residir en `frontend/src/proctoring/riskWeights.ts` y ser importados desde allí por `Examen.tsx` y `AdminDetectionHarness.tsx`.

#### Scenario: no hay duplicación de PESO_SCORE
- **WHEN** se hace una búsqueda de `PESO_SCORE` en el codebase
- **THEN** SHALL existir exactamente una definición (en `riskWeights.ts`) y dos imports (en `Examen.tsx` y `AdminDetectionHarness.tsx`)

#### Scenario: los valores de PESO_SCORE no cambian
- **WHEN** se extrae PESO_SCORE a riskWeights.ts
- **THEN** los valores SHALL ser idénticos a los originales: `{ baseline:0, baja:5, media:12, alta:22, critica:30 }`

#### Scenario: Examen.tsx sigue funcionando tras el refactor
- **WHEN** Examen.tsx importa PESO_SCORE desde riskWeights.ts
- **THEN** el comportamiento de score en el examen real SHALL ser idéntico al anterior (tsc --noEmit sin errores)
