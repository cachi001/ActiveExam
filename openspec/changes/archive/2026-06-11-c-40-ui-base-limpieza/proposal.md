## Why

El frontend expone jerga interna de desarrollo ("demo", "stub", "Ej:") directamente al usuario final, tiene un sistema de botones con un único tamaño que produce layouts rotos (botones gigantes y pegados), carece de primitivas de formulario reutilizables, y expone herramientas de desarrollo (ScreenNavigator, simulación de deriva de embedding) sin control de visibilidad. Este change sienta la base de UI minimalista/moderna antes de cualquier iteración de pantallas específicas.

## What Changes

- **Jerga eliminada**: Se reformulan 7 strings visibles al usuario que contienen "demo", "stub", "Ej:" o "modo demo" en StudentProfile, EnrollmentDniStep, EquipmentCheck, ScreenNavigator, AdminDetectionHarness y ConfigureExam. Los disclaimers legales L2.5 se conservan íntegros.
- **Sistema de tamaños de Button**: Se agrega prop `size?: 'sm' | 'md' | 'lg'` al componente `Button` en `ui/components.tsx`. Default `'md'` reproduce el comportamiento actual (`h-12 px-lg`). `'sm'` usa `h-9 px-md` (ya se usa ad-hoc con `className`). `'lg'` es `h-14 px-xl` (normaliza el `h-14` hardcodeado de Login.tsx).
- **Gaps en stacks de botones**: Los bloques `w-full` apilados sin gap en AdminDashboard (acciones rápidas, :57-59) y otros se corrigen con `gap-sm` / `space-y-sm`.
- **Primitivas de formulario**: Se crean dos nuevos componentes en `ui/`: `FormField` (label + control + hint/error reutilizable) y `RangeInput` (slider con label dinámico y valor). Reemplazan el `Field` local de ConfigureExam y el slider ad-hoc.
- **Flag VITE_DEV_TOOLS**: Nueva variable de entorno (default `'0'`, OFF en producción/demo) que controla la visibilidad de herramientas de desarrollo: ScreenNavigator flotante y el bloque "Control de demostración" (simular deriva embedding) en StudentProfile. Cuando está OFF, los componentes no se renderizan; no hay efectos ni lógica residual.

## Capabilities

### New Capabilities

- `button-size-system`: Prop `size` en Button con tokens del design system (sm/md/lg) y corrección de stacks sin gap.
- `form-primitives`: Componentes reutilizables `FormField` y `RangeInput` para formularios consistentes.
- `dev-tools-flag`: Flag `VITE_DEV_TOOLS` que oculta ScreenNavigator y controles de simulación en entornos no-dev.
- `visible-jargon-cleanup`: Limpieza de strings de UI con jerga de desarrollo; conserva disclaimers L2.5.

### Modified Capabilities

- `student-profile-shell`: El bloque "Control de demostración" (simular deriva embedding) queda condicional a `VITE_DEV_TOOLS`. El texto "Disponible próximamente" se reformula (sin cambio de comportamiento funcional).
- `login-portal-reframe`: El botón de ingreso migra de `h-14` hardcodeado a `size="lg"` del sistema.

## Impact

- `frontend/src/ui/components.tsx` — Button, nuevos FormField y RangeInput
- `frontend/src/ui/ScreenNavigator.tsx` — condicionado a `VITE_DEV_TOOLS`
- `frontend/src/App.tsx` — pasa el flag al ScreenNavigator (o lo omite)
- `frontend/src/screens/Login.tsx` — normaliza `h-14` a `size="lg"`
- `frontend/src/screens/AdminDashboard.tsx` — gap en acciones rápidas
- `frontend/src/screens/ConfigureExam.tsx` — usa FormField/RangeInput, placeholders sin "Ej:"
- `frontend/src/screens/StudentProfile.tsx` — bloque demo condicional, texto "próximamente" reformulado
- `frontend/src/screens/EquipmentCheck.tsx` — quita "(modo demo)" del mensaje de fallas
- `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — reformula headers "(demo)" preservando disclaimers
- `frontend/src/screens/AdminDetectionHarness.tsx` — reformula mensaje "señales del stub"
- `frontend/.env.example` (o `vite.config`) — documenta `VITE_DEV_TOOLS=0`
- Sin cambios de backend. Sin cambios de API. Sin breaking changes para el usuario.
