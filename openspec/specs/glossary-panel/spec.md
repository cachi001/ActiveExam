# glossary-panel

## Purpose

Define el componente `<GlossaryPanel>` — un modal accesible que lista todos los términos del diccionario `GLOSSARY` con sus definiciones y referencias legales, disponible desde el footer de la shell. Es el contrapunto al componente `<Term>` (tooltip puntual): cuando el usuario quiere ver todo el vocabulario técnico en un solo lugar, abre este panel desde cualquier pantalla de la aplicación.

## Requirements

### Requirement: Panel de glosario completo accesible desde el footer
El sistema SHALL proveer un componente `<GlossaryPanel>` en `frontend/src/ui/GlossaryPanel.tsx` que muestre un modal con la lista completa de términos del diccionario `GLOSSARY`, cada uno con su `label`, `definition` y `legalRef` (si existe). El panel SHALL ser activable mediante un botón "Glosario" en el footer de la shell (`shells.tsx`).

#### Scenario: Botón de glosario en el footer
- **WHEN** cualquier usuario visualiza cualquier pantalla de la aplicación
- **THEN** el footer contiene un botón o enlace con el texto "Glosario" (o icono "?" con label accesible)

#### Scenario: Modal se abre al activar el botón
- **WHEN** el usuario hace click/tap en el botón de glosario del footer
- **THEN** se abre un modal con el título "Glosario de términos" que lista todos los términos del diccionario

#### Scenario: Modal lista todos los términos con definición
- **WHEN** el GlossaryPanel está abierto
- **THEN** muestra las 7 entradas del GLOSSARY, cada una con su `label` como título, su `definition` como texto principal, y su `legalRef` como texto secundario (si existe)

#### Scenario: Modal cierra al presionar Escape o al hacer click fuera
- **WHEN** el GlossaryPanel está abierto y el usuario presiona Escape o hace click en el overlay
- **THEN** el modal se cierra

#### Scenario: Modal accesible — role="dialog"
- **WHEN** el GlossaryPanel está abierto
- **THEN** el elemento del modal tiene `role="dialog"`, `aria-modal="true"`, y `aria-label="Glosario de términos"`

#### Scenario: GlossaryPanel no agrega dependencias externas de modal
- **WHEN** se inspecciona el bundle del frontend
- **THEN** no hay dependencias nuevas de librerías de modal introducidas por GlossaryPanel; usa solo Tailwind + estado React local
