# auth-provider-abstraction Specification

## Purpose
TBD - created by archiving change c-55-auth-provider-jwt-propio. Update Purpose after archive.
## Requirements
### Requirement: Interfaz AuthProvider con tres adapters seleccionables por env
El frontend SHALL definir la interfaz `AuthProvider` en `lib/auth/provider.ts` con los métodos `init(): Promise<void>`, `login(creds?): Promise<void>`, `logout(): Promise<void>`, `getToken(): string | undefined`, `getPrincipal(): Principal | null`, `onAuthChange(cb): () => void` (retorna función de unsubscribe). Tres adapters SHALL implementar esta interfaz: `JwtAdapter` (`VITE_AUTH_PROVIDER=jwt`), `KeycloakAdapter` (`keycloak`), `DemoAdapter` (`demo`). El singleton del provider activo SHALL resolverse en `lib/authProvider.ts` según `VITE_AUTH_PROVIDER`.

#### Scenario: Selección de adapter jwt por env
- **WHEN** la app arranca con `VITE_AUTH_PROVIDER=jwt`
- **THEN** el provider activo es `JwtAdapter` y el formulario de login se renderiza en lugar del redirect a Keycloak

#### Scenario: Selección de adapter keycloak por env
- **WHEN** la app arranca con `VITE_AUTH_PROVIDER=keycloak`
- **THEN** el provider activo es `KeycloakAdapter` y el flujo PKCE de Keycloak funciona exactamente como antes de este change

#### Scenario: Selección de adapter demo por env
- **WHEN** la app arranca con `VITE_AUTH_PROVIDER=demo`
- **THEN** el provider activo es `DemoAdapter` y el selector de roles demo funciona sin red ni backend

#### Scenario: Variable ausente default a jwt
- **WHEN** `VITE_AUTH_PROVIDER` no está definida
- **THEN** el provider activo es `JwtAdapter` (default del MVP self-hosted)

### Requirement: JwtAdapter — formulario login con POST /api/v1/auth/login
`JwtAdapter.login()` SHALL mostrar (o delegar al componente de login) un formulario con campos `email`/`username` y `password`. Al submit SHALL llamar `POST /api/v1/auth/login` con las credenciales. Si la respuesta es 200, SHALL guardar el `access_token` en `sessionStorage` bajo la clave `jwt_access_token` y el `expires_in` para saber cuándo refrescar. Si la respuesta es 401 SHALL propagar un error con mensaje visible al usuario. `getToken()` SHALL devolver el token desde `sessionStorage` si no ha expirado, llamar a `POST /api/v1/auth/refresh` si está por expirar (< 60 s restantes), y `undefined` si no hay sesión.

#### Scenario: Login exitoso guarda token en sessionStorage
- **WHEN** el usuario completa el formulario con credenciales válidas y hace submit
- **THEN** el `access_token` se guarda en `sessionStorage['jwt_access_token']` y `authStore` se actualiza a `status: 'authenticated'`

#### Scenario: Login fallido muestra error al usuario
- **WHEN** el usuario envía credenciales incorrectas
- **THEN** el formulario muestra un mensaje de error claro (sin detalle sobre si el usuario existe)

#### Scenario: Token próximo a expirar dispara refresh automático
- **WHEN** `getToken()` es llamado y el token en sessionStorage expira en menos de 60 s
- **THEN** se llama automáticamente `POST /api/v1/auth/refresh` y se retorna el nuevo access token

#### Scenario: Sin sesión activa getToken retorna undefined
- **WHEN** no hay token en sessionStorage o el token expiró y no hay refresh token disponible
- **THEN** `getToken()` retorna `undefined` y el próximo request autenticado falla con 401 en el backend

### Requirement: KeycloakAdapter — envuelve flujo existente sin regresión
`KeycloakAdapter` SHALL envolver toda la lógica actual de `lib/auth/keycloak.ts` (init, login PKCE, logout, getToken, principalFromToken) detrás de la interfaz `AuthProvider`. `lib/auth/keycloak.ts` NO SHALL ser modificado en su lógica — solo se le agrega el wrapper. Con `VITE_AUTH_PROVIDER=keycloak`, la app SHALL comportarse exactamente igual que antes de este change.

#### Scenario: Flujo PKCE Keycloak intacto con adapter
- **WHEN** la app usa `KeycloakAdapter` (VITE_AUTH_PROVIDER=keycloak)
- **THEN** el flujo OIDC PKCE S256 con responseMode=query funciona igual que en C-06, sin regresiones

#### Scenario: getToken() del adapter Keycloak retorna token de keycloak.token
- **WHEN** hay sesión Keycloak activa
- **THEN** `KeycloakAdapter.getToken()` retorna `keycloak.token` (comportamiento C-06 conservado)

### Requirement: authStore desacoplado de Keycloak — consume AuthProvider activo
`authStore` (Zustand) SHALL depender de la interfaz `AuthProvider` en lugar de importar `keycloak.ts` directamente. Los métodos `login()`, `logout()`, `hydrateFromKeycloak()` (renombrado a `hydrateFromProvider()`) SHALL delegar al provider activo. `getToken()` en `api.ts` SHALL importar del provider activo, no de `keycloak.ts` directamente. Los componentes que usan `useAuth` SHALL funcionar sin cambio (la interfaz del store no cambia).

#### Scenario: authStore hidratado desde provider jwt al init
- **WHEN** la app arranca con VITE_AUTH_PROVIDER=jwt y hay un token válido en sessionStorage
- **THEN** authStore queda en status='authenticated' con el principal correcto sin login extra

#### Scenario: logout limpia sessionStorage en adapter jwt
- **WHEN** el usuario hace logout con el adapter jwt activo
- **THEN** `sessionStorage['jwt_access_token']` se borra y authStore queda en status='unauthenticated'

### Requirement: Pantalla de login con formulario para adapter jwt
El frontend SHALL renderizar una pantalla `LoginScreen` (o componente equivalente) con formulario usuario/contraseña cuando el provider activo es `JwtAdapter` y el usuario no está autenticado. La pantalla SHALL mostrar el logo/nombre institucional, campos `email o nombre de usuario` y `contraseña`, botón de submit con estado de loading, y mensajes de error inline. La pantalla NO SHALL redirigir a Keycloak cuando el adapter es `jwt`.

#### Scenario: Pantalla de login se muestra al no autenticado con adapter jwt
- **WHEN** la app carga sin sesión y VITE_AUTH_PROVIDER=jwt
- **THEN** se muestra la pantalla de login con formulario (no redirect a Keycloak)

#### Scenario: Pantalla de login muestra loading durante submit
- **WHEN** el usuario hace submit del formulario
- **THEN** el botón muestra estado de carga y los campos quedan deshabilitados hasta la respuesta

