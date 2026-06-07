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
 * | 'demo'             | DemoAdapter    | Selector de roles sin red (Vercel demo) |
 *
 * IMPORTANTE: importar este módulo (no adapters individuales) desde authStore y api.ts.
 */
import { JwtAdapter } from './auth/adapters/jwt';
import { KeycloakAdapter } from './auth/adapters/keycloak';
import { DemoAdapter } from './auth/adapters/demo';
import type { AuthProvider } from './auth/provider';

const VITE_AUTH_PROVIDER = (import.meta.env.VITE_AUTH_PROVIDER as string | undefined) || 'jwt';

// VITE_DEMO_MODE=1 es el flag histórico para el modo demo (retrocompatibilidad).
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === '1';

function _createProvider(): AuthProvider {
  if (DEMO_MODE || VITE_AUTH_PROVIDER === 'demo') {
    return new DemoAdapter();
  }
  if (VITE_AUTH_PROVIDER === 'keycloak') {
    return new KeycloakAdapter();
  }
  // Default: jwt
  return new JwtAdapter();
}

export const authProvider: AuthProvider = _createProvider();

/** Expone el tipo del provider activo para que los componentes puedan ramificar. */
export const AUTH_PROVIDER_TYPE: 'jwt' | 'keycloak' | 'demo' =
  DEMO_MODE || VITE_AUTH_PROVIDER === 'demo'
    ? 'demo'
    : VITE_AUTH_PROVIDER === 'keycloak'
      ? 'keycloak'
      : 'jwt';
