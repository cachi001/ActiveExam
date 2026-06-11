## MODIFIED Requirements

### Requirement: SessionDetail usa SectionTitle para encabezados de secciones internas
El encabezado "Eventos discretos" en `SessionDetail.tsx` SHALL usar `SectionTitle` del design system con un sub que indique la cantidad de eventos, en lugar de un `<h3>` con clases CSS manuales. Este cambio aplica al archivo `frontend/src/screens/SessionDetail.tsx` que forma parte de la shell de revisión.

#### Scenario: Encabezado de eventos con conteo en sub
- **WHEN** el revisor ve el detalle de una sesión con eventos
- **THEN** el encabezado "Eventos discretos" usa `SectionTitle` con `sub={`${sel.eventos.length} eventos`}` y tipografía consistente con el resto del design system (title-lg font-headline)

#### Scenario: Encabezado sin sub en lista vacía
- **WHEN** la sesión no tiene eventos discretos
- **THEN** `SectionTitle` muestra "Eventos discretos" sin sub (o sub vacío) — no se rompe el layout

#### Scenario: Consistencia visual con otras secciones de staff
- **WHEN** el revisor navega entre Revisor.tsx y SessionDetail.tsx
- **THEN** ambas pantallas usan el mismo componente `SectionTitle` para sus encabezados de sección, generando un ritmo visual coherente
