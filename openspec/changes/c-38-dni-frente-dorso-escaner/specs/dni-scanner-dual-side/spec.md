## ADDED Requirements

### Requirement: El alumno puede escanear el frente y dorso del DNI de forma secuencial
El sistema SHALL presentar un flujo de dos capturas secuenciales: primero el FRENTE del DNI, luego el DORSO. Cada captura SHALL usar el componente `CameraSnapshotCapture` con `shape='rect'`, `scannerCorners=true` y `aspectRatio=85.6/54` (tarjeta ID-1/CR80). El flujo SHALL ser: capturar frente → preview/confirmar frente → capturar dorso → preview/confirmar dorso → guardar ambos.

#### Scenario: Flujo inicia solicitando el frente del DNI
- **WHEN** el alumno activa el escaneo de DNI (ENABLE_DNI_SCAN activo)
- **THEN** se muestra `CameraSnapshotCapture` con instrucción "Colocá el FRENTE de tu DNI dentro del marco" y `scannerCorners=true`

#### Scenario: Confirmar frente avanza al dorso
- **WHEN** el alumno confirma la foto del frente en el preview
- **THEN** `CameraSnapshotCapture` se cierra y se vuelve a montar con instrucción "Ahora girá el DNI y colocá el DORSO dentro del marco"

#### Scenario: Confirmar dorso guarda el escaneo completo
- **WHEN** el alumno confirma la foto del dorso en el preview
- **THEN** `api.guardarEscaneDNI(frente, dorso)` es llamado con los dos dataURLs
- **THEN** el estado pasa a `completado` con `captura_completada: true`, `imagen_frente` e `imagen_dorso` poblados

#### Scenario: Cancelar en frente o dorso vuelve al estado inicio
- **WHEN** el alumno cancela durante la captura del frente o del dorso
- **THEN** `CameraSnapshotCapture` se desmonta y el flujo regresa al estado `inicio` (sin perder la imagen ya capturada del otro lado si existe)

### Requirement: El marco de escaneo DNI tiene aspecto ID-1 con esquinas de escáner
El marco SHALL tener relación de aspecto `85.6/54` (≈1.586, tarjeta CR80/ID-1). Cuando `scannerCorners=true`, el marco SHALL mostrar 4 esquinas tipo escáner en los vértices del rectángulo, realizadas con CSS (sin SVG externo). Las esquinas SHALL contrastar con el fondo del video para guiar el posicionamiento del documento.

#### Scenario: Marco tiene aspecto de tarjeta ID-1
- **WHEN** `CameraSnapshotCapture` se monta con `shape='rect'` y `aspectRatio=85.6/54`
- **THEN** el contenedor del marco tiene proporción ≈1.586 (ancho/alto)

#### Scenario: Esquinas de escáner son visibles en el video en vivo
- **WHEN** `scannerCorners=true` y `shape='rect'`
- **THEN** se renderizan 4 esquinas (2 líneas por vértice: horizontal + vertical) superpuestas sobre el video en vivo

#### Scenario: Esquinas no aparecen en modo oval
- **WHEN** `scannerCorners=true` pero `shape='oval'`
- **THEN** no se renderiza ninguna esquina de escáner (prop ignorada silenciosamente)

### Requirement: El tipo EscaneDNI modela frente y dorso por separado
El tipo `EscaneDNI` en `types.ts` SHALL contener `imagen_frente: string | null` e `imagen_dorso: string | null` en lugar del campo único `imagen`. `captura_completada` SHALL ser `true` solo cuando ambos lados fueron capturados y guardados.

#### Scenario: EscaneDNI con ambos lados capturados
- **WHEN** `api.guardarEscaneDNI(frente, dorso)` completa con éxito
- **THEN** retorna `EscaneDNI { captura_completada: true, imagen_frente: string, imagen_dorso: string, fecha_captura: ISO }`

#### Scenario: EscaneDNI nulo antes de cualquier captura
- **WHEN** el alumno no ha completado el escaneo
- **THEN** `enrollment.dni` es `null`

### Requirement: El escaneo de DNI es un dato sensible bajo Ley 25.326
El sistema SHALL tratar las imágenes del DNI (frente y dorso) como dato sensible. En la demo SHALL guardarlas únicamente en memoria de sesión (sin persistencia). El aviso legal en el UI SHALL mencionar: finalidad acotada a verificación de identidad, cifrado AES-256-GCM server-side, eliminación al egreso, holds disciplinarios difieren la eliminación.

#### Scenario: Aviso legal visible antes de iniciar el escaneo
- **WHEN** el alumno ve el estado `inicio` del paso de DNI
- **THEN** se muestra el aviso "Dato sensible (Ley 25.326): cifrado at-rest, finalidad acotada, eliminado al egreso"

#### Scenario: DNI no persiste entre recargas en modo demo
- **WHEN** el alumno recarga la página en modo demo
- **THEN** `enrollment.dni` vuelve a `null` (estado mock efímero en memoria)
