/**
 * Singleton del provider de auth activo (C-55, D6).
 *
 * Lee VITE_AUTH_PROVIDER del entorno y exporta el adapter correcto.
 * Default: 'jwt' (MVP self-hosted).
 *
 * | VITE_AUTH_PROVIDER | Adapter        | Comportamiento                          |
 * |--------------------|----------------|-----------------------------------------|
 * | 'jwt' (default)    | JwtAdapter     | Formulario login → POST /auth/login     |
 * | 'keycloak'         | KeycloakAdapter| Redirect OIDC PKCE (C-06 conservado)   |
 *
 * IMPORTANTE: importar este módulo (no adapters individuales) desde authStore y api.ts.
 */
import { JwtAdapter } from './auth/adapters/jwt';
import { KeycloakAdapter } from './auth/adapters/keycloak';
import type { AuthProvider } from './auth/provider';

const VITE_AUTH_PROVIDER = (import.meta.env.VITE_AUTH_PROVIDER as string | undefined) || 'jwt';

function _createProvider(): AuthProvider {
  if (VITE_AUTH_PROVIDER === 'keycloak') {
    return new KeycloakAdapter();
  }
  // Default: jwt
  return new JwtAdapter();
}

export const authProvider: AuthProvider = _createProvider();

/** Expone el tipo del provider activo para que los componentes puedan ramificar. */
export const AUTH_PROVIDER_TYPE: 'jwt' | 'keycloak' =
  VITE_AUTH_PROVIDER === 'keycloak' ? 'keycloak' : 'jwt';
