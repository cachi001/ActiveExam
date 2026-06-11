# term-tooltip-component

## Purpose

Define el componente átomo `<Term>` que envuelve terminología técnica en cualquier pantalla con una indicación visual (subrayado punteado + icono "?") y un tooltip accesible con la definición de `GLOSSARY[termKey]`. Cubre además el reemplazo de las menciones crudas de términos técnicos visibles al alumno (L2.5, embedding, WORM, liveness, cadena de custodia) por su versión envuelta en `<Term>` para que el texto siga visible pero la definición esté disponible en contexto.

## Requirements

### Requirement: Componente átomo Term que envuelve terminología técnica con definición accesible
El sistema SHALL proveer un componente React `<Term>` en `frontend/src/ui/Term.tsx` que reciba una `termKey: TermKey`, renderice el texto técnico con indicación visual (subrayado punteado + icono "?") y muestre la definición de `GLOSSARY[termKey]` como tooltip al hacer hover en desktop o tap en mobile. El componente SHALL ser accesible (aria-describedby, role="tooltip") y reutilizable en cualquier pantalla del frontend.

#### Scenario: Renderizado del texto técnico con indicación visual
- **WHEN** se renderiza `<Term termKey="l2_5" />`
- **THEN** el texto "L2.5" aparece con subrayado punteado y un icono pequeño "?" que indica la presencia de una definición disponible

#### Scenario: Tooltip visible en hover (desktop)
- **WHEN** el usuario hace hover sobre un `<Term termKey="embedding" />`
- **THEN** aparece un tooltip con el texto de `GLOSSARY['embedding'].definition` sin necesidad de click

#### Scenario: Tooltip visible en tap (mobile/touch)
- **WHEN** el usuario toca un `<Term termKey="liveness" />` en un dispositivo touch
- **THEN** aparece el tooltip con la definición de `liveness`

#### Scenario: Tooltip cierra al tap fuera
- **WHEN** el tooltip está visible y el usuario toca fuera del componente `<Term>`
- **THEN** el tooltip se cierra

#### Scenario: Referencia legal visible en el tooltip cuando existe
- **WHEN** el usuario activa el tooltip de `<Term termKey="embedding" />`
- **THEN** el tooltip muestra la `definition` y también la `legalRef` (Ley 25.326) en texto secundario

#### Scenario: Accesibilidad — aria-describedby
- **WHEN** se renderiza `<Term termKey="cadena_de_custodia" />`
- **THEN** el elemento de texto tiene `aria-describedby` apuntando al id del elemento tooltip, y el tooltip tiene `role="tooltip"`

#### Scenario: children override — texto personalizado
- **WHEN** se renderiza `<Term termKey="worm">almacenamiento WORM</Term>`
- **THEN** el texto visible es "almacenamiento WORM" (el children) en lugar del `label` del glosario, pero el tooltip muestra la definición de WORM

#### Scenario: Sin dependencias externas de tooltip
- **WHEN** se inspecciona el bundle del frontend
- **THEN** no hay dependencias nuevas de librerías de tooltip (@radix-ui, floating-ui, etc.) en `package.json` introducidas por este componente

### Requirement: Reemplazo de menciones crudas de términos técnicos visibles al alumno
Los términos técnicos visibles al usuario final (alumno) en las pantallas de consentimiento, acuse, perfil, biometría y cierre SHALL ser envueltos con el componente `<Term>` de modo que el texto técnico siga visible pero la definición esté disponible en contexto.

#### Scenario: L2.5 en pantalla AcuseExamen envuelto con Term
- **WHEN** un alumno visualiza la pantalla AcuseExamen
- **THEN** el texto "L2.5" está envuelto en `<Term termKey="l2_5">` y el tooltip es accesible

#### Scenario: L2.5 en pantalla Cierre envuelto con Term
- **WHEN** un alumno visualiza la pantalla de cierre de sesión
- **THEN** el texto "L2.5" está envuelto en `<Term termKey="l2_5">` y el tooltip es accesible

#### Scenario: embedding en ConsentScreen envuelto con Term
- **WHEN** un alumno visualiza la pantalla de consentimiento (ConsentScreen)
- **THEN** el texto "embedding" está envuelto en `<Term termKey="embedding">` con la definición y referencia a Ley 25.326

#### Scenario: WORM en ConsentScreen envuelto con Term
- **WHEN** un alumno visualiza la pantalla de consentimiento (ConsentScreen)
- **THEN** el texto "WORM" está envuelto en `<Term termKey="worm">` con la definición de almacenamiento inmutable

#### Scenario: liveness en Biometria envuelto con Term
- **WHEN** un alumno visualiza la pantalla Biometria
- **THEN** el texto "liveness" está envuelto en `<Term termKey="liveness">` con la definición correspondiente

#### Scenario: L2.5 en StudentProfile envuelto con Term
- **WHEN** un alumno visualiza su perfil (StudentProfile)
- **THEN** las menciones de "L2.5" en el perfil están envueltas en `<Term termKey="l2_5">`

#### Scenario: cadena de custodia en Revisor envuelto con Term
- **WHEN** un revisor visualiza su panel (Revisor)
- **THEN** el texto "cadena de custodia" está envuelto en `<Term termKey="cadena_de_custodia">`
