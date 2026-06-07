/**
 * JwtAdapter — adapter del provider JWT propio (C-55, D6 + D7).
 *
 * Flujo:
 *   1. login(creds) → POST /api/v1/auth/login → guarda access_token en sessionStorage.
 *   2. getToken()   → retorna el token si vigente; refresca si expira en < 60s.
 *   3. logout()     → limpia sessionStorage y notifica a los listeners.
 *
 * Storage (D7): access_token en sessionStorage (más seguro que localStorage —
 * se borra al cerrar la pestaña). El refresh_token NO se persiste en el frontend
 * en MVP (sin httpOnly cookie); al reabrir el navegador el usuario hace login de nuevo.
 *
 * Nota MFA (deuda técnica): el token propio no incluye `amr`, por lo que
 * `mfa_satisfecho` es false para todos los roles. El frontend advierte con un
 * warning visible (task 10.3) pero NO bloquea el acceso (MVP).
 */
import type { AuthProvider, AuthStatus } from '../provider';
import type { Principal, Rol } from '../../types';

const STORAGE_KEY = 'jwt_access_token';
const STORAGE_EXPIRES_KEY = 'jwt_access_token_expires_at';
const STORAGE_REFRESH_KEY = 'jwt_refresh_token';

const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api/v1';

/** Roles válidos del modelo MVP. */
const ROLES_VALIDOS: readonly Rol[] = ['estudiante', 'proctor', 'admin_sistema'];

/** Decodifica el payload del JWT SIN verificar la firma (solo para leer claims). */
function _decodePayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const padding = '='.repeat((4 - (parts[1].length % 4)) % 4);
    const json = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/') + padding);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Mapea los claims del JWT propio al Principal de dominio. */
function _principalFromClaims(claims: Record<string, unknown>): Principal | null {
  const realmAccess = claims['realm_access'] as { roles?: string[] } | undefined;
  const realmRoles = realmAccess?.roles ?? [];
  const roles = [...new Set(realmRoles.filter((r): r is Rol => ROLES_VALIDOS.includes(r as Rol)))];

  const idInstitucional =
    (claims['preferred_username'] as string | undefined) ||
    (claims['sub'] as string | undefined) ||
    '';
  if (!idInstitucional) return null;

  return {
    id_institucional: idInstitucional,
    nombre: (claims['name'] as string | undefined) || idInstitucional,
    email: (claims['email'] as string | undefined) || '',
    roles: roles.length > 0 ? roles : ['estudiante'],
    // mfa_satisfecho: el token propio no incluye amr → false (deuda técnica MFA).
    mfa_satisfecho: false,
    jurisdiccion: (claims['jurisdiccion'] as string | undefined) || 'AR',
  };
}

export class JwtAdapter implements AuthProvider {
  private _listeners: Array<(status: AuthStatus) => void> = [];
  private _principal: Principal | null = null;

  async init(): Promise<void> {
    // Intentar recuperar la sesión de sessionStorage al arrancar.
    const token = this._getStoredToken();
    if (token) {
      const claims = _decodePayload(token);
      this._principal = claims ? _principalFromClaims(claims) : null;
      this._notify('authenticated');
    } else {
      this._principal = null;
      this._notify('unauthenticated');
    }
  }

  async login(creds?: { username: string; password: string }): Promise<void> {
    if (!creds) {
      throw new Error('JwtAdapter requiere credenciales (username + password).');
    }
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: creds.username, password: creds.password }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({})) as Record<string, unknown>;
      throw new Error((data['detail'] as string | undefined) || `Error ${res.status}`);
    }

    const data = await res.json() as { access_token: string; refresh_token: string };
    this._storeToken(data.access_token, data.refresh_token);

    const claims = _decodePayload(data.access_token);
    this._principal = claims ? _principalFromClaims(claims) : null;
    this._notify('authenticated');
  }

  async logout(): Promise<void> {
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_EXPIRES_KEY);
    sessionStorage.removeItem(STORAGE_REFRESH_KEY);
    this._principal = null;
    this._notify('unauthenticated');
  }

  getToken(): string | undefined {
    const token = this._getStoredToken();
    if (!token) return undefined;

    // Refrescar automáticamente si el token expira en < 60s.
    const expiresAt = Number(sessionStorage.getItem(STORAGE_EXPIRES_KEY) || '0');
    const ahora = Math.floor(Date.now() / 1000);
    if (expiresAt - ahora < 60) {
      // Lanzar refresh en background (no await para no bloquear el getter).
      void this._refreshToken();
    }

    return token;
  }

  getPrincipal(): Principal | null {
    return this._principal;
  }

  onAuthChange(cb: (status: AuthStatus) => void): () => void {
    this._listeners.push(cb);
    return () => {
      this._listeners = this._listeners.filter((l) => l !== cb);
    };
  }

  // ---------------------------------------------------------------------------
  // Privados
  // ---------------------------------------------------------------------------

  private _getStoredToken(): string | null {
    const token = sessionStorage.getItem(STORAGE_KEY);
    if (!token) return null;

    const expiresAt = Number(sessionStorage.getItem(STORAGE_EXPIRES_KEY) || '0');
    const ahora = Math.floor(Date.now() / 1000);
    if (expiresAt > 0 && ahora >= expiresAt) {
      // Token expirado: limpiar.
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_EXPIRES_KEY);
      return null;
    }
    return token;
  }

  private _storeToken(accessToken: string, refreshToken?: string): void {
    const claims = _decodePayload(accessToken);
    const exp = claims ? (claims['exp'] as number | undefined) : undefined;
    sessionStorage.setItem(STORAGE_KEY, accessToken);
    if (exp) sessionStorage.setItem(STORAGE_EXPIRES_KEY, String(exp));
    if (refreshToken) sessionStorage.setItem(STORAGE_REFRESH_KEY, refreshToken);
  }

  private async _refreshToken(): Promise<void> {
    const refreshJti = sessionStorage.getItem(STORAGE_REFRESH_KEY);
    if (!refreshJti) return;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshJti }),
      });
      if (!res.ok) {
        await this.logout();
        return;
      }
      const data = await res.json() as { access_token: string; refresh_token: string };
      this._storeToken(data.access_token, data.refresh_token);
      const claims = _decodePayload(data.access_token);
      this._principal = claims ? _principalFromClaims(claims) : null;
    } catch {
      // Si falla el refresh: logout silencioso.
      await this.logout();
    }
  }

  private _notify(status: AuthStatus): void {
    this._listeners.forEach((l) => l(status));
  }
}
