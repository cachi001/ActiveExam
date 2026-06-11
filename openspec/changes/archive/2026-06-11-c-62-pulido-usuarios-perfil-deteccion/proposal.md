## Why

La pantalla de gestión de usuarios (C-61) tiene deuda de presentación: lista plana sin tabla en desktop, el campo interno `auth_provider` visible al administrador, y la entrada de roles como texto libre que facilita errores. Además, el perfil del alumno muestra solo el nombre sin apellido, la pantalla de consentimiento sufre delays artificiales que degradan la percepción de respuesta, y la herramienta de diagnóstico de detección inicia con el mesh simplificado ocultando información útil al administrador.

## What Changes

- **Tabla responsive en Gestión de Usuarios**: en desktop (md+) la lista de usuarios pasa a una tabla HTML con columnas definidas (Avatar+Nombre, Email, Legajo, Roles, Acciones); en mobile mantiene cards con estilo consistente (fondo blanco, borde sutil, sombra suave).
- **Ocultar `auth_provider` en la vista de usuarios**: el valor "jwt"/"local" deja de mostrarse en la fila de cada usuario; el campo permanece en el tipo y el backend pero se elimina de la presentación.
- **Selector de roles normalizado**: el campo de texto libre "Roles (separados por coma)" en el formulario create/edit se reemplaza por checkboxes con labels legibles en español; se introduce `ROL_LABELS` en `frontend/src/lib/constants/roles.ts` y se usa para renderizar los roles en la lista/tabla.
- **Nombre y apellido completos en el perfil del alumno**: `PerfilHeaderCard` muestra "Nombre Apellido" como título; `Principal` incorpora el campo `apellido?: string`; el endpoint `GET /auth/me` se extiende para incluir `nombre` y `apellido` consultando `UsuarioModel` en DB, y `PrincipalResponse` los expone; `AuthenticatedPrincipal` también los incorpora.
- **Eliminación de delays artificiales en consentimiento**: `getConsentText` y `getEnrollment` en `api.ts` reducen sus delays simulados a cero (o los eliminan), haciendo que la pantalla de consentimiento aparezca de inmediato.
- **Mesh completo por defecto en el harness de detección**: `useDetectionHarness` inicializa `showFullMesh` en `true` para que `/admin/detection-test` arranque mostrando los 468 landmarks.

## Capabilities

### New Capabilities

- `user-management-table`: Vista tabular responsive de gestión de usuarios (tabla en desktop, cards estilizadas en mobile) con selector de roles normalizado y labels legibles.
- `roles-constants`: Módulo `frontend/src/lib/constants/roles.ts` con `ROL_LABELS` para los 3 roles del MVP.

### Modified Capabilities

- `student-profile-shell`: El header del perfil del alumno ahora muestra nombre+apellido completos (requiere que `GET /auth/me` devuelva ambos campos y que `Principal` declare `apellido`).
- `admin-detection-test-harness`: El harness inicia con el mesh de 468 landmarks activo por defecto (`showFullMesh = true`).

## Impact

**Frontend:**
- `frontend/src/screens/GestionUsuarios.tsx` — tabla responsive, ocultar auth_provider, checkboxes de roles.
- `frontend/src/lib/types.ts` — agregar `apellido?: string` a `Principal`.
- `frontend/src/screens/alumno/components/PerfilHeaderCard.tsx` — mostrar nombre+apellido.
- `frontend/src/lib/api.ts` — eliminar delays en `getConsentText` y `getEnrollment`.
- `frontend/src/screens/harness/useDetectionHarness.ts` — `showFullMesh` default `true`.
- `frontend/src/lib/constants/roles.ts` — nuevo archivo de constantes de roles.

**Backend:**
- `backend/app/presentation/api/v1/auth/router.py` — `PrincipalResponse` agrega `nombre` y `apellido`; endpoint `GET /auth/me` hace query a `UsuarioModel` por `subject` del token para obtenerlos.
- `backend/app/domain/auth/identity.py` — `AuthenticatedPrincipal` agrega `nombre` y `apellido`.
- `backend/app/presentation/api/v1/auth/dependencies.py` — revisar cómo se construye `AuthenticatedPrincipal` para inyectar nombre/apellido.
- Tests backend: nuevo test para `/auth/me` verificando que devuelve `nombre` y `apellido` (postgres real, sin mocks de DB).

**Sin migraciones de base de datos**: `nombre` y `apellido` ya existen en `UsuarioModel` (C-61); solo se exponen en el contrato de la API.
