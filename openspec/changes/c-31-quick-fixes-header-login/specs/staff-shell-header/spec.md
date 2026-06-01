# Delta Spec: staff-shell-header (C-31)

## Capability
`staff-shell-header` — Header de la shell de staff.

## Change Type
DELTA — modifica comportamiento de presentación existente.

## Requirements

### REQ-SH-01: Sin badge de infraestructura
El header de la shell de staff NO debe mostrar ningún indicador de modo de despliegue ("Self-hosted", "Cloud", etc.) ni iconos de infraestructura (`dns`, `cloud`, etc.).

**Antes (eliminado)**:
- Badge `<span>` con ícono `dns` y texto "Self-hosted · {INSTITUTION.nombreCorto}"

**Después**:
- El área derecha del header queda sin badge; si no hay otros controles, el contenedor vacío se elimina del DOM.

### REQ-SH-02: INSTITUTION.nombreCorto no se repite en el header
El nombre corto de la institución ya aparece en la sidebar. No debe duplicarse en el header.

## Rationale
"Self-hosted" es jerga de infraestructura irrelevante para el usuario final (staff, revisor). Su presencia genera preguntas innecesarias y no aporta valor funcional en la UI.
