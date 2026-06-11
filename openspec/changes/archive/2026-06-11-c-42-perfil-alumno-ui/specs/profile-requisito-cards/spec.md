## ADDED Requirements

### Requirement: RequisitoCard es un componente de presentación pura para requisitos de enrollment
El sistema SHALL proveer un componente `RequisitoCard` en `frontend/src/screens/alumno/components/RequisitoCard.tsx` que encapsule el patrón visual de un requisito de enrollment del alumno. El componente SHALL renderizar: un encabezado con ícono (`icon: string`), título (`title: string`) y badge de estado (`badge: { tone: BadgeTone; label: string }`); un slot `children` para el detalle del requisito; un slot opcional `action` para el CTA. El componente es presentación pura: no accede al store ni llama APIs.

#### Scenario: Renderizado con requisito pendiente
- **WHEN** se instancia `RequisitoCard` con `badge.tone='warning'` y `badge.label='Pendiente'`
- **THEN** el componente muestra el ícono, el título y un badge con tono warning/dot y label "Pendiente"
- **THEN** el slot `children` es renderizado debajo del encabezado
- **THEN** si `action` es proporcionado, se renderiza a la derecha del encabezado o debajo del contenido

#### Scenario: Renderizado con requisito completado
- **WHEN** se instancia `RequisitoCard` con `badge.tone='success'` y `badge.label='Completado'`
- **THEN** el componente muestra el badge con tono success/dot y label "Completado"

#### Scenario: RequisitoCard sin action no muestra CTA
- **WHEN** se instancia `RequisitoCard` sin prop `action`
- **THEN** el componente no renderiza ningún botón ni slot de acción

### Requirement: La vista del perfil usa RequisitoCard para los cuatro requisitos de enrollment
El sistema SHALL usar `RequisitoCard` como contenedor para las cuatro secciones de requisitos en la vista `paso==='perfil'` de `StudentProfile.tsx`: consentimiento informado (`icon='gavel'`), referencia biométrica (`icon='face'`, solo si `!viaAlternativa`), verificación documental DNI (`icon='badge'`). El badge SHALL reflejar el estado real del requisito según `enrollment`.

#### Scenario: Consentimiento informado muestra badge 'Completado' cuando el acuse existe
- **WHEN** `enrollment.consentimiento` no es null y `paso === 'perfil'`
- **THEN** la `RequisitoCard` de consentimiento muestra badge `tone='success'` y label 'Completado' (o 'Vía alternativa' si `viaAlternativa`)

#### Scenario: Consentimiento informado muestra badge 'Pendiente' sin acuse
- **WHEN** `enrollment.consentimiento` es null y `paso === 'perfil'`
- **THEN** la `RequisitoCard` de consentimiento muestra badge `tone='warning'` y label 'Pendiente'

#### Scenario: Referencia biométrica no visible en vía alternativa
- **WHEN** `enrollment.consentimiento.via_alternativa === true` y `paso === 'perfil'`
- **THEN** la `RequisitoCard` de referencia biométrica NO se renderiza

#### Scenario: DNI muestra badge 'Registrado' cuando captura completada
- **WHEN** `enrollment.dni.captura_completada === true` y `paso === 'perfil'`
- **THEN** la `RequisitoCard` de verificación documental muestra badge `tone='success'` y label 'Registrado'

#### Scenario: DNI muestra badge 'No disponible' cuando el flag está apagado
- **WHEN** `ENABLE_DNI_SCAN` es false y `enrollment.dni.captura_completada` es false
- **THEN** la `RequisitoCard` de verificación documental muestra badge `tone='neutral'` y label 'No disponible'

### Requirement: El contenido interno de cada RequisitoCard preserva la información legal y L2.5
El sistema SHALL mantener dentro del slot `children` de cada `RequisitoCard` toda la información legal y de privacidad existente: notas Ley 25.326, referencias a `<Term termKey="embedding" />` y `<Term termKey="l2_5" />`, el disclaimer "decisión disciplinaria siempre humana", el hash de acuse del consentimiento. No se elimina ni simplifica ningún texto legal para lograr el look minimalista.

#### Scenario: Nota de privacidad presente en biometría pendiente
- **WHEN** `!biometriaOk` y la `RequisitoCard` de biometría está visible
- **THEN** el slot `children` incluye la nota "Privacidad (Ley 25.326):" con los datos sensibles del embedding

#### Scenario: Hash de acuse visible en consentimiento completado
- **WHEN** `enrollment.consentimiento` existe y tiene campo `hash`
- **THEN** el slot `children` de la `RequisitoCard` de consentimiento muestra el hash en `font-mono text-[11px] break-all`
