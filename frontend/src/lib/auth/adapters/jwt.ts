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
import { ROLES_VALIDOS } from '../../constants/roles';
import type { Principal, Rol } from '../../types';

const STORAGE_KEY = 'jwt_access_token';
const STORAGE_EXPIRES_KEY = 'jwt_access_token_expires_at';
const STORAGE_REFRESH_KEY = 'jwt_refresh_token';

const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api/v1';

// Roles válidos: se leen de la fuente única (`lib/constants/roles`), que espeja el
// enum `Rol` del backend. NO redeclarar la lista acá.
//
// Tenía su propia copia con solo 3 roles. Como abajo el fallback convierte una
// lista vacía en `['estudiante']`, cualquier rol fuera de esa copia — docente,
// revisor, auditor, coordinador — se filtraba y la persona entraba al sistema
// COMO ESTUDIANTE, en silencio: sin error, sin aviso, con el panel de alumno. Un
// revisor legítimo perdía sus permisos por una lista desactualizada.

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
  // Un rol que el token trae pero el front no reconoce es un BUG de sincronización
  // con el backend, no un usuario sin permisos: avisar fuerte en dev en vez de
  // degradarlo a estudiante sin que nadie se entere.
  if (import.meta.env.DEV && realmRoles.length > 0 && roles.length === 0) {
    console.error(
      `[auth] El token trae roles que el frontend no conoce: ${realmRoles.join(', ')}. ` +
        `Agregalos a lib/constants/roles.ts y a lib/types.ts §Rol (deben espejar el enum Rol del backend).`,
    );
  }

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
  // Single-flight: todas las llamadas concurrentes que disparan un refresh
  // (múltiples requests en paralelo pegando 401 a la vez) esperan la MISMA
  // promesa en vez de una por-caller. Sin esto, la primera gana el refresh
  // token rotado; las demás llegan con el refresh_token ya usado, el backend
  // las rechaza con 401, y cada una dispara su propio logout() — pisando la
  // sesión válida que la ganadora acababa de guardar un instante antes.
  private _refreshInFlight: Promise<void> | null = null;

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
      const detail = data['detail'] as string | undefined;
      if (detail) throw new Error(detail);
      if (res.status === 401 || res.status === 403) throw new Error('Correo o contraseña incorrectos.');
      throw new Error('No pudimos conectar con el servidor. Intentá de nuevo más tarde.');
    }

    const data = await res.json() as { access_token: string; refresh_token: string };
    this._storeToken(data.access_token, data.refresh_token);

    const claims = _decodePayload(data.access_token);
    this._principal = claims ? _principalFromClaims(claims) : null;
    this._notify('authenticated');
  }

  /**
   * Adopta una sesión emitida fuera del formulario de login (C-75 §7.1): el
   * launch LTI valida al alumno en el backend y redirige al frontend con el
   * access/refresh token ya emitidos. La landing `/lti-login` los pasa acá para
   * persistirlos con el MISMO mecanismo que un login normal (mismas claves de
   * sessionStorage, mismo decode de exp/principal). Falla cerrado: si el token
   * no decodifica, no autentica.
   */
  seedSession(accessToken: string, refreshToken?: string): void {
    this._storeToken(accessToken, refreshToken);
    const claims = _decodePayload(accessToken);
    this._principal = claims ? _principalFromClaims(claims) : null;
    if (this._principal) {
      this._notify('authenticated');
    } else {
      // Token ilegible: no dejamos storage a medias con un principal nulo.
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_EXPIRES_KEY);
      sessionStorage.removeItem(STORAGE_REFRESH_KEY);
      this._notify('unauthenticated');
    }
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

  /**
   * Refresh awaitable (usado por realFetch ante un 401). El access token vive sólo
   * 15 min; en flujos largos (captura biométrica) expira. `getToken()` no podía
   * recuperar porque `_getStoredToken()` borra el token expirado y devolvía undefined
   * ANTES de poder refrescar. Acá refrescamos con el refresh_token (que NO se borra)
   * y devolvemos el token fresco para reintentar el request.
   */
  async refresh(): Promise<string | undefined> {
    await this._refreshToken();
    return sessionStorage.getItem(STORAGE_KEY) ?? undefined;
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
    // Ya hay un refresh en curso: esperar ESE resultado en vez de disparar
    // otro POST /auth/refresh con el mismo refresh_token (que el backend
    // rechazaría por rotación de un solo uso).
    if (this._refreshInFlight) {
      await this._refreshInFlight;
      return;
    }
    this._refreshInFlight = this._doRefresh().finally(() => {
      this._refreshInFlight = null;
    });
    await this._refreshInFlight;
  }

  private async _doRefresh(): Promise<void> {
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
