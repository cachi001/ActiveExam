## ADDED Requirements

### Requirement: DEV_TOOLS_ENABLED flag
El sistema SHALL leer la variable de entorno `VITE_DEV_TOOLS` (string Vite) y exponerla como constante booleana `DEV_TOOLS_ENABLED` en el módulo `src/lib/devConfig.ts`. El valor `'1'` habilita las herramientas; cualquier otro valor (incluyendo `undefined`) las deshabilita. El módulo SHALL ser el único punto de acceso al flag en el frontend.

```
DEV_TOOLS_ENABLED = import.meta.env.VITE_DEV_TOOLS === '1'
```

#### Scenario: Flag off by default
- **WHEN** la variable `VITE_DEV_TOOLS` no está definida en el entorno
- **THEN** `DEV_TOOLS_ENABLED` es `false`

#### Scenario: Flag on with value 1
- **WHEN** `VITE_DEV_TOOLS=1` está definido en el entorno de build
- **THEN** `DEV_TOOLS_ENABLED` es `true`

#### Scenario: Flag off with value 0
- **WHEN** `VITE_DEV_TOOLS=0` está definido en el entorno de build
- **THEN** `DEV_TOOLS_ENABLED` es `false`

### Requirement: ScreenNavigator conditioned on flag
El componente `ScreenNavigator` SHALL renderizarse en `App.tsx` únicamente cuando `DEV_TOOLS_ENABLED === true`. Cuando el flag está desactivado, el componente NO MUST renderizarse en el DOM (no solo estar oculto con CSS).

#### Scenario: Navigator absent when flag off
- **WHEN** `DEV_TOOLS_ENABLED` es `false`
- **THEN** el botón flotante del ScreenNavigator no aparece en el DOM

#### Scenario: Navigator present when flag on
- **WHEN** `DEV_TOOLS_ENABLED` es `true`
- **THEN** el botón flotante del ScreenNavigator aparece en la esquina inferior derecha

### Requirement: Embedding drift simulation conditioned on flag
El bloque de "Control de demostración / simular deriva embedding" en `StudentProfile` SHALL renderizarse únicamente cuando `DEV_TOOLS_ENABLED === true` (además de las condiciones biométricas existentes). Cuando el flag está desactivado, el bloque no aparece en el DOM.

#### Scenario: Simulation block absent when flag off
- **WHEN** `DEV_TOOLS_ENABLED` es `false` y `biometriaOk` es `true`
- **THEN** el bloque de simulación de deriva no aparece en el perfil del alumno

#### Scenario: Simulation block present when flag on
- **WHEN** `DEV_TOOLS_ENABLED` es `true` y `biometriaOk` es `true` y la biometría no está caducada
- **THEN** el bloque de simulación de deriva aparece en el perfil del alumno

### Requirement: No functionality loss when flag off
Cuando `DEV_TOOLS_ENABLED` es `false`, MUST NO existir efectos secundarios, errores de consola ni lógica bloqueada por la ausencia de las herramientas. El flujo completo de estudiante y administrador MUST funcionar igual que con el flag activo.

#### Scenario: Student flow unaffected
- **WHEN** `DEV_TOOLS_ENABLED` es `false` y el alumno completa el flujo de examen
- **THEN** todas las pantallas del flujo funcionan correctamente sin el ScreenNavigator

### Requirement: env.example documents the flag
El archivo `.env.example` del proyecto frontend SHALL incluir la variable `VITE_DEV_TOOLS=0` con un comentario que explique su propósito y que para desarrollo local puede activarse con `VITE_DEV_TOOLS=1` en `.env.local`.

#### Scenario: env.example has the flag
- **WHEN** se lee `frontend/.env.example`
- **THEN** contiene la línea `VITE_DEV_TOOLS=0` o `# VITE_DEV_TOOLS=0` con comentario
