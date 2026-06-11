## 1. Constantes de roles (frontend)

- [x] 1.1 Crear `frontend/src/lib/constants/roles.ts` exportando `ROL_LABELS: Record<string, string>` con los tres roles del MVP mapeados a labels en español
- [x] 1.2 Crear función helper `getRolLabel(rol: string): string` en el mismo módulo que hace fallback al identificador si la clave no existe

## 2. Tipo Principal con apellido (frontend)

- [x] 2.1 Agregar `apellido?: string` al interface `Principal` en `frontend/src/lib/types.ts`
- [x] 2.2 Verificar que ningún consumidor existente de `Principal` falle por la adición del campo opcional (TypeScript lo acepta sin cambios)

## 3. Backend — AuthenticatedPrincipal con nombre y apellido

- [x] 3.1 Agregar `nombre: str | None = None` y `apellido: str | None = None` al dataclass `AuthenticatedPrincipal` en `backend/app/domain/auth/identity.py`
- [x] 3.2 Verificar que `TokenPolicy.principal_desde_claims()` en `backend/app/domain/auth/token.py` no necesita cambios (los nuevos campos tienen default `None`)

## 4. Backend — PrincipalResponse y GET /auth/me con DB lookup

- [x] 4.1 Agregar `nombre: str | None = None` y `apellido: str | None = None` a `PrincipalResponse` en `backend/app/presentation/api/v1/auth/router.py` (mantener `extra='forbid'`)
- [x] 4.2 Extender el endpoint `GET /auth/me` para aceptar `request: Request` como parámetro adicional y obtener `session_factory` desde `app.state`
- [x] 4.3 Si `session_factory` está disponible, hacer query `SELECT UsuarioModel WHERE id = principal.subject` para obtener `nombre` y `apellido`
- [x] 4.4 Devolver `nombre` y `apellido` en `PrincipalResponse`; si la DB no está disponible o el usuario no se encuentra, devolver `None` en ambos campos (degradación graceful)

## 5. Tests backend — GET /auth/me con nombre y apellido

- [x] 5.1 Agregar test de integración en el módulo de tests de auth (postgres real, sin mocks de DB) que crea un usuario con `nombre` y `apellido`, hace login, llama a `GET /auth/me` y verifica que la respuesta incluye los campos correctos
- [x] 5.2 Agregar caso de test donde el usuario tiene `nombre=null` y `apellido=null`: verificar que `GET /auth/me` devuelve `null` en ambos sin error 500

## 6. PerfilHeaderCard — nombre y apellido completos

- [x] 6.1 En `frontend/src/screens/alumno/components/PerfilHeaderCard.tsx`, cambiar `{principal?.nombre ?? '—'}` por `{[principal?.nombre, principal?.apellido].filter(Boolean).join(' ') || '—'}` (o equivalente legible)
- [x] 6.2 Actualizar el texto `alt` de la imagen de perfil para incluir apellido si está disponible

## 7. Eliminar delays artificiales en consentimiento (frontend)

- [x] 7.1 En `frontend/src/lib/api.ts`, cambiar `await delay(300)` en `getConsentText` a `await delay(0)` (o eliminar la línea)
- [x] 7.2 En `frontend/src/lib/api.ts`, cambiar `await delay(250)` en `getEnrollment` a `await delay(0)` (o eliminar la línea)
- [x] 7.3 Verificar manualmente que la pantalla de consentimiento carga sin retardo perceptible en modo demo

## 8. Harness de detección — mesh completo por defecto

- [x] 8.1 En `frontend/src/screens/harness/useDetectionHarness.ts`, cambiar `useState(false)` a `useState(true)` en la inicialización de `showFullMesh`

## 9. GestionUsuarios — ocultar auth_provider

- [x] 9.1 En `frontend/src/screens/GestionUsuarios.tsx`, eliminar `· {u.auth_provider}` de la línea que muestra roles (línea 404), dejando solo `{u.roles.join(', ')}` (que luego se migrará a ROL_LABELS en la tarea de tabla)

## 10. GestionUsuarios — tabla responsive y cards estilizadas

- [x] 10.1 En `GestionUsuarios.tsx`, reemplazar el bloque de lista (`<div className="mt-md space-y-base">`) por una estructura dual: `<table>` con `className="hidden md:table w-full"` y `<div>` de cards con `className="md:hidden space-y-base"`
- [x] 10.2 Implementar el `<thead>` con columnas: Avatar+Nombre, Email, Legajo, Roles, Acciones
- [x] 10.3 Implementar el `<tbody>` con una `<tr>` por usuario; celda Avatar+Nombre combina el avatar existente + nombre completo; celda Roles usa `ROL_LABELS`
- [x] 10.4 Aplicar estilo a las cards mobile: fondo blanco (`bg-white`), borde sutil (`border border-outline-variant/30`), sombra suave (`shadow-sm`), `rounded-md` (no `rounded-xl`)
- [x] 10.5 Asegurar que los botones de Editar y Dar de baja aparecen tanto en la fila de tabla (columna Acciones) como en cada card mobile

## 11. GestionUsuarios — selector de roles por checkboxes

- [x] 11.1 En `GestionUsuarios.tsx`, importar `ROL_LABELS` desde `frontend/src/lib/constants/roles.ts`
- [x] 11.2 Reemplazar el `<TextField>` de "Roles (separados por coma)" por un grupo de tres checkboxes usando los valores de `ROLES_VALIDOS` y labels de `ROL_LABELS`
- [x] 11.3 Actualizar `FormState.roles` de `string` a `string[]` (o mantener como string y parsear internamente — ver opción más limpia) para reflejar el estado de checkboxes
- [x] 11.4 Actualizar `abrirEditar` para pre-seleccionar los checkboxes del usuario existente (`u.roles`) al abrir el formulario de edición
- [x] 11.5 Actualizar `handleSubmit` para leer los roles desde el estado de checkboxes en lugar de parsear texto
- [x] 11.6 Eliminar la lógica de `parsearRoles` ya que no aplica con checkboxes; validar que al menos un checkbox esté marcado antes de submit
