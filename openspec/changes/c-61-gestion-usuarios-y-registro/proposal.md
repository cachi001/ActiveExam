## Why

Hoy el sistema solo permite **crear** usuarios uno a uno desde un endpoint protegido (`POST /api/v1/users/`, solo `admin_sistema`) y **subir** una foto de perfil que después no se puede recuperar (`POST /enrollment/foto-perfil` persiste un BYTEA opaco sin lectura). No existe forma de **listar, editar ni dar de baja** usuarios, no hay **auto-registro** de estudiantes, y la foto de perfil cargada **nunca se muestra** como avatar. El dueño pidió tres cosas concretas: gestionar usuarios desde el panel admin, que la gente pueda registrarse con sus datos, y que la foto de perfil se vea.

## What Changes

**Frente 1 — CRUD de usuarios (backend + UI admin)**
- `GET /api/v1/users/` — listar usuarios paginado (solo `admin_sistema`).
- `PUT /api/v1/users/{usuario_id}` — editar email y roles (solo `admin_sistema`).
- `DELETE /api/v1/users/{usuario_id}` — baja de usuario (solo `admin_sistema`). Se decide **soft-delete** (ver design D3) para preservar la cadena de custodia y las FKs.
- UI admin: pantalla de gestión de usuarios (listado responsive, alta, edición, baja con confirmación) integrada al `STAFF_NAV` / `AdminDashboard`.

**Frente 2 — Registro / auto-registro de estudiantes**
- `POST /api/v1/auth/register` — **endpoint público** de auto-registro de **estudiantes** (rol forzado a `estudiante`; nunca se permite auto-asignarse `proctor`/`admin_sistema`). Valida dominio de email institucional, unicidad de email e `id_institucional`, y fuerza mínima de password.
- Modelo `usuario`: se agregan columnas `nombre` y `apellido` (registro "con todos sus datos") vía migración Alembic **aislada en la rama slim** (patrón 0008, sin arrastrar TimescaleDB).
- UI: pantalla de **registro (signup)** enlazada desde el login, **reutilizando el componente de input reusable que define C-60** (dependencia, ver design D6). NO se crea un estilo de input propio.

**Frente 3 — Foto de perfil visible (avatar)**
- `GET /api/v1/enrollment/foto-perfil` — devuelve la foto vigente del **usuario autenticado**.
- `GET /api/v1/enrollment/foto-perfil/{usuario_id}` — variante para `admin_sistema`/`proctor` con permiso (dato sensible, Ley 25.326 — regla dura #7).
- `api.obtenerFotoPerfil()` en `frontend/src/lib/api.ts` y render del avatar donde corresponda (header de perfil, gestión de usuarios).

## Capabilities

### New Capabilities
- `user-management`: CRUD administrativo de usuarios (listar, editar roles/email, baja soft-delete), protegido por rol `admin_sistema`, con tests sobre Postgres real.
- `user-registration`: auto-registro público de estudiantes con validación de dominio institucional, rol forzado, datos personales (nombre/apellido), unicidad y fuerza de password.
- `profile-photo-retrieval`: recuperación de la foto de perfil persistida (propia del usuario o, con permiso, de otro) respetando el tratamiento de dato sensible.

### Modified Capabilities
<!-- Ninguna capability con spec.md previo en openspec/specs/ cambia sus requisitos a nivel contrato.
     Los endpoints de C-55 (auth) y C-56/C-57 (enrollment) se EXTIENDEN con rutas nuevas, no se redefine su comportamiento existente. -->

## Impact

- **Backend (slim + full)**: nuevos endpoints en `backend/app/presentation/api/v1/users/router.py`, `auth/router.py` (o nuevo `auth` register), `enrollment/router.py`. Nueva migración Alembic `0009_*` en la rama slim (`down_revision = "0008"`, `depends_on = None`). Modelo `UsuarioModel` (+`nombre`, +`apellido`, +`eliminado_en` para soft-delete). Posible servicio de aplicación para registro y para CRUD.
- **Frontend**: nueva pantalla de gestión de usuarios (admin), nueva pantalla de registro (signup), nuevo método `api.obtenerFotoPerfil`, render de avatar, entrada nueva en `STAFF_NAV`, link de registro en `Login.tsx`. Reúso del componente de input de C-60.
- **Dependencias entre changes**: **C-60** debe aplicarse antes que el frente de registro de C-61 (componente de input reusable). C-56 (`completedTasks 23/33`, in-progress) introdujo `foto_referencia`; el frente 3 se apoya en esa tabla (variante slim BYTEA `foto_bytes`).
- **Cumplimiento**: la foto de perfil es dato personal/sensible (Ley 25.326). El endpoint de lectura nunca expone fotos de terceros sin rol autorizado; no se loguea el binario. El soft-delete preserva evidencia con cadena de custodia (no se borra físicamente al usuario con sesiones/casos asociados).
- **Regla de dominio #5**: ninguna de estas funciones sanciona; son administrativas. La decisión disciplinaria sigue siendo humana y ajena a este change.
