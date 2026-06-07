## MODIFIED Requirements

### Requirement: Las secciones de contenido real son placeholders en C-21
El sistema SHALL usar los endpoints reales de enrollment para persistir la foto de perfil y el embedding de referencia. El componente `StudentProfile.tsx` SHALL llamar a `api.guardarFotoPerfil(dataUrl)` y `api.guardarReferenciaBiometrica({ imagen: null, embedding })`, que a su vez invocan los endpoints `POST /api/v1/enrollment/foto-perfil` y `POST /api/v1/enrollment/embedding-referencia` respectivamente. Tras completar cada fase, el componente SHALL recibir un ID de referencia opaco del backend y persistirlo en el store (no el embedding crudo). El comportamiento demo (in-memory) queda eliminado para estas dos operaciones.

#### Scenario: Foto de perfil persistida en backend al completar la fase foto_perfil
- **WHEN** el alumno captura la foto de perfil en la fase `foto_perfil` del flujo de enrollment
- **THEN** `api.guardarFotoPerfil(dataUrl)` hace `POST /api/v1/enrollment/foto-perfil` con la imagen
- **THEN** el backend responde `{ foto_referencia_id: "<uuid>" }` con HTTP 201
- **THEN** el store persiste el `foto_referencia_id` (no el dataUrl completo)
- **THEN** la fase avanza al siguiente paso del enrollment

#### Scenario: Embedding de referencia persistido en backend al completar la fase biometria
- **WHEN** el alumno completa la captura biométrica en la fase `biometria` del flujo de enrollment
- **THEN** `api.guardarReferenciaBiometrica({ imagen: null, embedding })` hace `POST /api/v1/enrollment/embedding-referencia` con el array de 128 floats
- **THEN** el backend responde `{ referencia_id: "<uuid>" }` con HTTP 201
- **THEN** el store persiste el `referencia_id` y elimina cualquier embedding crudo previo de localStorage (`activeexam_bio_ref`)
- **THEN** la fase de enrollment marca `biometria` como completada

#### Scenario: Error del backend en guardar foto muestra mensaje al alumno y no avanza la fase
- **WHEN** `POST /api/v1/enrollment/foto-perfil` devuelve HTTP 5xx o fallo de red
- **THEN** la fase `foto_perfil` no avanza
- **THEN** se muestra un mensaje de error al alumno con opción de reintentar
- **THEN** el store no persiste ningún ID de referencia inválido

#### Scenario: Error del backend en guardar embedding muestra mensaje al alumno y no avanza la fase
- **WHEN** `POST /api/v1/enrollment/embedding-referencia` devuelve HTTP 4xx o 5xx
- **THEN** la fase `biometria` no avanza
- **THEN** se muestra un mensaje de error al alumno con opción de reintentar
- **THEN** el store no persiste ningún `referencia_id` inválido
