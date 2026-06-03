## ADDED Requirements

### Requirement: BiometricCapture notifica al caller con resultado biométrico completo
El componente `BiometricCapture` SHALL invocar el callback `onComplete` con la firma ampliada: `(landmarks: FaceLandmark[], frame: HTMLCanvasElement | null, passiveOk: boolean, retosResueltos: string[], virtualCameraDetected: boolean)`. Los callers del componente (verificación en `Biometria.tsx` y enrollment en el perfil del alumno) SHALL actualizar su handler para aceptar los nuevos parámetros.

#### Scenario: onComplete invocado con todos los parámetros reales
- **WHEN** el alumno completa todos los retos activos y el liveness pasivo tiene resultado
- **THEN** `onComplete` se invoca con `landmarks` del último frame, `frame` del canvas, `passiveOk` calculado, `retosResueltos` del `resueltosRef` y `virtualCameraDetected` del detector
- **THEN** el handler de `Biometria.tsx` recibe todos los parámetros sin errores TypeScript

#### Scenario: onComplete en modo fallback manual
- **WHEN** el motor falla y el alumno completa los retos en modo manual
- **THEN** `onComplete` se invoca con `passiveOk: false`, `retosResueltos` de los retos marcados manualmente, `virtualCameraDetected: false`
- **THEN** `landmarks` puede ser vacío (`[]`) si no hubo detección

#### Scenario: Caller de enrollment actualizado
- **WHEN** `BiometricCapture` se monta para el flujo de enrollment en el perfil del alumno
- **THEN** el handler `onComplete` del caller de enrollment acepta los 5 parámetros sin error de compilación TypeScript
- **THEN** el flujo de enrollment no se interrumpe aunque ignore `passiveOk` / `virtualCameraDetected`
