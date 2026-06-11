## Context

ActiveExam corre en dos perfiles: el **slim** (Railway, `app.main_slim`, Postgres estándar sin TimescaleDB, foto de perfil como BYTEA en `foto_referencia.foto_bytes`) y el **full** (MinIO/WORM). La auth es JWT propia (C-55): login por email o `id_institucional`, access token HS256 + refresh persistente, roles en JSONB (`estudiante`, `proctor`, `admin_sistema`).

Estado actual relevante:
- `POST /api/v1/users/` ya crea usuarios (solo `admin_sistema`, bcrypt, valida roles, 409 en duplicado). NO existe listar/editar/borrar.
- `POST /enrollment/foto-perfil` ya **sube** la foto (slim → `DbPhotoStorageService` BYTEA; full → MinIO) pero NO hay endpoint de **lectura**.
- `UsuarioModel` tiene: `id`, `id_institucional` (unique), `email`, `roles` (JSONB), `attrs_federados`, `password_hash` (nullable), `auth_provider`. **NO tiene `nombre`/`apellido`** ni columna de baja lógica.
- Las migraciones del slim viven en una **rama Alembic aislada** (`0005 → 0008`, `down_revision="0005"`, `depends_on=None`) para no arrastrar `0001_enable_timescaledb`. Incidente conocido: cruzar ramas rompe el deploy slim.
- El input de formularios hoy es `FormField` (label) + `<input className="input">` crudo. **C-60 (en proposal, en paralelo)** define el componente de input reusable de calidad; C-61 lo reúsa.

Constraints duros: snake_case Python; PascalCase componentes React; Pydantic `extra='forbid'`; tests SIN mocks de DB (`postgres:16-alpine` para slim, NO timescale); foto/embedding = dato sensible (Ley 25.326); el sistema nunca sanciona (#5).

## Goals / Non-Goals

**Goals:**
- CRUD admin de usuarios (listar paginado, editar email/roles, baja) sólo para `admin_sistema`.
- Auto-registro público de **estudiantes** con sus datos personales (nombre, apellido, id_institucional, email institucional, password).
- Servir la foto de perfil persistida para mostrarla como avatar, respetando privacidad.
- Una migración Alembic en la rama slim que NO toque TimescaleDB.

**Non-Goals:**
- Auto-registro de proctores/admins (los crea el admin, frente 1). Jamás auto-elevación de rol.
- Reset de password / recuperación por email / verificación de email (out of scope; supuesto S2).
- Definir el componente de input reusable (lo hace C-60). C-61 sólo lo consume.
- Cambiar el flujo de login, refresh o el contrato de `/auth/me` existente.
- Re-inferencia o verificación biométrica (eso es C-59).
- Variante full/MinIO de lectura de foto más allá de lo mínimo: el foco operativo es el slim (Railway). Se diseña la abstracción pero el test E2E se clava en slim.

## Decisions

### D1 — Endpoints CRUD bajo `/api/v1/users/`
`GET /` (lista paginada con `limit`/`offset`, `extra='forbid'` en query via dependencia), `PUT /{usuario_id}` (email y roles; valida roles contra `Rol`), `DELETE /{usuario_id}`. Todos con `Depends(require_roles(Rol.ADMIN_SISTEMA))`, reusando el patrón ya presente en `users/router.py`. Schemas de respuesta con `extra='forbid'`.
- **Alternativa descartada**: un router `/admin/users` separado. Se descarta: ya existe `users/router.py` montado en slim; extenderlo es menos superficie y menos riesgo.

### D2 — Edición de roles: validación y auto-protección
`PUT` valida los roles igual que el alta (`{r.value for r in Rol}`). Regla de seguridad: un admin **no puede quitarse a sí mismo** el rol `admin_sistema` (evita lockout) → 409/422. No se permite editar `password_hash` ni `auth_provider` por este endpoint (cambio de password es otro flujo, S2).

### D3 — Baja: **soft-delete** (no hard-delete)
Se agrega `eliminado_en TIMESTAMPTZ NULL` a `usuario`. `DELETE` setea `eliminado_en = now()` en vez de borrar la fila.
- **Por qué**: el usuario tiene FKs desde `refresh_tokens`, `foto_referencia`, `embedding_referencia` (todas `ON DELETE CASCADE`) y, en el full, desde `sesion`/`consentimiento`/`embedding` (cadena de custodia, regla #6/#7). Un hard-delete destruiría evidencia y acuses inmutables. El soft-delete preserva la cadena de custodia y permite holds disciplinarios.
- **Efectos colaterales del soft-delete**: el usuario dado de baja (a) no aparece en el listado por default (filtro `eliminado_en IS NULL`), (b) no puede loguear → el login (`auth/router.py`) debe filtrar `eliminado_en IS NULL`, (c) sus refresh tokens se invalidan (revocar/rotar). **Decisión**: además del soft-delete, revocar refresh tokens vigentes del usuario (marcar `rotado_en`).
- **Alternativa descartada**: hard-delete con CASCADE. Se descarta por destrucción de evidencia (viola #6/#7). Para el embedding sí aplica la eliminación "al egreso" (DD-13), pero eso es un flujo de retención distinto, no la baja administrativa.

### D4 — Registro público de estudiantes: `POST /api/v1/auth/register`
Endpoint PÚBLICO (sin `require_roles`, como `/auth/login`). Recibe `nombre`, `apellido`, `id_institucional`, `email`, `password`, `password_confirmacion`. Reglas:
- Rol **forzado** a `["estudiante"]` server-side. El body NO acepta `roles` (`extra='forbid'` lo rechaza). Defensa en profundidad contra auto-elevación.
- Valida dominio de email contra `INSTITUTION.dominioEmail` (frontend) y su equivalente backend (env `INSTITUTION_EMAIL_DOMAIN`, configurable). Email fuera de dominio → 422.
- `password == password_confirmacion` y fuerza mínima (≥ 8, igual que el alta admin; opcional: 1 dígito + 1 letra). bcrypt 12r.
- `auth_provider = "local"`.
- Unicidad: 409 si email o `id_institucional` ya existen (mismo `IntegrityError` que el alta).
- **No** emite token automáticamente: tras registrar, el frontend redirige al login (supuesto S3 a confirmar; alternativa: auto-login devolviendo `LoginResponse`).
- **Alternativa descartada**: registrar vía `POST /users/` con rol pasado por el cliente. Se descarta: ese endpoint exige `admin_sistema` y deja el rol en manos del cliente — inseguro para auto-registro.

### D5 — Migración: `0009` en la rama slim, sin TimescaleDB
Nueva migración `0009_c61_usuario_datos_personales.py` con `revision="0009"`, `down_revision="0008"`, `branch_labels=None`, `depends_on=None` (idéntico patrón a 0008). `upgrade()`:
- `ADD COLUMN nombre VARCHAR(255) NULL`, `ADD COLUMN apellido VARCHAR(255) NULL` (nullable para no romper filas existentes — usuarios federados/legacy no los tienen).
- `ADD COLUMN eliminado_en TIMESTAMPTZ NULL` (soft-delete).
`downgrade()` dropea las tres columnas. **NO se toca la rama principal** (el modelo `UsuarioModel` declara las columnas como nullable; en full se agregarán en una migración de esa rama si/ cuando se promueva — fuera de scope de este change, que es slim).
- **Gotcha conocido**: si se pone `down_revision` apuntando a la rama principal o `depends_on` cruzado, el deploy slim de Railway rompe (incidente de C-55/C-56). Mantener `depends_on=None` y `down_revision="0008"`.

### D6 — Frontend: reúso del input de C-60 (dependencia dura)
Las pantallas nuevas (registro, formularios de alta/edición de usuario) **deben** usar el componente de input reusable de C-60, NO inventar estilo propio ni copiar el `<input className="input">` crudo de `Login.tsx`.
- **Coordinación**: el `apply` de C-61 se ejecuta **después** del `apply` de C-60 para que el componente exista. Si C-60 aún no aterrizó al implementar, se bloquea el frente de UI de registro (el backend y el CRUD de API pueden avanzar en paralelo).
- Mientras tanto, las pantallas se construyen contra la interfaz esperada del input (label, placeholder, error, icono, estado disabled, type password con toggle), que es el contrato que C-60 promete.

### D7 — Lectura de foto: `GET /enrollment/foto-perfil` (+ variante admin)
- `GET /enrollment/foto-perfil`: el usuario autenticado obtiene **su** foto vigente. Devuelve la imagen (slim: lee `foto_bytes` de la fila `vigente=true` del `subject`). Formato: **base64 dataURL** en JSON `{ imagen_base64 }` (consistente con cómo se sube y con `api`), o `image/*` binario con `Response` — se elige **base64 en JSON** para uniformidad con el resto de la API y para que el frontend lo use directo en `<img src>`. 404 si no hay foto vigente.
- `GET /enrollment/foto-perfil/{usuario_id}`: sólo `admin_sistema`/`proctor`. Sirve la foto de otro usuario para la gestión/supervisión. Dato sensible: se restringe por rol, no se loguea el binario, y se documenta la finalidad acotada (Ley 25.326, #7).
- El binario NO se cachea en logs ni en almacenamiento del cliente más allá del render.
- **Alternativa descartada**: exponer una URL firmada del bucket. En slim no hay bucket (BYTEA en DB), así que el endpoint sirve el contenido directo. En full podría firmarse, pero queda fuera del foco operativo (Non-Goal).

### D8 — `api.obtenerFotoPerfil()` y render del avatar
Nuevo método en `lib/api.ts` con el patrón dual real/mock existente: real → `GET /enrollment/foto-perfil` (y variante por `usuario_id`); mock → la foto demo en memoria. El componente `Avatar` (ya existe en `ui/components.tsx`) recibe el `src` resultante. Se muestra en el header de perfil del alumno y en la tabla de gestión de usuarios.

## Risks / Trade-offs

- **[Dependencia de C-60 no aplicada]** → El frente de UI de registro/forms queda bloqueado. Mitigación: backend + CRUD API + lectura de foto avanzan en paralelo; el apply de UI se ordena después de C-60. Documentado en tasks como prerequisito.
- **[Soft-delete deja datos del usuario en DB]** → Tensión con "derecho a eliminación" (Ley 25.326). Mitigación: el soft-delete es la baja **operativa**; la eliminación efectiva de datos sensibles (embedding/foto) sigue el flujo de retención/egreso (DD-13, C-19), que difiere por holds. La baja no borra evidencia con cadena de custodia por diseño (#6).
- **[Auto-registro abre superficie de abuso]** (cuentas masivas) → Mitigación: validación de dominio institucional + unicidad de `id_institucional`. Rate-limiting y verificación de email quedan como supuesto/futuro (S2/S4).
- **[Columnas nombre/apellido nullable]** → usuarios viejos sin nombre. Mitigación: la UI muestra fallback (email/id_institucional) cuando falta el nombre. No se exige backfill.
- **[Migración cruzando ramas Alembic]** → rompe el deploy slim (incidente histórico). Mitigación: `down_revision="0008"`, `depends_on=None`, verificar con `alembic upgrade slim@head` contra `postgres:16-alpine`.
- **[Servir foto de terceros]** → fuga de dato sensible si el guard falla. Mitigación: la variante `{usuario_id}` exige rol explícito; tests cubren 401/403; binario no se loguea.

## Migration Plan

1. Migración `0009` en rama slim (add `nombre`, `apellido`, `eliminado_en`), verificada contra `postgres:16-alpine` con `alembic upgrade slim@head`.
2. Actualizar `UsuarioModel` con las tres columnas (nullable).
3. Backend: endpoints CRUD + registro + lectura de foto, con tests sobre Postgres real (sin mocks de DB).
4. Ajustar login para filtrar `eliminado_en IS NULL`.
5. Frontend (DESPUÉS de C-60): pantalla de registro, pantalla de gestión de usuarios, `api.obtenerFotoPerfil`, render de avatar, link de registro en `Login.tsx`, entrada en `STAFF_NAV`.
- **Rollback**: `alembic downgrade slim@0008` dropea las columnas; las features de API/UI se revierten por revert de commit. El soft-delete sólo agrega una columna nullable → rollback no destructivo.

## Open Questions

- **S1 (registro público)**: ¿El auto-registro es realmente abierto a cualquier estudiante con email institucional, o requiere pre-aprobación / lista blanca de `id_institucional`? (Asumido: abierto con validación de dominio.) **Confirmar con el dueño.**
- **S2 (alcance del registro)**: ¿Hace falta verificación de email, recuperación de password, o rate-limiting en v1? (Asumido: NO, fuera de scope.) **Confirmar.**
- **S3 (post-registro)**: ¿Tras registrarse, auto-login (devolver tokens) o redirigir al login? (Asumido: redirigir al login.) **Confirmar.**
- **S4 (dominio de email)**: ¿Un único dominio (`frm.utn.edu.ar`) o varios sub-dominios institucionales? (Asumido: configurable, uno por env.) **Confirmar.**
- **S5 (baja)**: ¿La baja debe poder revertirse (reactivar usuario) desde la UI? (Asumido: soft-delete reversible a nivel datos, pero la UI de reactivación queda fuera de scope salvo pedido.)
