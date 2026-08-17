/**
 * Singleton del provider de auth (C-55, D6).
 *
 * Autenticación exclusivamente vía JWT propio: formulario de login →
 * POST /auth/login. Keycloak fue ELIMINADO del dominio (solo debe existir
 * un mecanismo de auth).
 *
 * IMPORTANTE: importar este módulo (no el adapter directo) desde authStore y api.ts.
 */
import { JwtAdapter } from './auth/adapters/jwt';
import type { AuthProvider } from './auth/provider';

export const authProvider: AuthProvider = new JwtAdapter();

/** Único provider soportado — se conserva el tipo por compatibilidad de imports. */
export const AUTH_PROVIDER_TYPE: 'jwt' = 'jwt';
