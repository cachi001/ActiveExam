## ADDED Requirements

### Requirement: AuditLogItem como componente de presentación pura
Cada entrada del registro de auditoría SHALL ser un componente `AuditLogItem` en `screens/admin/components/AuditLogItem.tsx` con prop `entrada: { ts: string; actor: string; accion: string; detalle: string; tono: 'error' | 'neutral' | 'warning' | 'success' | 'primary' }`.

#### Scenario: Renderizado de entrada de auditoría
- **WHEN** `AuditLogItem` recibe una entrada
- **THEN** muestra icono history + accion (font-semibold) + Badge con tono + detalle + timestamp en font-mono, con mismo espaciado que antes

#### Scenario: Mantenimiento de distinción visual por tono
- **WHEN** hay entradas de distintos actores (Sistema vs. Prof. Acuña)
- **THEN** el Badge de actor refleja el tono correcto (error → derivación, success → consentimiento, etc.)

### Requirement: DsrCard como componente de presentación pura
Cada derecho del titular (Acceso, Rectificación, Supresión, Reclamo AAIP) SHALL ser un componente `DsrCard` en `screens/admin/components/DsrCard.tsx` con prop `derecho: { icon: string; titulo: string; desc: string }`.

#### Scenario: Renderizado de derecho
- **WHEN** `DsrCard` recibe un derecho
- **THEN** muestra icono primary + titulo en font-semibold + desc en on-surface-variant, con `p-base rounded-xl bg-surface-container-low border border-outline-variant/30`

### Requirement: SectionTitle en AuditPrivacy
El encabezado "Derechos del titular" en AuditPrivacy SHALL usar `SectionTitle` con `sub="Ley 25.326 · AAIP"` en lugar de `<h3>` + `<p>` por separado.

#### Scenario: Encabezado con sub legal
- **WHEN** se visualiza la sección de derechos
- **THEN** `SectionTitle` muestra "Derechos del titular" como título y "Ley 25.326 · AAIP" como sub — coherente con el design system

### Requirement: AuditPrivacy.tsx queda como orquestador delgado
Tras la extracción, `AuditPrivacy.tsx` SHALL contener solo: arrays `AUDITORIA` y `DSR` (datos estáticos), el shell y el layout, con `AuditLogItem` y `DsrCard` mapeados.

#### Scenario: Largo de archivo post-refactor
- **WHEN** se completa la extracción
- **THEN** `AuditPrivacy.tsx` tiene ≤55 líneas (bajando de ~83)
