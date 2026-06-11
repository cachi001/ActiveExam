## MODIFIED Requirements

### Requirement: La pantalla de perfil muestra los datos personales del alumno
El sistema SHALL proveer la pantalla `/alumno/perfil` que muestre el nombre completo, legajo, email institucional y la institución (`UTN Regional Mendoza`) del alumno autenticado. Estos datos SHALL ser presentados mediante el componente `PerfilHeaderCard` (`frontend/src/screens/alumno/components/PerfilHeaderCard.tsx`), que también incluye el avatar condicional del alumno (foto circular si `foto_perfil` existe, inicial si no) y la jurisdicción. `StudentProfile.tsx` pasa `principal` como prop a `PerfilHeaderCard`.

#### Scenario: Datos personales visibles en el perfil vía PerfilHeaderCard
- **WHEN** el alumno navega a `/alumno/perfil` y el estado es `paso === 'perfil'`
- **THEN** se renderiza `PerfilHeaderCard` con nombre completo, legajo (`id_institucional`), email (`@frm.utn.edu.ar`), institución y jurisdicción del `principal`

#### Scenario: Email del perfil es de UTN FRM
- **WHEN** el alumno autenticado es el principal de demo para rol `estudiante`
- **THEN** el email mostrado en `PerfilHeaderCard` termina en `@frm.utn.edu.ar`

### Requirement: El perfil incluye secciones de requisitos de enrollment como tarjetas uniformes
El sistema SHALL mostrar las secciones de enrollment del perfil usando el componente `RequisitoCard`. Cada requisito (consentimiento informado, referencia biométrica, verificación documental DNI) SHALL ser una `RequisitoCard` con su badge de estado correspondiente. El layout SHALL ser minimalista: tarjetas con el mismo ancho y espaciado, badges consistentes (dots), botones de tamaño adecuado (`size='sm'` para acciones secundarias). El alumno SHALL poder entender de un vistazo qué requisitos están completados y cuáles faltan.

#### Scenario: Sección de consentimiento muestra estado pendiente por defecto
- **WHEN** el alumno accede al perfil y `enrollment.consentimiento` es null
- **THEN** la `RequisitoCard` de "Consentimiento informado" muestra badge `tone='warning'` y label 'Pendiente'
- **THEN** dentro del card hay un botón "Leer y consentir" que navega al paso `consentimiento`

#### Scenario: Sección de consentimiento muestra acuse cuando completado
- **WHEN** `enrollment.consentimiento` existe
- **THEN** la `RequisitoCard` de "Consentimiento informado" muestra badge `tone='success'` y label 'Completado'
- **THEN** dentro del card se muestran: versión del consentimiento, fecha del acuse y hash en formato mono truncado

#### Scenario: Sección de biometría solo visible cuando no es vía alternativa
- **WHEN** `!viaAlternativa` y `paso === 'perfil'`
- **THEN** la `RequisitoCard` de "Referencia biométrica" es visible con badge reflejando el estado de vigencia

#### Scenario: Sección DNI muestra estado correcto según flag y captura
- **WHEN** `ENABLE_DNI_SCAN=true` y `!dniOk`
- **THEN** la `RequisitoCard` de "Verificación documental" muestra badge `tone='neutral'` y label 'Pendiente', con CTA "Escanear DNI (opcional)"

#### Scenario: Banners contextuales del estado del perfil encapsulados en PerfilBannerEstado
- **WHEN** `perfilCompleto=true` y `!biometriaCaducada` y `!biometriaRenovacionRequerida`
- **THEN** `PerfilBannerEstado` muestra el banner verde con "Perfil completo — podés rendir tus exámenes"

#### Scenario: Perfil completo habilita el gate puedeRendir
- **WHEN** `enrollment.perfil_completo === true`
- **THEN** `api.puedeRendir()` retorna `{ puede: true }` (comportamiento sin cambio)

#### Scenario: Perfil incompleto mantiene el gate bloqueado
- **WHEN** al menos un requisito crítico (consentimiento o biometría sin vía alternativa) está pendiente
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: string }` (comportamiento sin cambio)
