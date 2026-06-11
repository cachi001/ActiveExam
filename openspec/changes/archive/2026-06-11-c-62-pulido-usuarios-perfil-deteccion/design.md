## Context

C-61 introdujo el CRUD de usuarios y el auto-registro. Quedaron pendientes seis ítems de calidad de presentación y UX que este change cierra:

1. La lista de usuarios en `GestionUsuarios.tsx` usa flex-wrap plano sin estilo de tabla ni cards con identidad visual consistente.
2. El campo interno `auth_provider` ("jwt"/"local") es un detalle de infraestructura que no tiene significado para el administrador y fue expuesto por accidente.
3. El input de roles acepta texto libre, lo que genera errores de tipeo y no comunica los valores válidos al operador.
4. `PerfilHeaderCard` muestra solo `principal.nombre` ignorando el apellido, y el tipo `Principal` no declara `apellido`.
5. `GET /auth/me` no devuelve `nombre` ni `apellido`: el JWT propio (C-55) deliberadamente no los incluye en claims para minimizar el payload del token; los datos ya existen en `UsuarioModel` desde C-61 y deben exponerse via DB lookup en el endpoint.
6. `getConsentText` y `getEnrollment` en `api.ts` tienen `await delay(300)` y `await delay(250)` respectivamente; son artefactos del desarrollo mock que degradan la respuesta percibida.
7. `useDetectionHarness` inicializa `showFullMesh = false`; para diagnóstico, el mesh completo es más informativo y debería ser el default.

**Restricciones del stack relevantes:**
- No hay migración de base de datos: `nombre` y `apellido` ya existen en `UsuarioModel`.
- El JWT propio (C-55) no lleva `nombre`/`apellido` en claims por decisión deliberada (D3 de C-55: shape compatible con Keycloak, que sí lleva `given_name`/`family_name` pero no los mapea al dominio).
- `AuthenticatedPrincipal` es un `@dataclass(frozen=True, slots=True)` puro de dominio — agregar campos no requiere migración.
- `PrincipalResponse` usa `extra='forbid'` (regla dura); agregar campos es retrocompatible para clientes que ya usan la API.
- Tests backend: sin mocks de DB; usar postgres real (regla dura #4).

## Goals / Non-Goals

**Goals:**
- Tabla HTML responsive en desktop, cards estilizadas en mobile para la lista de usuarios.
- Ocultar `auth_provider` de la presentación (el campo permanece en tipos y backend).
- Checkboxes de roles con `ROL_LABELS` normalizados; etiquetas legibles en la lista.
- `PerfilHeaderCard` muestra "Nombre Apellido"; `Principal` agrega `apellido?: string`.
- `GET /auth/me` devuelve `nombre` y `apellido` via DB lookup por `subject` del token.
- Delays de consentimiento eliminados (`delay(0)` o sin `await delay`).
- `showFullMesh` por defecto `true` en el harness.

**Non-Goals:**
- No se modifica el JWT (los claims del token quedan igual; C-55 no se toca).
- No se añaden ni modifican columnas de base de datos.
- No se cambia el flujo de enrollment ni la lógica de consentimiento.
- No se implementa edición de foto desde `GestionUsuarios`.
- No se introduce paginación nueva ni filtros.

## Decisions

### D1 — `GET /auth/me` hace DB lookup para nombre y apellido

**Decisión**: El endpoint `GET /auth/me` acepta la dependencia `get_current_principal` (que ya valida el JWT), y agrega una query a `UsuarioModel` usando `principal.subject` (= `UsuarioModel.id`, UUID, claim `sub` del token) para obtener `nombre` y `apellido`.

**Alternativas consideradas:**
- *Poner nombre/apellido en el JWT*: incrementa el payload y requiere que el token se renueve para reflejar cambios de nombre. Descartado; el JWT propio tiene forma fija (D3 de C-55).
- *Leer `attrs_federados` del principal*: el JWT propio solo incluye `preferred_username` en `attrs_federados`, no nombre ni apellido. No aplica.
- *Retornar claims de Keycloak `given_name`/`family_name`*: el MVP usa auth propio, Keycloak es futuro. Inconsistente con el proveedor activo.

**Consecuencia**: `GET /auth/me` necesita acceso a `session_factory` (igual que `/auth/login` y `/auth/refresh`). Si no hay DB disponible, devuelve `nombre=null` y `apellido=null` (degradación graceful; no falla el endpoint).

### D2 — `AuthenticatedPrincipal` agrega `nombre` y `apellido` como Optional

**Decisión**: Agregar `nombre: str | None = None` y `apellido: str | None = None` al dataclass. `TokenPolicy.principal_desde_claims()` los deja en `None` (el JWT no los porta). `GET /auth/me` los sobreescribe desde la DB.

**Alternativa descartada**: No modificar `AuthenticatedPrincipal` y leer la DB solo en el endpoint. Preferimos que el value object de dominio sea extensible y refleje el estado completo del principal cuando esté disponible.

### D3 — Selector de roles como checkboxes (no `<select multiple>`)

**Decisión**: Tres checkboxes independientes (uno por rol: Estudiante, Proctor, Administrador del sistema). Más usable que un `<select multiple>` (que requiere Ctrl+Click para selección múltiple) y consistente con UX de formularios de admin simples.

**Constante centralizada**: `ROL_LABELS` en `frontend/src/lib/constants/roles.ts` como `Record<string, string>`. Se usa tanto en el formulario como en el render de la lista/tabla.

### D4 — Tabla HTML semántica con Tailwind responsive

**Decisión**: Usar `<table>` nativo con `hidden md:table` / `md:hidden` para alternar entre vista tabla (desktop) y cards (mobile). La tabla usa `<thead>/<tbody>/<tr>/<td>` semánticos; las cards mantienen el patrón existente con estilo de fondo blanco, borde sutil y sombra suave.

**Alternativa descartada**: CSS Grid que simula una tabla. Más complejidad sin beneficio semántico.

### D5 — Delays de consentimiento: reducir a cero, no eliminar la llamada

**Decisión**: Cambiar `await delay(300)` y `await delay(250)` a `await delay(0)` en lugar de eliminar la llamada `delay`. Preserva la estructura async para cuando USE_REAL_BACKEND=1 tome el camino real (que ya no tiene delay artificial). Efecto práctico: respuesta inmediata en modo demo.

### D6 — `showFullMesh` default `true` sin cambio de persistencia

**Decisión**: Cambiar solo el valor inicial de `useState(false)` a `useState(true)`. No se persiste esta preferencia en localStorage ni en el store. Es una herramienta de diagnóstico admin sin necesidad de recordar estado.

## Risks / Trade-offs

- **[Riesgo: DB lookup en /auth/me aumenta latencia]** → Mitigación: la query es por PK (UUID indexado); latencia adicional <1ms en postgres local. Degradación graceful si la DB no está disponible.
- **[Riesgo: extra='forbid' en PrincipalResponse rompe tests existentes]** → Mitigación: los campos `nombre` y `apellido` son opcionales (`str | None = None`); clientes existentes que no los esperan los ignoran.
- **[Riesgo: `AuthenticatedPrincipal` es frozen dataclass — agregar campos]** → Mitigación: agregar campos con default es compatible con `frozen=True`. Los tests que construyen `AuthenticatedPrincipal` manualmente no necesitan pasar los nuevos campos si tienen default.
- **[Riesgo: showFullMesh=true impacta performance en máquinas lentas]** → Aceptado. El harness es herramienta admin; el administrador puede apagarlo con el toggle existente.

## Migration Plan

1. Backend primero: extender `AuthenticatedPrincipal` → actualizar `PrincipalResponse` → extender `GET /auth/me`. Sin migraciones de BD.
2. Frontend: extender tipo `Principal` con `apellido` → actualizar `PerfilHeaderCard` → crear `roles.ts` → refactorizar `GestionUsuarios` (tabla + checkboxes + ocultar auth_provider) → eliminar delays → cambiar default mesh.
3. Tests: agregar test de integración para `GET /auth/me` verificando `nombre` y `apellido`.
4. Sin rollback especial: todos los cambios son aditivos o de presentación.

## Open Questions

- ¿El frontend debe mostrar `nombre` en el menú de navegación (avatar/header de shell) además de en `PerfilHeaderCard`? → Fuera de scope de este change; anotar como deuda.
- ¿Conviene agregar un índice en `UsuarioModel.id` si no existe ya? → `id` es la PK (UUID), ya tiene índice primario. No se requiere acción.
