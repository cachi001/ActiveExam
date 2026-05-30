# Design — C-21 `frontend-inscripcion-rediseno`

> Decisiones de diseño del refinamiento del frontend de demo. Alcance: capa de presentación React sobre la API mock ([[frontend-demo-mock-layer]]). No backend.

## Contexto

El frontend (`frontend/src`) corre contra `lib/api.ts` (mock en memoria, mismos esquemas/enums que el backend) con router por hash propio (`lib/router.tsx`) y store Zustand (`lib/store.ts`). Pantallas en `screens/`, UI kit en `ui/components.tsx`, layouts en `ui/shells.tsx`, navegador de demo en `ui/ScreenNavigator.tsx`. La lógica cliente real (visión, liveness, detectores, transporte) está cableada en `Examen.tsx`/`Biometria.tsx` y NO se reescribe: solo se ajustan tipos si bloquean el build.

## Decisión 1 — Reorden del flujo del estudiante

**Flujo actual (a reemplazar):**
```
login → requisitos → consentimiento → biometría → sala-espera → examen → cierre
```
El consentimiento (paso 2) y la biometría (paso 3) viven dentro del pre-examen.

**Flujo objetivo:**
```
login → dashboard-estudiante
          ├── (inscribirse) → detalle-examen → consentimiento → inscripto ✓
          └── (rendir, si habilitado) → WIZARD PRE-EXAMEN
                                           requisitos → biometría → sala-espera → examen → cierre
```

- **El consentimiento se mueve a la inscripción.** `Consent.tsx` deja de ser un paso del pre-examen y pasa a ser un paso del flujo de inscripción (sub-vista de la inscripción a un examen).
- **El wizard pre-examen solo verifica.** Requisitos + biometría + sala de espera. Sin pantalla de consentimiento. El paso de biometría queda como **único gate** previo a rendir.
- **Gate de habilitación (demo):** para "rendir" un examen, el mock exige `inscripto === true && consentimiento_resuelto === true`. Si no, el dashboard ofrece "Inscribirse" en vez de "Rendir", y el wizard, si se entra sin habilitación, redirige al dashboard.

**Por qué:** alinea la demo con el proceso real (decisión legal al inscribirse, trámite operativo al rendir) y hace el consentimiento más libre (sin presión del examen inminente). No cambia ninguna garantía de C-08.

## Decisión 2 — Modelo de datos de demo (mock)

Extender `lib/api.ts` / `lib/types.ts` sin romper esquemas existentes:

- `Examen` gana, para la vista de estudiante: `descripcion`, `fecha_hora` (inicio programado), `modalidad_proctoring` (L2.5), `que_se_monitorea: string[]`, `cupo`, `aula_virtual`.
- Nueva entidad de demo `Inscripcion`: `{ id, examen_id, estudiante_id, estado: 'inscripto'|'consentimiento_pendiente'|'habilitado'|'rendido', consentimiento: { version, timestamp, hash, via_alternativa: boolean } | null, fecha_inscripcion }`.
- API mock nueva:
  - `api.examenesDisponibles()` → exámenes en estado `programado`/`en_curso` abiertos a inscripción.
  - `api.misInscripciones()` → inscripciones del estudiante actual (in-memory).
  - `api.inscribir(examenId)` → crea inscripción en estado `consentimiento_pendiente`.
  - `api.registrarConsentimientoInscripcion(inscripcionId, { afirmativo, via_alternativa })` → sella consentimiento (timestamp+hash simulado), pasa a `habilitado`; rechaza si no hay acción afirmativa (espejo de RN-CO-02 en demo).
  - `api.puedeRendir(examenId)` → bool del gate.
- La elección de "vía alternativa sin biometría" se registra como `via_alternativa: true` y, en el wizard, saltea el paso biométrico mostrando "verificación por proctor humano".

**Inmutabilidad (demo):** el consentimiento, una vez sellado, no se reescribe desde la UI; reinscribirse requiere una inscripción nueva. Es una simulación del registro inmutable de C-08 (no es la garantía real, que vive en el backend).

## Decisión 3 — Rediseño minimalista

Sobre el design system existente (tokens en `tailwind.config.js` + `ui/components.tsx`), sin cambiar la paleta base:

- **Jerarquía y aire**: reducir ruido visual, una acción primaria clara por pantalla, espaciado consistente con la escala de tokens.
- **Componentes reutilizados**: `Card`, `Button`, `Badge`, `Stat`, `Avatar`, `SeverityBadge` ya existen; el rediseño los usa de forma consistente en vez de estilos ad-hoc.
- **Estados**: cada pantalla con datos asíncronos define estado de **carga**, **vacío** y **error** (hoy faltan en varias).
- **Microcopy** en español rioplatense, claro y sobrio; sin jerga innecesaria.
- **Wizard**: indicador de pasos honesto (los pasos reales del wizard, no "2/7" heredado del flujo viejo).
- **ScreenNavigator**: actualizar las entradas para reflejar el flujo nuevo (dashboard, inscripción) y agrupar por rol.

## Decisión 4 — Fix del build

`npm run build` = `tsc && vite build`. Errores a resolver:

1. **`vitest` ausente**: las ~17 `*.test.ts` referencian `vitest` no instalado. **Opción elegida**: excluir los tests del `tsc` de build (vía `tsconfig` build separado o `exclude`) y dejar que corran con `vitest` cuando se instale, evitando agregar una dep pesada solo para typechequear. (Alternativa documentada: agregar `vitest` a devDeps. Se elige `exclude` para no inflar el bundle ni el lockfile en la etapa de demo; los tests no se borran.)
2. **Bug `data` indefinido** en `features/biometria/BiometricVerification.tsx` (~líneas 113/116): falta la llamada de verificación final que asigna `data`. Como este componente es **legacy y no se importa** en la app nueva, se corrige el tipo (declarar/await la respuesta) o se aísla del build. Se corrige correctamente para que compile sin cambiar el comportamiento de la app nueva.
3. **`lib` ES target** para `.at()` y otros: ajustar `tsconfig` `lib`/`target` a `ES2022` si hace falta.
4. **Variables sin usar**: limpiar o anotar las que rompan `noUnusedLocals`.

**Criterio de Done del build**: `npx tsc --noEmit` sin errores y `vite build` produciendo bundle. No se ejecuta el build automáticamente (regla dura #1): se deja listo y se corre solo cuando el usuario lo pida o para verificar el cierre.

## Decisión 5 — Rebrand UTN

Reemplazo mecánico + revisión de contexto en los 6 archivos con refs (`lib/api.ts`, `ui/shells.tsx`, `screens/Login.tsx`, `screens/Revisor.tsx`, `screens/ConfigureExam.tsx`, y `screens/html/StyleGuide.html` si aplica):

- "Universidad de Buenos Aires — UBA" → "Universidad Tecnológica Nacional — Regional Mendoza".
- "Ingresar con UBA ID" → "Ingresar con UTN ID".
- `@uba.ar` → `@frm.utn.edu.ar` (dominio de la Facultad Regional Mendoza).
- IDs `UBA-*` → `UTN-*`; `EX-UBA-*` → `EX-UTN-*` (incluido el generador en `ConfigureExam.tsx`).
- Cátedras genéricas de Medicina (Anatomía/Histología) → cátedras coherentes con UTN (carreras de ingeniería: Análisis Matemático, Algoritmos, Física, Sistemas Operativos, etc.).
- "UBA Medicina" (breadcrumb Revisor) → facultad/carrera UTN.

## Riesgos y mitigaciones

- **Romper la lógica real cableada** (visión/liveness/detectores): el rediseño no toca esa lógica; solo el shell de las pantallas `Biometria.tsx`/`Examen.tsx`. Mitigación: cambios de presentación, no de pipeline.
- **Divergencia demo vs backend**: el reorden vive en el mock; las specs de C-08/C-09 se actualizan para que el backend, al implementarse, siga el mismo orden. Mitigación: specs sincronizadas en este change.
- **Build "verde" pero app rota**: typecheck no garantiza runtime. Mitigación: verificación manual del flujo en dev server al cerrar (`npm run dev`).
