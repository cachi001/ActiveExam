## ADDED Requirements

### Requirement: CameraSnapshotCapture muestra overlay inmersivo full-screen con marco-guía parametrizable
El sistema SHALL proveer el componente `CameraSnapshotCapture` (`frontend/src/ui/CameraSnapshotCapture.tsx`) que muestre un overlay full-screen (portal a `document.body`, `fixed inset-0`, fondo blanco, `z-[60]`) con la vista en vivo de la cámara frontal del alumno enmarcada según el parámetro `shape`. El componente SHALL aceptar `shape: 'oval' | 'rect'` y un `aspectRatio` opcional. Para `shape='oval'` SHALL aplicar `clipPath: 'ellipse(50% 50% at 50% 50%)'` al contenedor de video con aspecto 3/4. Para `shape='rect'` SHALL mostrar un borde redondeado (`rounded-xl`) con el aspecto indicado por `aspectRatio`. El overlay SHALL incluir un botón "Cancelar" discreto en la esquina superior derecha que llama `onCancel` y detiene el stream.

#### Scenario: Overlay oval para foto de perfil
- **WHEN** el componente se monta con `shape='oval'`
- **THEN** el overlay full-screen aparece con fondo blanco y el video enmarcado en óvalo con clip-path

#### Scenario: Overlay rect para DNI
- **WHEN** el componente se monta con `shape='rect'` y `aspectRatio={1.586}`
- **THEN** el overlay full-screen aparece con fondo blanco y el video enmarcado en rectángulo redondeado con aspecto ~CR80

#### Scenario: Botón cancelar cierra el overlay y libera la cámara
- **WHEN** el usuario hace clic en "Cancelar"
- **THEN** el overlay se desmonta, el stream de cámara se detiene y se llama `onCancel()`

### Requirement: CameraSnapshotCapture solicita acceso a la cámara frontal al montar y muestra error si se deniega
El sistema SHALL llamar a `getUserMedia({ video: { facingMode: 'user' } })` al montar el componente. Si el acceso es concedido SHALL mostrar el video en vivo dentro del marco-guía. Si el acceso es denegado o falla SHALL mostrar un estado de error con mensaje claro y el botón "Cancelar".

#### Scenario: Acceso a cámara concedido — video en vivo visible
- **WHEN** el usuario concede el permiso de cámara
- **THEN** el video en vivo se muestra dentro del marco-guía y el botón "Capturar" está habilitado

#### Scenario: Acceso a cámara denegado — estado de error
- **WHEN** el usuario deniega el permiso de cámara o `getUserMedia` falla
- **THEN** se muestra el estado `'error'` con ícono `videocam_off` y mensaje descriptivo del error

#### Scenario: Stream detenido al desmontar en cualquier estado
- **WHEN** el componente se desmonta (por cancelación o por cualquier causa)
- **THEN** todos los tracks del MediaStream se detienen (`track.stop()`)

### Requirement: CameraSnapshotCapture permite tomar un snapshot y confirmar o repetir
El sistema SHALL mostrar un botón "Capturar" que, al pulsarse, tome un snapshot del frame actual usando `canvas.drawImage(video)` seguido de `canvas.toDataURL('image/jpeg', quality)`. Tras la captura SHALL entrar en estado `'preview'` mostrando la imagen tomada con la forma del marco aplicada como clip visual. En estado `'preview'` SHALL mostrar dos botones: "Usar foto" (llama `onCapture(dataUrl)`) y "Repetir" (vuelve al estado `'capturando'` con el video en vivo). El botón "Capturar" SHALL estar disponible solo en estado `'capturando'`.

#### Scenario: Captura de snapshot — transición a preview
- **WHEN** el usuario hace clic en "Capturar" en estado `'capturando'`
- **THEN** el componente pasa a estado `'preview'` mostrando la imagen tomada

#### Scenario: Preview oval — imagen recortada en círculo
- **WHEN** `shape='oval'` y el componente está en estado `'preview'`
- **THEN** la imagen de preview se muestra con `border-radius: 50%` y `object-fit: cover`

#### Scenario: Confirmar foto — llamada a onCapture con dataURL
- **WHEN** el usuario hace clic en "Usar foto" en estado `'preview'`
- **THEN** se llama `onCapture(dataUrl)` con el dataURL JPEG de la imagen capturada

#### Scenario: Repetir — vuelve al video en vivo
- **WHEN** el usuario hace clic en "Repetir" en estado `'preview'`
- **THEN** el componente vuelve a estado `'capturando'` con el video en vivo activo

### Requirement: CameraSnapshotCapture es genérico y reutilizable por C-38 sin modificación
El componente SHALL ser parametrizable mediante props (`shape`, `aspectRatio`, `instruction`, `contextLabel`, `jpegQuality`, `onCapture`, `onCancel`) de modo que pueda ser reutilizado para la captura de foto de DNI (C-38) pasando `shape='rect'` y el `aspectRatio` correspondiente, sin modificar el componente. El texto de instrucción SHALL ser configurable por la prop `instruction`.

#### Scenario: Texto de instrucción configurable
- **WHEN** el componente recibe `instruction="Posicioná tu cara dentro del óvalo"`
- **THEN** el texto de instrucción visible bajo el marco muestra exactamente ese string

#### Scenario: Calidad JPEG configurable
- **WHEN** el componente recibe `jpegQuality={0.92}`
- **THEN** el dataURL resultante de `canvas.toDataURL('image/jpeg', 0.92)` usa esa calidad
