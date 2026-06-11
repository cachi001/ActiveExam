## ADDED Requirements

### Requirement: PerfilHeaderCard es un componente de presentación pura para el encabezado del perfil
El sistema SHALL proveer un componente `PerfilHeaderCard` en `frontend/src/screens/alumno/components/PerfilHeaderCard.tsx`. El componente SHALL renderizar, dado un `principal: Principal | null`: (1) avatar condicional — si `principal.foto_perfil` existe, una imagen circular (`w-14 h-14 rounded-full object-cover`); si no existe, la inicial del nombre en un círculo de color `secondary-container`; (2) nombre completo y roles del alumno debajo del avatar; (3) un grid de datos personales 2×2 con: legajo (`id_institucional`), email institucional, institución y jurisdicción. El componente es presentación pura: no accede al store ni llama APIs. Recibe `principal` como prop.

#### Scenario: Avatar circular muestra foto de perfil cuando existe
- **WHEN** `principal.foto_perfil` tiene un valor (data URL o URL)
- **THEN** `PerfilHeaderCard` renderiza un `<img>` con `src={principal.foto_perfil}` y clase `rounded-full`

#### Scenario: Avatar inicial cuando no hay foto de perfil
- **WHEN** `principal.foto_perfil` es undefined o null
- **THEN** `PerfilHeaderCard` renderiza un div circular con la primera letra de `principal.nombre`

#### Scenario: Datos personales del alumno visible completos
- **WHEN** `principal` contiene `nombre`, `id_institucional`, `email`, `roles`, `jurisdiccion`
- **THEN** el componente muestra los cuatro campos en el grid: legajo, email, institución (hardcoded 'UTN Regional Mendoza'), jurisdicción

#### Scenario: Datos personales con principal null no rompe el componente
- **WHEN** `principal` es null
- **THEN** `PerfilHeaderCard` renderiza valores fallback (`'—'`) sin error
