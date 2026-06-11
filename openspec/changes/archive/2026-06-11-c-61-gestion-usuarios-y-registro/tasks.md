## 1. Modelo de datos y migración (slim)

- [x] 1.1 Crear migración `0009_c61_usuario_datos_personales.py` en `backend/migrations/versions/` con `revision="0009"`, `down_revision="0008"`, `branch_labels=None`, `depends_on=None` (NO cruzar la rama principal ni TimescaleDB)
- [x] 1.2 En `upgrade()`: `ADD COLUMN nombre VARCHAR(255) NULL`, `ADD COLUMN apellido VARCHAR(255) NULL`, `ADD COLUMN eliminado_en TIMESTAMPTZ NULL` sobre `usuario`
- [x] 1.3 En `downgrade()`: dropear las tres columnas en orden inverso
- [x] 1.4 Actualizar `UsuarioModel` (`backend/app/infrastructure/persistence/models/transactional.py`) con `nombre`, `apellido` (nullable) y `eliminado_en` (TIMESTAMPTZ nullable)
- [x] 1.5 Verificar `alembic upgrade slim@head` contra `postgres:16-alpine` (sin timescale) y `alembic history` muestra `0005 → 0008 → 0009`

## 2. Backend — CRUD de usuarios (user-management)

- [x] 2.1 `GET /api/v1/users/` paginado (`limit`/`offset`), solo `admin_sistema`, filtra `eliminado_en IS NULL`, excluye `password_hash`; schema de respuesta con `extra='forbid'`
- [x] 2.2 `PUT /api/v1/users/{usuario_id}` edita email y roles (valida roles contra `Rol`), solo `admin_sistema`; rechaza editar `password_hash`/`auth_provider` (extra='forbid'); 404 si no existe
- [x] 2.3 Regla anti-lockout en `PUT`: el admin no puede quitarse a sí mismo `admin_sistema` (4xx)
- [x] 2.4 `DELETE /api/v1/users/{usuario_id}` soft-delete (`eliminado_en = now()`), solo `admin_sistema`, 204; revoca refresh tokens vigentes del usuario
- [x] 2.5 Ajustar `POST /api/v1/auth/login` para filtrar `eliminado_en IS NULL` (usuario dado de baja no puede loguear, mensaje genérico)
- [x] 2.6 Tests con Postgres real (sin mocks de DB): listado (200/403/401, baja excluida), edición (200/422/404/anti-lockout), baja (204, no loguea, evidencia intacta, 403)

## 3. Backend — Registro público (user-registration)

- [x] 3.1 `POST /api/v1/auth/register` PÚBLICO; schema con `extra='forbid'`: nombre, apellido, id_institucional, email, password, password_confirmacion (sin campo `roles`)
- [x] 3.2 Validar dominio de email institucional (env configurable, ej. `INSTITUTION_EMAIL_DOMAIN`); coincidencia y fuerza mínima de password; forzar rol `["estudiante"]` y `auth_provider="local"`; bcrypt 12r
- [x] 3.3 Manejar 409 (email/id_institucional duplicado) y 422 (validaciones); password nunca en claro ni en logs
- [x] 3.4 Decisión post-registro: responder 201 sin token (frontend redirige a login) — ver S3 del design
- [x] 3.5 Tests con Postgres real: registro exitoso (201), rechazo de `roles` en body (422), email fuera de dominio (422), password no coincide/débil (422), duplicado (409), password hasheado

## 4. Backend — Lectura de foto de perfil (profile-photo-retrieval)

- [x] 4.1 `GET /api/v1/enrollment/foto-perfil` devuelve la foto vigente del usuario autenticado como base64 en JSON; 404 sin foto; 401 sin token; binario no se loguea
- [x] 4.2 `GET /api/v1/enrollment/foto-perfil/{usuario_id}` solo `admin_sistema`/`proctor`; 403 para `estudiante` sobre foto ajena; 404 si el objetivo no tiene foto
- [x] 4.3 Lectura slim: leer `foto_bytes` de `foto_referencia` con `vigente=true` (SQLAlchemy Core, patrón de `DbPhotoStorageService`)
- [x] 4.4 Montar el endpoint en `main_slim.py` si hace falta y verificar que el router de enrollment lo expone
- [x] 4.5 Tests con Postgres real: foto propia (200/404/401), foto ajena por rol (200 admin, 403 estudiante, 404 sin foto)

## 5. Frontend — Avatar y API (depende de backend frente 4)

- [x] 5.1 Agregar `api.obtenerFotoPerfil()` y `api.obtenerFotoPerfil(usuarioId)` en `frontend/src/lib/api.ts` con patrón dual real/mock
- [x] 5.2 Mostrar el avatar (componente `Avatar`) en el header de perfil del alumno con fallback sin foto
- [x] 5.3 Mostrar el avatar en la tabla de gestión de usuarios

## 6. Frontend — Gestión de usuarios (admin) (REQUIERE C-60 aplicado)

- [x] 6.1 Crear pantalla `GestionUsuarios.tsx` (PascalCase) con listado responsive (tabla/cards), reusando el componente de input reusable de C-60
- [x] 6.2 Formulario de alta (invoca `POST /users/`), edición (`PUT /users/{id}`) y baja con confirmación (`DELETE /users/{id}`) reusando inputs de C-60 y `ConfirmModal` existente
- [x] 6.3 Agregar entrada en `STAFF_NAV` (`frontend/src/ui/nav.ts`) y ruta en el router; enlazar desde `AdminDashboard`
- [x] 6.4 Métodos `api.listarUsuarios`, `api.editarUsuario`, `api.eliminarUsuario`, `api.crearUsuario` en `lib/api.ts` (dual real/mock)

## 7. Frontend — Registro / signup (REQUIERE C-60 aplicado)

- [x] 7.1 Crear pantalla `Registro.tsx` (PascalCase) con campos nombre, apellido, id_institucional, email, password + confirmación, reusando el input de C-60
- [x] 7.2 Validación en cliente: dominio de email institucional (`INSTITUTION.dominioEmail`) y coincidencia de password antes de enviar
- [x] 7.3 `api.registrarUsuario()` en `lib/api.ts` (POST `/auth/register`, dual real/mock); tras éxito redirigir al login
- [x] 7.4 Agregar enlace "Registrarse" en `Login.tsx` (variante JWT) y ruta en el router

## 8. Verificación y cierre

- [x] 8.1 `openspec verify` / revisar que specs, design y tasks están alineados
- [x] 8.2 Confirmar reglas duras: snake_case Python, PascalCase componentes, `extra='forbid'` en todos los schemas, tests sin mocks de DB, sin build/commit automático
- [x] 8.3 Confirmar con el dueño los supuestos abiertos S1–S5 del design antes del archive [Confirmado por el dueño (2026-06-11): S1 registro abierto con validación de dominio, S2 sin verificación email/recuperación/rate-limiting en v1, S3 redirige al login, S4 dominio configurable por env, S5 soft-delete sin UI de reactivación. DEUDA anotada: rate-limiting del auto-registro (S1+S2) como prioridad de hardening futuro.]
