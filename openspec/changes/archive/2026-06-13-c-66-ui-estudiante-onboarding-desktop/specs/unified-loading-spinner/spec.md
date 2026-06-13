## ADDED Requirements

### Requirement: Componente `LoadingSpinner` reutilizable

El sistema SHALL proveer un componente `LoadingSpinner` en `frontend/src/ui/components.tsx` con la firma `<LoadingSpinner size?: 'sm' | 'md' | 'lg' label?: string />`. El spinner SHALL renderizar internamente: `<Icon name="progress_activity" className="ae-spin text-primary text-[XX]" />` envuelto en `<div className="flex items-center justify-center py-xl gap-sm text-on-surface-variant">`. El tamaño `XX` SHALL ser 20/32/48 px para `sm`/`md`/`lg` respectivamente. El label opcional SHALL renderizar como texto al lado o debajo del spinner (a definir en implementación).

#### Scenario: Spinner default es md morado centrado
- **WHEN** se renderiza `<LoadingSpinner />`
- **THEN** el DOM resultante contiene un `<Icon>` con clases `ae-spin text-primary text-[32px]` envuelto en un contenedor flex centered

#### Scenario: Spinner con label muestra texto
- **WHEN** se renderiza `<LoadingSpinner label="Cargando perfil…" />`
- **THEN** el DOM contiene el spinner + el texto "Cargando perfil…" visible

#### Scenario: Spinner pequeño (sm) usa 20px
- **WHEN** se renderiza `<LoadingSpinner size="sm" />`
- **THEN** el icono usa `text-[20px]`

### Requirement: Todas las pantallas del estudiante usan `LoadingSpinner`

Cada pantalla del workflow del estudiante (`StudentProfile.tsx`, `Consent.tsx`, `EnrollmentConsentStep.tsx`, `EnrollmentBiometricStep.tsx`, `EnrollmentDniStep.tsx`, dashboard) cuando esté en estado de carga (loading), SHALL renderizar `<LoadingSpinner />` en lugar de un spinner local ad-hoc. Los spinners pre-existentes en estas pantallas SHALL ser reemplazados por el componente reutilizable.

#### Scenario: StudentProfile.tsx usa LoadingSpinner
- **WHEN** `StudentProfile.tsx` está en estado `paso === 'cargando'`
- **THEN** renderiza `<LoadingSpinner label="Cargando perfil…" />` en lugar del spinner inline actual con `text-[24px]` gris

#### Scenario: EnrollmentConsentStep.tsx usa LoadingSpinner
- **WHEN** `EnrollmentConsentStep.tsx` está procesando/cargando
- **THEN** renderiza `<LoadingSpinner />` en lugar del spinner inline actual

#### Scenario: Botones con spinner inline mantienen su patrón
- **WHEN** un botón "Registrando…" muestra un spinner DENTRO del botón mientras procesa
- **THEN** ese spinner puede seguir siendo inline (`<Icon name="progress_activity" className="ae-spin text-[20px]" />`) porque es UI de botón, no de pantalla de carga — el componente `LoadingSpinner` aplica a estados de "pantalla en carga", no a botones individuales
