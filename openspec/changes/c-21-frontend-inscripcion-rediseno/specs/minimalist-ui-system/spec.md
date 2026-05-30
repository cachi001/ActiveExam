# Spec — minimalist-ui-system

> Rediseño minimalista y consistente de la UI/UX sobre el design system existente: jerarquía, tokens, microcopy en español y estados vacío/carga/error.

## ADDED Requirements

### Requirement: Consistencia visual sobre el design system
El sistema SHALL presentar las pantallas usando los componentes y tokens del design system existente (espaciado, tipografía, color, jerarquía) con una acción primaria clara por pantalla, evitando estilos ad-hoc.

#### Scenario: Una acción primaria por pantalla
- **WHEN** el usuario abre una pantalla del flujo
- **THEN** hay una única acción primaria visualmente destacada y el resto son secundarias

### Requirement: Estados vacío, carga y error
El sistema SHALL mostrar estados de carga, vacío y error en toda pantalla que dependa de datos asíncronos, en lugar de áreas en blanco o pantallas congeladas.

#### Scenario: Pantalla con datos asíncronos
- **WHEN** una pantalla carga datos de la API mock
- **THEN** muestra un estado de carga mientras resuelve y un estado vacío o de error si corresponde
