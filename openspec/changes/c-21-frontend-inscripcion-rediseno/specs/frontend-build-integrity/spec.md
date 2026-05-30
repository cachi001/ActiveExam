# Spec — frontend-build-integrity

> El frontend buildea sin errores de tipos: tests resueltos fuera del `tsc` de build, bug `data` de `BiometricVerification.tsx` corregido y configuración de `tsconfig` adecuada.

## ADDED Requirements

### Requirement: El proyecto typechequea y buildea
El sistema (frontend) SHALL pasar `tsc --noEmit` sin errores y `vite build` SHALL producir un bundle; las suites de test que dependen de `vitest` NO SHALL romper el build de producción.

#### Scenario: Typecheck del código de aplicación
- **WHEN** se ejecuta `tsc --noEmit` sobre `src` (excluyendo archivos de test)
- **THEN** no se reportan errores de tipos

#### Scenario: Los tests no rompen el build
- **WHEN** se ejecuta el build de producción
- **THEN** los archivos `*.test.ts` que importan `vitest` no causan fallo del build

### Requirement: Sin variables indefinidas en componentes
El sistema NO SHALL contener referencias a variables indefinidas (p. ej. `data` en `BiometricVerification.tsx`); el componente legacy SHALL compilar sin alterar el comportamiento de la app nueva.

#### Scenario: Componente biométrico legacy compila
- **WHEN** `tsc` procesa `features/biometria/BiometricVerification.tsx`
- **THEN** no hay referencias a variables indefinidas y el archivo typechequea
