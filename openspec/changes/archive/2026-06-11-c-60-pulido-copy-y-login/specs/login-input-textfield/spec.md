## ADDED Requirements

### Requirement: Componente TextField reusable
El sistema SHALL proveer un componente `TextField` exportado desde `frontend/src/ui/TextField.tsx` y re-exportado en el barrel `frontend/src/ui/components.tsx`. El componente SHALL aceptar las props `label`, `name`, `type` (`text` | `email` | `password` | `search`, default `text`), `value`, `onChange`, y opcionalmente `placeholder`, `icon` (Material Symbol name), `error`, `hint`, `disabled`, `required`, `autoComplete`, `className`. SHALL implementar `forwardRef` al `<input>` subyacente.

#### Scenario: Render básico con label e input
- **WHEN** se renderiza `<TextField label="Usuario" name="user" value="" onChange={fn} />`
- **THEN** aparece un label con el texto "Usuario" encima del input, y el input está visible y accesible

#### Scenario: Ícono izquierdo dentro del input
- **WHEN** se renderiza `TextField` con `icon="person"`
- **THEN** el ícono Material Symbol `person` es visible dentro del área del input, alineado a la izquierda, y el texto de entrada no se superpone con él

#### Scenario: Toggle ver/ocultar contraseña con `type="password"`
- **WHEN** se renderiza `TextField` con `type="password"`
- **THEN** el input oculta los caracteres por defecto y aparece un botón con ícono `visibility` a la derecha; al hacer click en ese botón el input cambia a `type="text"` y el ícono cambia a `visibility_off`

#### Scenario: No se muestra toggle en type distinto de password
- **WHEN** se renderiza `TextField` con `type="text"`
- **THEN** no aparece ningún botón de toggle de visibilidad a la derecha

#### Scenario: Mensaje de error
- **WHEN** se renderiza `TextField` con `error="Campo requerido"`
- **THEN** el texto "Campo requerido" es visible en color de error debajo del input, y el borde del input tiene color de error

#### Scenario: Estado disabled
- **WHEN** se renderiza `TextField` con `disabled={true}`
- **THEN** el input no acepta focus ni input del usuario, y su opacidad es reducida

### Requirement: Estilo del TextField — fondo blanco, espacioso, ring primario
El componente TextField SHALL renderizar el input con fondo blanco (`bg-white`), borde sutil de 1px con color `outline-variant`, bordes redondeados `rounded-xl`, padding cómodo (`px-4 py-3`), sombra muy sutil (`shadow-xs`), y al recibir foco SHALL mostrar un ring de 4px con el color primario al 15% de opacidad y el borde en color primario. En hover SHALL mostrar el borde con color `outline`. SHALL usar exclusivamente los tokens de color de ActiveExam (primary violeta, surface, on-surface-variant, outline) sin introducir paletas externas.

#### Scenario: Foco activa ring primario
- **WHEN** el input recibe foco
- **THEN** aparece un ring visual de 4px con el color primary al 15% de opacidad, y el borde cambia al color primary

#### Scenario: Sin fondo gris
- **WHEN** se renderiza el input en estado normal
- **THEN** el fondo del input es blanco, no gris ni `surface-container-low`

### Requirement: TextField adoptable por c-61 sin modificaciones
El componente TextField SHALL estar completamente definido (props, comportamiento, estilos) de modo que el change c-61 (registro de nuevo usuario) pueda importarlo y usarlo sin necesitar cambiar su implementación. La API SHALL ser estable en el momento del merge de c-60.

#### Scenario: Import desde barrel
- **WHEN** un componente importa `import { TextField } from '../ui/components'`
- **THEN** el import resuelve correctamente sin errores de TypeScript
