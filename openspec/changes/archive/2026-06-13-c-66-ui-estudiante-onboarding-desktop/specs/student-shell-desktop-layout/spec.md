## ADDED Requirements

### Requirement: StudentShell usa el ancho disponible en desktop

El componente `StudentShell` SHALL aumentar el `max-width` del contenido en breakpoints desktop (`lg:` y `xl:`) para no dejar grandes franjas vacías a los lados en pantallas grandes, manteniendo el `max-width` actual en mobile (`sm:`/`md:`).

#### Scenario: Desktop ancho (xl) usa más ancho
- **WHEN** el viewport tiene >= 1280px de ancho (breakpoint `xl`)
- **THEN** el contenedor principal del `StudentShell` permite un `max-width` mayor al actual mobile (e.g. `xl:max-w-6xl` en lugar de `max-w-3xl`)

#### Scenario: Mobile mantiene layout actual
- **WHEN** el viewport tiene < 640px de ancho (breakpoint `sm`)
- **THEN** el contenedor principal del `StudentShell` mantiene el `max-width` mobile actual sin cambios

#### Scenario: Contenido legible en pantallas muy grandes
- **WHEN** el viewport tiene > 1920px de ancho
- **THEN** el contenido NO se estira a 100% del ancho — mantiene un `max-width` razonable (e.g. `2xl:max-w-7xl`) para que las líneas de texto sigan siendo legibles (~80ch máximo)

### Requirement: Contenido en grids responsive donde aplique

Las pantallas del workflow del estudiante que tienen elementos repetibles (cláusulas del consentimiento, requisitos del perfil, cards de pasos del enrollment, etc.) SHALL usar grids responsive que muestren 1 columna en mobile y 2-3 columnas en desktop, sin romper la jerarquía visual.

#### Scenario: Cláusulas del consentimiento en grid 2-cols en desktop
- **WHEN** el viewport tiene >= 640px (breakpoint `sm`) y se renderizan las cláusulas del consentimiento en `Consent.tsx`
- **THEN** las cláusulas se muestran en un grid de 2 columnas (ya existe `grid sm:grid-cols-2 gap-md` en el código actual — verificar y mantener)

#### Scenario: Pantallas de un solo bloque NO usan grid
- **WHEN** se renderiza una pantalla con un único bloque de contenido principal (e.g. confirmación de biometría)
- **THEN** ese bloque ocupa el ancho útil del shell sin forzar un grid
