/**
 * Interfaz AuthProvider — puerto de autenticación (C-55, D6).
 *
 * Tres adapters implementan esta interfaz:
 *   - JwtAdapter    (VITE_AUTH_PROVIDER=jwt)      → formulario + POST /auth/login
 *   - KeycloakAdapter (VITE_AUTH_PROVIDER=keycloak) → flujo OIDC PKCE existente
 *   - DemoAdapter   (VITE_AUTH_PROVIDER=demo)     → selector de roles sin red
 *
 * El singleton del provider activo se resuelve en lib/authProvider.ts.
 * authStore y api.ts dependen de esta interfaz, no de Keycloak directamente.
 */
import type { Principal } from '../types';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface AuthProvider {
  /**
   * Inicializa el provider (check-sso silencioso, recuperar token de storage, etc.).
   * Debe resolverse antes de renderizar la app.
   */
  init(): Promise<void>;

  /**
   * Inicia sesión. Para JwtAdapter: requiere credenciales. Para Keycloak: redirige.
   * Para Demo: sin red.
   */
  login(creds?: { username: string; password: string }): Promise<void>;

  /** Cierra sesión y limpia el estado. */
  logout(): Promise<void>;

  /**
   * Retorna el access token vigente, o undefined si no hay sesión.
   * JwtAdapter: refresca automáticamente si el token expira en < 60s.
   */
  getToken(): string | undefined;

  /**
   * Refresca el access token usando el refresh_token, si el adapter lo soporta.
   * Devuelve el nuevo token vigente, o undefined si no se pudo refrescar.
   * Opcional: sólo JwtAdapter lo implementa (Keycloak refresca solo; Demo no aplica).
   * Lo usa `realFetch` para auto-curarse ante un 401 por token expirado.
   */
  refresh?(): Promise<string | undefined>;

  /** Retorna el principal autenticado, o null si no hay sesión. */
  getPrincipal(): Principal | null;

  /**
   * Registra un callback para cambios de estado de auth.
   * Retorna una función de unsubscribe.
   */
  onAuthChange(cb: (status: AuthStatus) => void): () => void;
}
