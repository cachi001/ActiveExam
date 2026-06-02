## MODIFIED Requirements

### Requirement: Login visual layout — minimalista centrado con branding institucional
La pantalla de Login SHALL presentar un layout centrado en pantalla completa con:
- Card principal con `max-w-md`, sombra suave `shadow-card-lg`, borde `border-outline-variant/50`, radio `rounded-xl`, fondo `surface-container-lowest`
- Header de la card: ícono `school` en caja `bg-primary text-on-primary rounded-2xl`, seguido de `INSTITUTION.nombre — INSTITUTION.facultad` en `text-headline-md` y sigla institucional visible (ej. "UTN FRM")
- Sección institución: campo solo-lectura con ícono `account_balance` mostrando nombre institucional completo
- CTA principal: único botón `size="lg"` `w-full` con texto derivado de `INSTITUTION.loginLabel`
- Microcopy de privacidad: una sola línea `text-label-sm text-on-surface-variant text-center`
- Footer: badge "lock" + texto de privacidad condensado (Ley 25.326) en `bg-surface-container-low rounded-full`
- Efecto decorativo: glow orb en top-right con `opacity-40 blur-[100px] bg-primary-fixed-dim` (sin cambio)
- Animación de entrada: `animate-in fade-in slide-in-from-bottom-4 duration-700` en la card

La pantalla NO SHALL mostrar campos de usuario/contraseña (login federado vía Keycloak mock).

#### Scenario: Render inicial
- **WHEN** el usuario navega a `/login`
- **THEN** se muestra la card centrada con el nombre de la institución, el botón de ingreso habilitado y el microcopy de privacidad en una sola línea

#### Scenario: Estado cargando
- **WHEN** el usuario clickea "Ingresar con <loginLabel>" y `cargando === true`
- **THEN** el botón muestra spinner `progress_activity` + "Conectando con Keycloak…" y está deshabilitado

#### Scenario: Navegación post-login
- **WHEN** el login mock completa (`api.login` + `api.listExams`)
- **THEN** se navega a `/alumno/dashboard` sin parámetros adicionales
