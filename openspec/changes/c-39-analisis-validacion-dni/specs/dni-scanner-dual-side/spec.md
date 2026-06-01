## MODIFIED Requirements

### Requirement: El paso de escaneo de DNI captura frente y dorso del documento
El sistema SHALL presentar el paso de escaneo de DNI cuando `ENABLE_DNI_SCAN` es `true` (default). El paso SHALL capturar el FRENTE y el DORSO del DNI mediante dos llamadas secuenciales a `CameraSnapshotCapture` con `shape='rect'`, `scannerCorners=true` y `aspectRatio=85.6/54`. Al completarse la captura del dorso, SHALL llamar `api.guardarEscaneDNI(frente, dorso)` seguido de `api.analizarDNI()` que produce un `AnalisisDNI`. El escaneo SHALL ser OPCIONAL y NO SHALL bloquear `perfil_completo`. El flujo SHALL incluir las fases: `'inicio'` → `'analizando'` → `'resultado'`, donde `'analizando'` muestra el spinner durante `api.analizarDNI()` y `'resultado'` muestra el panel completo.

#### Scenario: Paso DNI visible cuando ENABLE_DNI_SCAN es true
- **WHEN** `ENABLE_DNI_SCAN !== '0'` (default activo)
- **THEN** el paso de DNI muestra el flujo de captura (no el banner "Próximamente")

#### Scenario: Paso DNI muestra "Próximamente" cuando ENABLE_DNI_SCAN es false
- **WHEN** `VITE_ENABLE_DNI_SCAN=0` en el entorno
- **THEN** el paso muestra el banner "Verificación documental — Próximamente" con botón "Continuar sin DNI"

#### Scenario: Flujo completa ambos lados antes de guardar y analizar
- **WHEN** el alumno confirma frente y dorso
- **THEN** `api.guardarEscaneDNI(imagenFrente, imagenDorso)` es invocado con ambos dataURLs
- **THEN** `api.analizarDNI()` es invocado inmediatamente después mostrando fase 'analizando'
- **THEN** al completar el análisis, se muestra la fase 'resultado' con el panel

#### Scenario: Omitir DNI no bloquea el perfil
- **WHEN** el alumno hace clic en "Omitir este paso" o cancela durante la captura
- **THEN** `enrollment.perfil_completo` no cambia (gate depende solo de consentimiento + biometría)

#### Scenario: Estado completado ya existente muestra panel de resultados
- **WHEN** `enrollment.dni.captura_completada` es `true` y `enrollment.dni.analisis` existe
- **THEN** el estado inicial del paso muestra directamente el panel de resultados del análisis previo

#### Scenario: Estado completado sin análisis muestra confirmación básica
- **WHEN** `enrollment.dni.captura_completada` es `true` pero `enrollment.dni.analisis` es undefined
- **THEN** el estado muestra la confirmación básica "DNI registrado (frente y dorso)" con opción de re-analizar

## ADDED Requirements

### Requirement: Fase analizando con spinner en EnrollmentDniStep
El componente `EnrollmentDniStep` SHALL incluir la fase `'analizando'` que muestra un spinner y el texto "Verificando documento…" mientras `api.analizarDNI()` está en progreso. La transición a la fase `'analizando'` SHALL ser inmediata tras guardar el escaneo, sin intervención del usuario.

#### Scenario: Transición automática a fase analizando
- **WHEN** `handleDorsoCapturado` completa el guardado del escaneo
- **THEN** la fase cambia a `'analizando'` mostrando el spinner antes de que el usuario realice ninguna acción

#### Scenario: Fase analizando no tiene botón de cancelar
- **WHEN** la fase `'analizando'` está activa
- **THEN** NO SHALL mostrarse un botón de cancelar (el análisis es automático y rápido)

### Requirement: api.guardarEscaneDNI acepta frente y dorso como parámetros separados (sin cambio)
La función `api.guardarEscaneDNI` SHALL aceptar dos parámetros: `frente: string` y `dorso: string`. SHALL retornar `Promise<EscaneDNI>` con `imagen_frente`, `imagen_dorso`, `captura_completada: true` y `fecha_captura` en ISO 8601. En modo demo SHALL completar en ~400ms. El campo `analisis` NO es retornado por esta función; se completa mediante `api.analizarDNI()` separado.

#### Scenario: guardarEscaneDNI construye EscaneDNI sin analisis
- **WHEN** `api.guardarEscaneDNI(frente, dorso)` es invocado
- **THEN** retorna `{ captura_completada: true, imagen_frente: frente, imagen_dorso: dorso, fecha_captura: <ISO> }` sin campo `analisis`

### Requirement: EscaneDNI extiende con campo analisis opcional
El tipo `EscaneDNI` en `types.ts` SHALL incluir el campo opcional `analisis?: AnalisisDNI`. El campo es `undefined` hasta que `api.analizarDNI()` completa y se adjunta el resultado.

#### Scenario: EscaneDNI inicial sin analisis
- **WHEN** `api.guardarEscaneDNI` retorna el escaneo
- **THEN** el campo `analisis` es `undefined` (no incluido en el objeto)

#### Scenario: EscaneDNI con analisis adjunto al notificar
- **WHEN** `api.analizarDNI()` completa y se llama `onEscaneado`
- **THEN** el objeto `EscaneDNI` pasado a `onEscaneado` incluye `analisis: AnalisisDNI` con todos los campos
