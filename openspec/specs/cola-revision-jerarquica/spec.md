# cola-revision-jerarquica

## Purpose

Define la presentación drill-down jerárquica de cuatro niveles (materia → comisión → examen → persona) de la cola de revisión, que reemplaza el modelo de lista plana de `cola-revision-real` por una navegación orientada al catálogo académico. Incluye el breadcrumb clickable, los contadores "N en riesgo" por nodo, el panel de decisión humana en el nivel persona y las reglas de layout y legibilidad — manteniendo la regla dura L2.5 de que el score solo prioriza y la decisión es del revisor humano.

## Requirements

### Requirement: Navegación drill-down de 4 niveles en la Cola de revisión

`Revisor.tsx` SHALL presentar las sesiones de alto riesgo (`score >= UMBRAL_COLA_REVISION`) como una navegación drill-down jerárquica de cuatro niveles: Nivel 1 Materias, Nivel 2 Comisiones, Nivel 3 Exámenes, Nivel 4 Personas en riesgo. El nivel actual SHALL derivarse de un estado de path `{ materia?, comision?, examen? }`. La fuente de datos SHALL ser `api.listarSesionesProctoring()` (dual real/mock) enriquecida con `joinExamInfo` y filtrada por umbral. Esta presentación REEMPLAZA el modelo de lista plana previo.

#### Scenario: Nivel 1 lista materias con contador
- **WHEN** el revisor entra a `/revisor` y hay sesiones de alto riesgo
- **THEN** se muestran cards de las materias que tienen sesiones en riesgo, cada una con un contador "N en riesgo"

#### Scenario: Drill-down hasta personas
- **WHEN** el revisor hace click en una materia, luego en una comisión, luego en un examen
- **THEN** el contenido baja a Nivel 2 (comisiones), Nivel 3 (exámenes) y Nivel 4 (personas en riesgo de ese examen), cada nodo intermedio con su contador "N en riesgo"

#### Scenario: Nivel persona muestra métricas de la sesión
- **WHEN** el revisor llega al Nivel 4 de un examen
- **THEN** se muestra una card por sesión (persona) con score, eventos y discrepancias, y una acción para ver el detalle completo

#### Scenario: Sesiones sin examen asociado no se pierden
- **WHEN** una sesión de alto riesgo no tiene `exam_id` resoluble en el catálogo
- **THEN** aparece agrupada bajo un nodo "Sin examen asociado" navegable en el drill-down

### Requirement: Breadcrumb clickable y navegación de regreso

`Revisor.tsx` SHALL mostrar un breadcrumb (Materias › Materia › Comisión › Examen) en su propia fila, encima del contenido del nivel. Los segmentos previos al nivel actual SHALL ser clickables y, al activarse, recortar el path al nivel correspondiente. SHALL existir además un botón "Volver" que sube un nivel.

#### Scenario: Volver a un nivel anterior por breadcrumb
- **WHEN** el revisor está en Nivel 4 y hace click en el segmento "Materia" del breadcrumb
- **THEN** la navegación vuelve al Nivel 2 (comisiones de esa materia) recortando el path

#### Scenario: Botón volver sube un nivel
- **WHEN** el revisor está en Nivel 3 y pulsa "Volver"
- **THEN** la navegación vuelve al Nivel 2

### Requirement: Detalle y decisión humana en el nivel persona

Al seleccionar una persona en el Nivel 4, `Revisor.tsx` SHALL ofrecer el detalle completo reutilizando `ProctoringSessionDetail` (navegación a `/admin/proctoring-session-detail` vía `setProctoringSessionId`) y un panel de decisión del revisor con tres acciones en palabras llanas. Al resolver, SHALL llamar `setDecisionRevisor(id, decision)`, mostrar un toast y quitar la persona de la vista. El sistema NUNCA sanciona automáticamente: el texto del panel SHALL dejar claro que el score solo prioriza y la decisión es del revisor.

#### Scenario: Ver detalle completo reusa ProctoringSessionDetail
- **WHEN** el revisor hace click en "Ver detalle" de una persona
- **THEN** se llama `setProctoringSessionId(sesion.id)` y se navega a `/admin/proctoring-session-detail`

#### Scenario: Resolución registrada en store
- **WHEN** el revisor elige una de las tres acciones de decisión
- **THEN** se llama `setDecisionRevisor(sesion.id, decision)`, se muestra un toast y la persona desaparece de la vista

### Requirement: Layout limpio sin solapamientos

La pantalla SHALL usar un layout basado en flex/grid con gaps y cards con padding, sin elementos `absolute` montados sobre el texto. El breadcrumb SHALL ocupar su propia fila. La pantalla SHALL renderizarse sin solapamientos visuales a 1440px, 1280px y 1024px de ancho. No SHALL usar `window.confirm`/`window.alert`. El texto visible NO SHALL contener códigos `C-NN`, la cadena "L2.5", ni nombres de repositorios externos.

#### Scenario: Sin solapamientos a 1440 y 1280
- **WHEN** la pantalla se renderiza a 1440x1000 y a 1280x800 en cualquier nivel del drill-down
- **THEN** no hay texto ni badges superpuestos; las cards se distribuyen en una grilla que colapsa limpia

#### Scenario: Componentes por debajo del límite de líneas
- **WHEN** se revisa cada archivo de la pantalla (`Revisor.tsx` y los componentes en `screens/proctoring/`)
- **THEN** cada archivo tiene ≤ 400 líneas
