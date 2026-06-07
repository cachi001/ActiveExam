/**
 * KeycloakAdapter — wrapper del flujo OIDC PKCE existente (C-55, D6).
 *
 * Envuelve toda la lógica de lib/auth/keycloak.ts sin modificar su lógica interna.
 * Con VITE_AUTH_PROVIDER=keycloak, la app se comporta exactamente igual que antes
 * de este change (retrocompatibilidad garantizada).
 *
 * keycloak.ts NO SE MODIFICA — solo se le agrega este wrapper.
 */
import type { AuthProvider, AuthStatus } from '../provider';
import type { Principal } from '../../types';
import {
  keycloak,
  initKeycloak,
  principalFromToken,
  login as kcLogin,
  logout as kcLogout,
  getToken as kcGetToken,
} from '../keycloak';

export class KeycloakAdapter implements AuthProvider {
  private _listeners: Array<(status: AuthStatus) => void> = [];

  async init(): Promise<void> {
    // Registrar los callbacks de Keycloak antes de inicializar.
    keycloak.onAuthSuccess = () => this._notify('authenticated');
    keycloak.onAuthRefreshSuccess = () => this._notify('authenticated');
    keycloak.onAuthLogout = () => this._notify('unauthenticated');
    keycloak.onTokenExpired = () => {
      void keycloak.updateToken(30).then(() => this._notify('authenticated'));
    };

    try {
      await initKeycloak();
      this._notify(keycloak.authenticated ? 'authenticated' : 'unauthenticated');
    } catch {
      this._notify('unauthenticated');
    }
  }

  async login(_creds?: { username: string; password: string }): Promise<void> {
    // Keycloak no usa credenciales directas — redirige al IdP.
    kcLogin();
  }

  async logout(): Promise<void> {
    kcLogout();
  }

  getToken(): string | undefined {
    return kcGetToken();
  }

  getPrincipal(): Principal | null {
    return principalFromToken();
  }

  onAuthChange(cb: (status: AuthStatus) => void): () => void {
    this._listeners.push(cb);
    return () => {
      this._listeners = this._listeners.filter((l) => l !== cb);
    };
  }

  private _notify(status: AuthStatus): void {
    this._listeners.forEach((l) => l(status));
  }
}
