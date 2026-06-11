# realtime-handshake-auth Specification

## Purpose
TBD - created by archiving change c-06-auth-rbac-keycloak. Update Purpose after archive.
## Requirements
### Requirement: Handshake WS/SSE validado con JWT y revalidación periódica
El handshake de los canales de tiempo real (WebSocket del estudiante, SSE del panel) SHALL validar el JWT al conectar y SHALL **revalidarlo periódicamente** durante la vida de la conexión, cortando el canal si el token expira o se revoca (`03` §Suposición).

#### Scenario: Handshake sin token rechazado
- **WHEN** se intenta abrir una conexión WS/SSE sin un JWT válido en el handshake
- **THEN** el handshake es rechazado y no se establece el canal

#### Scenario: Conexión cortada al dejar de ser válido el token
- **WHEN** una conexión WS/SSE activa supera el período de revalidación y su token está expirado o revocado
- **THEN** la revalidación periódica falla y el canal se corta

### Requirement: Rate limiting y rutas públicas mínimas
El sistema SHALL aplicar rate limiting en Keycloak (login) y Nginx (API) contra fuerza bruta, y SHALL exponer una superficie pública mínima — login institucional y estáticos del frontend — exigiendo JWT en todo el resto de la API y los canales (`08` §Seguridad, `03` §Rutas públicas).

#### Scenario: Rate limiting activo sobre login y API
- **WHEN** se exceden los umbrales de solicitudes de login o de API
- **THEN** Keycloak y Nginx aplican rate limiting, mitigando la fuerza bruta

#### Scenario: Solo rutas públicas mínimas sin JWT
- **WHEN** se accede a un endpoint de la API o a un canal que no es login ni estático del frontend
- **THEN** se exige un JWT válido; `POST /api/v1/auth/refresh` opera con token (no es estrictamente pública)

