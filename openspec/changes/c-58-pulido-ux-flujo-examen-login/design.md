## Context

El flujo del alumno hoy es: `AlumnoMisExamenes` → botón "Rendir" (`handleRendir`) → `navigate('/requisitos')` (`EquipmentCheck`) → `navigate('/consentimiento')` (`Consent`) → `/biometria`. En esta cadena **nunca** se llama a `setExamenActivo`: el único caller de `setExamenActivo` en todo el front es `ExamList.tsx` (panel admin, para editar/crear exámenes). Por eso `Consent` lee `examenActivo = null` y `aceptar()` (`if (!acepto || !examen) return;`) queda inerte: el botón se tilda pero no avanza. **Esta es la causa raíz del bug bloqueante.**

Existen DOS consentimientos distintos y AMBOS deben conservarse:
- **Perfil** (`EnrollmentConsentStep` → `api.registrarConsentimientoPerfil(version, viaAlternativa)`): consentimiento general de tratamiento de datos biométricos. Produce un `AcuseConsentimiento { version, timestamp, hash, via_alternativa }` accesible vía `api.getEnrollment()` (`estado.consentimiento`).
- **Por-examen / por-rendición** (`Consent` → `api.recordConsent(examen.id)`): acuse atado a `examen.id`, parte de la cadena de custodia (RN-CC). Da finalidad concreta a esa instancia de tratamiento (Ley 25.326). NO se elimina.

Constraints del proyecto: cambios solo de presentación y wiring de estado; sin backend; sin migraciones; PascalCase en componentes React; reutilizar `frontend/src/ui/components.tsx` (`Icon`, `FormField`, `Button`, `Card`, `Badge`); clase global `.input` (`frontend/src/index.css`); acción afirmativa nunca pre-marcada (RN-CO-02); el acuse por-rendición es obligatorio (RN-CC). No buildear ni commitear sin pedido.

## Goals / Non-Goals

**Goals:**
- Desbloquear el flujo del examen seteando `examenActivo` antes de llegar a `/consentimiento`.
- Que el consentimiento del examen sea de **1 click** cuando el alumno ya consintió el tratamiento en el perfil con la versión vigente, **conservando** el registro de `recordConsent(examen.id)`.
- Eliminar elementos visuales redundantes (flecha direccional + label contextual en liveness) y la pantalla de spinner intermedia del consentimiento.
- Login con toggle mostrar/ocultar contraseña e inputs unificados al patrón del sistema.
- Tarjetas de "Mis exámenes" sin desbordes en mobile (<360px).

**Non-Goals:**
- Gestión de usuarios (GET/PUT/DELETE users, UI admin, avatar) → C-59.
- Cambiar el contrato de los acuses ni eliminar ninguno de los dos consentimientos.
- Tocar el motor de visión/liveness (solo se quita chrome de presentación).
- Cambiar backend, tipos, migraciones o la lógica del gate `puedeRendir`.

## Decisions

### D1 — Fix del bug `examenActivo`: setear el examen en `handleRendir`, no en `Consent`

`AlumnoMisExamenes.handleRendir(inscripcion)` ya tiene la `Inscripcion` y ya pasó el gate (`gate.puede`). Antes de `navigate('/requisitos')` se resuelve el `Examen` del catálogo y se setea en el store.

- **Cómo obtener el `Examen`**: `await api.getExam(inscripcion.examen_id)`. Si por algún motivo retorna `undefined` (catálogo mock acotado), se construye un `Examen` mínimo derivado de la `Inscripcion` (id, nombre desde `nombre_examen`, `estado: 'en_curso'`, campos restantes con defaults seguros) para no romper el flujo. Se setea con `setExamenActivo(examen)`.
- **Por qué acá y no en `Consent`**: `handleRendir` es el punto donde el alumno elige rendir un examen concreto; es el lugar semánticamente correcto para fijar el examen activo de la sesión. `EquipmentCheck` (paso intermedio) no conoce el examen. Setear en `Consent` vía `useEffect` sería tardío y frágil (Consent ya asume que el examen existe).
- **Alternativa descartada**: pasar el `examen_id` por la URL/router. El router es hash sin params dinámicos (documentado en el store para `proctoringExamId`); meter params rompería el patrón. Zustand es el canal establecido para este acoplamiento.
- **Defensa adicional en `Consent`**: si aún así `examenActivo` es null al montar (entrada directa por deep-link), `aceptar()` no debe quedar mudo; se documenta como guard pero el fix principal es D1. (Se mantiene el `return` defensivo; el caso normal ya no lo dispara.)

### D2 — Consentimiento de examen liviano: derivar el estado client-side, sin backend

El estado "ya consintió el tratamiento + versión vigente" se deriva de datos ya disponibles:
- `api.getEnrollment()` → `estado.consentimiento: AcuseConsentimiento | null` (tiene `version`, `timestamp`, `via_alternativa`).
- `api.getConsentText()` → `texto.version` (= `CONSENT_TEXT.version`, fuente de la versión vigente).

Regla de la rama liviana en `Consent`:
```
yaConsintioPerfil = consentimiento != null
                    && (consentimiento.via_alternativa || consentimiento.version === texto.version)
```
- Si `yaConsintioPerfil` → render **liviano**: tarjeta corta con la fecha del acuse de perfil ("Ya consentiste el tratamiento de tus datos el {fecha}") + checkbox afirmativo corto ("Confirmo que acepto ser supervisado en esta evaluación", RN-CO-02 nunca pre-marcado) + botón "Confirmar y continuar". Al confirmar: `await api.recordConsent(examen.id)` y `navigate('/biometria')`. **El acuse por-rendición se sigue registrando.**
- Si NO `yaConsintioPerfil` (no consintió en perfil, o la versión cambió) → render **completo** (bloques + texto largo) como hoy.
- **Por qué reutilizar la versión del perfil**: `via_alternativa === true` también cuenta como consentimiento de perfil válido (consistente con `recalcularPerfilCompleto` en `api.ts`). Si la versión del texto cambió respecto al acuse de perfil, NO se considera vigente → se muestra el completo, forzando re-lectura (consistente con el gate `consentimiento_version_desactualizada`).
- **Alternativa descartada**: nuevo endpoint backend para "¿ya consintió?". Innecesario: el dato ya viaja en `getEnrollment()`. Agregar backend violaría el alcance (frontend puro) y sumaría superficie.

### D3 — Quitar el spinner intermedio del consentimiento sin bloquear el render

- `EnrollmentConsentStep`: eliminar la rama `if (cargandoTexto) return <spinner/>`. El layout (encabezado + grilla de bloques + acción) se renderiza de una; los bloques salen de `texto?.bloques ?? []` (ya soporta `texto` null → grilla vacía). Mientras `texto` es null, el encabezado y el área de bloques aparecen; cuando llega `texto`, los bloques se rellenan (render progresivo). Se elimina el estado `cargandoTexto`.
- `Consent`: ya renderiza el layout sin spinner global (solo el inline "Cargando texto de consentimiento…" en la grilla, línea 60). Se reemplaza ese texto por un placeholder neutro o se omite (la grilla simplemente queda vacía hasta que llega `texto`), evitando jerga de carga.
- **Trade-off**: durante ~300ms (delay mock) la grilla de bloques está vacía. Aceptable: el encabezado, la versión y la acción ya son visibles; no hay salto de layout disruptivo. Se puede agregar un skeleton ligero (placeholders gris) si se quiere pulir, pero no es bloqueante.

### D4 — Liveness: quitar flecha direccional y label contextual (solo presentación)

- `CaptureProgress`: eliminar el bloque `{!enExito && !cooldownActivo && turnDirection && (...)}` (líneas 78-90) que renderiza `←`/`→` y "hacia la izquierda/derecha". La prop `turnDirection` puede quedar sin uso visual; se evalúa quitarla de la interfaz `CaptureProgressProps` y del paso desde `CaptureOverlay` para no dejar props muertas (decisión de limpieza: quitar la prop si ningún otro consumidor la usa).
- `CaptureOverlay`: eliminar el `<p>` con `contextLabel` (líneas 84-86) de la barra superior; el botón "Cancelar" queda alineado a la derecha (`justify-end` o `justify-between` con un spacer). Evaluar quitar la prop `contextLabel` de `CaptureOverlayProps` si ningún caller la sigue pasando con sentido.
- **Por qué**: la detección de giro funciona igual; la flecha y el label eran chrome redundante. NO se toca la lógica de `liveness`/detección.
- **Riesgo de props muertas**: se verifica en `apply` quién pasa `turnDirection`/`contextLabel` (BiometricCapture) antes de borrar la prop; si se borra, se actualiza el caller.

### D5 — Login: toggle de contraseña + inputs al patrón del sistema

- En `FormularioJwt` (`Login.tsx`): el `<input type="password">` pasa a `type={verPassword ? 'text' : 'password'}` con estado local `verPassword`. Se agrega un botón de ojo (`<Icon name="visibility" />` / `visibility_off`) posicionado dentro del campo (contenedor `relative`, botón `absolute` a la derecha), `type="button"`, `aria-label` "Mostrar/Ocultar contraseña".
- Inputs migrados al patrón del sistema: envolver cada campo en `FormField label=...` (de `ui/components.tsx`) y aplicar la clase global `.input` (de `index.css`) en lugar de las clases Tailwind hardcodeadas inline. Mantener `autoComplete` (`username` / `current-password`), `required`, `disabled={loading}` y los `id`/`htmlFor` para accesibilidad.
- **Alcance**: solo `FormularioJwt`. `SelectorRolDemo` y `LoginKeycloak` no tienen inputs de texto → sin cambios.
- **Alternativa descartada**: crear un componente `PasswordField` nuevo. Para un solo campo es sobre-ingeniería; el toggle inline + `FormField` existente alcanza. Si C-59 necesita reuso, se extrae entonces.

### D6 — Mis Exámenes responsive: breakpoints + truncado, tokens del sistema

- `InscripcionCard`: la fila `<div className="flex items-start gap-md">` ya tiene `flex-1 min-w-0` en el bloque de texto; el `Badge` puede desbordar. Cambios: permitir que el badge baje en mobile (`flex-wrap` o estructura `flex-col sm:flex-row`), agregar `truncate`/`line-clamp-2` a `nombre_examen` y `nombre_materia`. La fila de acción (`flex items-center gap-sm`) pasa a `flex-col sm:flex-row` para que el `<p>` de razón y el `Button` no compriman en pantallas chicas.
- `ExamenCard`: `<Card className="flex items-center gap-md">` con `Badge` + `Button` en row se desborda. Cambios: `flex-col sm:flex-row`, `min-w-0` + `truncate` en el nombre, y el cluster de la derecha con `flex-wrap` / `shrink-0` según corresponda.
- Tokens: usar los `gap-*`, `on-surface`, `on-surface-variant`, etc. existentes; no introducir valores mágicos.
- **Criterio de aceptación visual**: a 360px de ancho, ningún texto ni control se sale del `Card`; los nombres largos truncan con elipsis.

## Risks / Trade-offs

- **[Borrar `turnDirection`/`contextLabel` rompe el caller (BiometricCapture)]** → En `apply`, primero grep de los callers; si se eliminan las props, se actualiza `BiometricCapture` en el mismo paso. Si hay dudas, se deja la prop pero se elimina solo el render (más conservador).
- **[`api.getExam` retorna `undefined` para la inscripción]** → Fallback: construir `Examen` mínimo desde la `Inscripcion`. El flujo no se rompe; `Consent` solo necesita `examen.id` para `recordConsent`.
- **[Rama liviana saltea la re-lectura del texto largo]** → Es la decisión del dueño: el alumno ya leyó y consintió el tratamiento en el perfil; el acuse por-rendición sigue registrándose con su propio timestamp/hash (cadena de custodia intacta). Si la versión cambió, se cae al flujo completo (no se saltea nunca un texto nuevo).
- **[Grilla de bloques vacía durante el fetch]** → Ventana de ~300ms; encabezado y acción visibles; sin salto de layout grave. Opcional: skeleton.
- **[Regresión de accesibilidad en login al migrar inputs]** → Mantener `id`/`htmlFor`, `autoComplete`, `aria-label` del toggle; el `FormField` aporta el `<label>`.

## Migration Plan

Cambios puramente de frontend, sin migraciones de datos ni feature flags. Despliegue normal del bundle. Rollback = revertir el commit del change. No hay estado persistido nuevo.

## Open Questions

- ¿Se quiere un skeleton (placeholders grises animados) en lugar de grilla vacía durante el fetch del consentimiento, o alcanza con el render progresivo? (Default propuesto: render progresivo simple; skeleton opcional, no bloqueante.)
- En el render liviano del consentimiento de examen, ¿se muestra también un enlace "ver texto completo" para el alumno que quiera releer? (Default propuesto: sí, un link discreto que expande/lleva al texto completo, sin bloquear el 1 click — confirmar con el dueño en apply.)
