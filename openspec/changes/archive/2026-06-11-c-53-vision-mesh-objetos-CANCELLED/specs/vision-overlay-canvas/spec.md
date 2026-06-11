# Spec — vision-overlay-canvas (delta C-53)

> El overlay de diagnóstico deja de pintar el mesh verde por defecto; el mesh completo (468) pasa a ser opt-in solo-staff. La cámara del alumno durante el examen NUNCA dibuja puntos sobre su cara.

## MODIFIED Requirements

### Requirement: Dibujar landmarks del Face Mesh
El overlay de diagnóstico (harness de staff) SHALL renderizar landmarks del Face Mesh SOLO bajo demanda explícita del staff. Por defecto (mesh completo desactivado) el overlay NO SHALL pintar puntos del mesh sobre la cara; SHALL conservar el bounding box del rostro y el indicador de mirada (gaze) como ayudas mínimas de diagnóstico. El mesh completo de 468 puntos SHALL dibujarse únicamente cuando el toggle de staff (`showFullMesh`) está activado.

#### Scenario: por defecto no se pinta mesh sobre la cara
- **WHEN** el overlay renderiza un frame con `showFullMesh === false`
- **THEN** NO se dibujan puntos del mesh (ni el subconjunto verde de 68 puntos), pero SÍ se dibujan el bounding box del rostro y el indicador de gaze

#### Scenario: mesh completo (468) es opt-in del staff
- **WHEN** el staff activa el toggle `showFullMesh` y `faceMesh.landmarks.length === 468`
- **THEN** el overlay dibuja los 468 puntos del mesh completo

#### Scenario: vector gaze como línea/flecha
- **WHEN** `faceMesh.gaze` is available
- **THEN** a directional indicator (line or arrow) SHALL be drawn from the face center in the direction of the normalized gaze vector `{x, y}` scaled to canvas pixels

#### Scenario: landmarks no disponibles — no se dibuja mesh
- **WHEN** `faceMesh` is null or `faceMesh.landmarks` is empty
- **THEN** no landmark points or gaze indicator SHALL be drawn

## ADDED Requirements

### Requirement: El examen del alumno no dibuja overlay sobre la cara
El flujo de examen del alumno SHALL ejecutar el pipeline de visión SIN montar el overlay de canvas sobre el video. NINGÚN punto de mesh ni bounding box SHALL dibujarse sobre la cara del alumno durante el examen; el overlay de diagnóstico queda restringido al harness de staff.

#### Scenario: examen corre sin overlay
- **WHEN** el alumno rinde un examen con proctoring activo
- **THEN** la detección y emisión de eventos ocurre en segundo plano sin renderizar ningún canvas overlay con puntos sobre su cara

#### Scenario: overlay reservado al harness de staff
- **WHEN** se revisa el flujo de examen del alumno
- **THEN** el componente de overlay de visión NO está instanciado en ese flujo (solo en el harness de diagnóstico)
