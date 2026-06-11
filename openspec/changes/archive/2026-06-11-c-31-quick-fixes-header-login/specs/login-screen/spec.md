# Delta Spec: login-screen (C-31)

## Capability
`login-screen` — Pantalla de login del alumno.

## Change Type
DELTA — modifica navegación de la pantalla de login.

## Requirements

### REQ-LG-01: Nav del login sin link a /requisitos
El `<nav>` del login NO debe contener el link "Requisitos técnicos" (`href="#/requisitos"`).

**Motivo**: La ruta `/requisitos` lleva al flujo demo de EquipmentCheck, causando confusión al alumno que intenta hacer login. La verificación de equipo es parte del flujo de examen, no del login.

### REQ-LG-02: Sin separadores huérfanos en el nav
Al eliminar el link de requisitos, el separador visual (`<span>` bullet) que lo acompañaba también debe eliminarse. El nav debe contener solo los links presentes.

### REQ-LG-03: Ruta /requisitos puede permanecer en App.tsx
La definición de la ruta `#/requisitos` en el router puede mantenerse para uso futuro (flujo de verificación de equipo pre-examen real). Solo se elimina el punto de entrada desde el login.

## Rationale
Separación entre el flujo de autenticación y el flujo de verificación de equipo. El login es el punto de entrada único; los flujos de pre-examen se acceden desde el portal del alumno, no desde el login.
