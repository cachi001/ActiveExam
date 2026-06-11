## Why

El header de staff muestra el texto "Self-hosted · " junto al nombre institucional, exponiendo un detalle de infraestructura irrelevante para el usuario final. El login expone un link "Requisitos técnicos" que lleva al flujo de demo de equipo (`/requisitos` → EquipmentCheck), causando confusión: el alumno que lo toca cae en el flujo de examen demo en lugar de hacer login. Dos fixes de presentación, sin cambios funcionales ni de backend.

## What Changes

- **Sacar "Self-hosted · "** del badge del header de staff (`frontend/src/ui/shells.tsx`). El ícono `dns` queda sin contexto si solo muestra el nombre corto de la institución; se elimina el badge completo y se deja solo el nombre institucional como texto plano. La constante `INSTITUTION` no se modifica.
- **Sacar el link "Requisitos técnicos"** del nav del login (`frontend/src/screens/Login.tsx`). Al quedar un solo item en el `<nav>`, se elimina también el separador visual (`<span>` bullet) que lo acompañaba. La ruta `#/requisitos` puede permanecer definida en `App.tsx` para el futuro flujo real pero NO es accesible desde el login.

## Capabilities

### New Capabilities
<!-- ninguna — es un fix de presentación puro -->

### Modified Capabilities
- `staff-shell-header`: elimina el badge "Self-hosted" del header de la shell de staff; solo muestra título de página.
- `login-screen`: elimina el link "Requisitos técnicos" y el separador visual asociado del nav de login.

## Impact

- **Archivos modificados**: `frontend/src/ui/shells.tsx` (línea ~115), `frontend/src/screens/Login.tsx` (líneas ~59-63)
- **Sin cambios de API, rutas, lógica de negocio ni otros componentes**
- **TypeScript**: 0 errores esperados (solo eliminación de JSX estático)
