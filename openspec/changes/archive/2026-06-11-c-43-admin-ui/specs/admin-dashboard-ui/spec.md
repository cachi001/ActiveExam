## ADDED Requirements

### Requirement: Acciones rápidas con SectionTitle
El sidebar de acciones rápidas en AdminDashboard SHALL usar `SectionTitle` en lugar de `<h3>` manual para mantener tipografía consistente con el resto del design system.

#### Scenario: Encabezado visual unificado
- **WHEN** el admin navega a `/admin`
- **THEN** el card de acciones rápidas muestra un encabezado con `SectionTitle` y los botones son `size="sm"` — proporcionales al ancho del card (no `md`/h-12 que es excesivo para un card de sidebar estrecho)

### Requirement: Botones de acción proporcionales en AdminDashboard
Los tres botones del card de acciones rápidas (Crear examen, Ver reportes, Auditoría) SHALL tener `size="sm"` para ser proporcionales al espacio disponible en el card de sidebar.

#### Scenario: Botones sin exceso de altura
- **WHEN** el admin visualiza el card "Acciones rápidas"
- **THEN** los tres botones tienen altura h-9 (size="sm"), no h-12 (size="md"), evitando que el card se sienta pesado en pantallas medianas

### Requirement: Tabla de exámenes con jerarquía visual clara
La tabla de exámenes en AdminDashboard SHALL mostrar nombre+cátedra con jerarquía clara: nombre en `font-semibold`, cátedra+inscriptos en `text-label-sm text-on-surface-variant`.

#### Scenario: Lectura rápida de la tabla
- **WHEN** hay múltiples exámenes en la tabla
- **THEN** el nombre del examen domina visualmente y los metadatos (cátedra, inscriptos) son secundarios con color muted

### Requirement: ExamList usa Button para acción inline
El enlace "Configurar" inline en la tabla de ExamList SHALL ser un `Button` del design system con `size="sm" variant="ghost"` en vez de un `<button>` raw con clases manuales.

#### Scenario: Acción de configurar proporcional
- **WHEN** el admin ve la lista de exámenes
- **THEN** cada fila tiene un Button ghost con icon="edit" y texto "Configurar" — consistente con el design system, sin clases CSS manuales de color

### Requirement: Reports usa ProgressBar del design system
Las barras de distribución de severidad en Reports SHALL usar el tono semántico correcto de `ProgressBar` en vez de una clase `bg-primary-container` genérica para todos los niveles.

#### Scenario: Barra de severidad con tono semántico
- **WHEN** se muestra la distribución de severidad
- **THEN** cada barra tiene el tono correspondiente: baja→success, media→warning, alta→error, critica→error, baseline→primary
