## ADDED Requirements

### Requirement: `ProctoringRevisor` — lista de sesiones persistidas
El sistema SHALL proveer un componente `ProctoringRevisor` en `frontend/src/screens/ProctoringRevisor.tsx` accesible en la ruta `/admin/proctoring-sessions`. Muestra la lista de sesiones devuelta por `api.listarSesionesProctoring()`. Cada ítem de la lista SHALL mostrar: id de sesión, modo (diagnostico/examen), etiqueta (si hay), fecha `creada_en`, total_eventos, total_discrepancias y score. Un ítem seleccionado abre el detalle. El componente usa `StaffShell` con `STAFF_NAV` y reutiliza `Card`, `Badge`, `SeverityBadge`, `SectionTitle` del design system.

#### Scenario: Lista cargada al montar
- **WHEN** el componente monta
- **THEN** llama a `api.listarSesionesProctoring()` y muestra la lista; mientras carga muestra spinner

#### Scenario: Lista vacía
- **WHEN** el backend devuelve array vacío
- **THEN** muestra mensaje "No hay sesiones grabadas aún"

#### Scenario: Selección de sesión navega al detalle
- **WHEN** el usuario hace clic en una sesión de la lista
- **THEN** navega a `ProctoringSessionDetail` con el id de la sesión seleccionada

### Requirement: `ProctoringSessionDetail` — detalle completo de sesión
El sistema SHALL proveer un componente `ProctoringSessionDetail` en `frontend/src/screens/ProctoringSessionDetail.tsx`. Recibe el `id` de sesión desde la URL o el store. Llama `api.getSesionProctoring(id)` y muestra: (a) metadata de la sesión (id, modo, etiqueta, fecha, score), (b) lista de eventos con screenshot + veredicto_reinferencia + face_count_cliente vs face_count_servidor + severidad, (c) sección de biometría (liveness_ok, retos_resueltos, resultado) si existe, (d) score total con gauge (reusar el patrón de gauge del harness).

#### Scenario: Detalle cargado correctamente
- **WHEN** el componente carga con un id de sesión válido
- **THEN** muestra todos los campos de la sesión con sus eventos y biometría

#### Scenario: Screenshot por evento mostrado
- **WHEN** un evento tiene `screenshot_base64` no nulo
- **THEN** muestra la imagen del screenshot en una miniatura expandible; si `screenshot_base64` es nulo muestra "Sin captura"

#### Scenario: Veredicto de re-inferencia visible y diferenciado
- **WHEN** un evento tiene `veredicto_reinferencia`
- **THEN** muestra el veredicto con color semántico: 'coincide' → success-container, 'discrepancia' → error-container, 'sin_referencia' / 'error' → surface-container

#### Scenario: Comparación face_count cliente vs servidor
- **WHEN** un evento tiene `face_count_cliente` y `face_count_servidor`
- **THEN** ambos valores se muestran juntos ("Cliente: N · Servidor: M"); si difieren se muestra badge de discrepancia

#### Scenario: Sección biometría ausente si no hay datos
- **WHEN** `biometria` es null en la respuesta del backend
- **THEN** la sección de biometría muestra "Sin verificación biométrica registrada"

### Requirement: Disclaimer L2.5 en la vista de revisión
La vista de detalle SHALL mostrar un disclaimer inamovible visible al revisor: "Este sistema (L2.5) nunca sanciona automáticamente. El score es un indicador de prioridad para revisión humana. La decisión disciplinaria es siempre del revisor." El disclaimer se muestra en un banner informativo en la parte superior de la pantalla de detalle.

#### Scenario: Disclaimer siempre visible
- **WHEN** el revisor abre cualquier sesión de detalle
- **THEN** el disclaimer L2.5 es visible antes del contenido de la sesión, no colapsable

### Requirement: Datos sensibles — screenshots sin logging
Los screenshots (campo `screenshot_base64`) recibidos del backend SHALL ser renderizados directamente en la UI como `<img src={...}>`. El sistema NO SHALL registrar el contenido de `screenshot_base64` en `console.log`, `localStorage`, ni en ningún store global persistente (Zustand, sessionStorage). Los datos quedan solo en el estado local del componente durante la sesión de UI.

#### Scenario: Screenshot no se loguea en consola
- **WHEN** se recibe y muestra un evento con screenshot_base64
- **THEN** el string base64 no aparece en console.log ni console.debug

### Requirement: Ruta `/admin/proctoring-sessions` registrada en el router
El sistema SHALL agregar la ruta `/admin/proctoring-sessions` en `frontend/src/lib/router.tsx` con componente `ProctoringRevisor`, accesible para roles `admin_examenes`, `coordinador` y `revisor`. La ruta de detalle `/admin/proctoring-sessions/:id` carga `ProctoringSessionDetail`.

#### Scenario: Ruta accesible
- **WHEN** un usuario con rol `admin_examenes` navega a `/admin/proctoring-sessions`
- **THEN** se renderiza `ProctoringRevisor` correctamente
