## MODIFIED Requirements

### Requirement: El paso de escaneo de DNI captura frente y dorso del documento
El sistema SHALL presentar el paso de escaneo de DNI cuando `ENABLE_DNI_SCAN` es `true` (default). El paso SHALL capturar el FRENTE y el DORSO del DNI mediante dos llamadas secuenciales a `CameraSnapshotCapture` con `shape='rect'`, `scannerCorners=true` y `aspectRatio=85.6/54`. Al completarse, SHALL llamar `api.guardarEscaneDNI(frente, dorso)` y retornar `EscaneDNI` con `imagen_frente` e `imagen_dorso`. El escaneo SHALL ser OPCIONAL y NO SHALL bloquear `perfil_completo`.

#### Scenario: Paso DNI visible cuando ENABLE_DNI_SCAN es true
- **WHEN** `ENABLE_DNI_SCAN !== '0'` (default activo)
- **THEN** el paso de DNI muestra el flujo de captura (no el banner "Próximamente")

#### Scenario: Paso DNI muestra "Próximamente" cuando ENABLE_DNI_SCAN es false
- **WHEN** `VITE_ENABLE_DNI_SCAN=0` en el entorno
- **THEN** el paso muestra el banner "Verificación documental — Próximamente" con botón "Continuar sin DNI"

#### Scenario: Flujo completa ambos lados antes de guardar
- **WHEN** el alumno confirma frente y dorso
- **THEN** `api.guardarEscaneDNI(imagenFrente, imagenDorso)` es invocado con ambos dataURLs
- **THEN** `enrollment.dni.captura_completada` es `true`

#### Scenario: Omitir DNI no bloquea el perfil
- **WHEN** el alumno hace clic en "Omitir este paso" o cancela durante la captura
- **THEN** `enrollment.perfil_completo` no cambia (gate depende solo de consentimiento + biometría)

#### Scenario: Estado completado muestra fecha y confirmación de frente+dorso
- **WHEN** `enrollment.dni.captura_completada` es `true`
- **THEN** el estado `completado` del paso muestra "DNI registrado (frente y dorso)" y la fecha de captura

## ADDED Requirements

### Requirement: api.guardarEscaneDNI acepta frente y dorso como parámetros separados
La función `api.guardarEscaneDNI` SHALL aceptar dos parámetros: `frente: string` y `dorso: string`. SHALL retornar `Promise<EscaneDNI>` con `imagen_frente`, `imagen_dorso`, `captura_completada: true` y `fecha_captura` en ISO 8601. En modo demo SHALL completar en ~400ms simulando cifrado server-side.

#### Scenario: guardarEscaneDNI construye EscaneDNI con ambos lados
- **WHEN** `api.guardarEscaneDNI(frente, dorso)` es invocado
- **THEN** retorna `{ captura_completada: true, imagen_frente: frente, imagen_dorso: dorso, fecha_captura: <ISO> }`

#### Scenario: ENABLE_DNI_SCAN default true sin variable de entorno
- **WHEN** `VITE_ENABLE_DNI_SCAN` no está definida en el entorno
- **THEN** `ENABLE_DNI_SCAN` es `true` (evaluado como `import.meta.env.VITE_ENABLE_DNI_SCAN !== '0'`)
