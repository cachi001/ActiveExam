/**
 * authStore — Estado de autenticación (Zustand), desacoplado del provider concreto (C-55).
 *
 * Delega al provider activo (JwtAdapter) vía la interfaz AuthProvider — los
 * componentes que usan useAuth no dependen del adapter concreto.
 */
import { create } from 'zustand';
import type { Principal, Rol } from './types';
import type { AuthProvider, AuthStatus } from './auth/provider';
import { API_BASE, resetEnrollmentCache } from './api';
import { useApp } from './store';

export type { AuthStatus };

/**
 * Trae nombre/apellido del usuario logueado desde GET /auth/me y los devuelve
 * para que el caller los fusione en el principal del store. El JWT propio
 * (C-55, own_issuer.py) NO incluye el claim `name`, así que sin esta llamada
 * el frontend cae al fallback `username` y la UI muestra "Hola, 123".
 *
 * Fire-and-forget seguro: cualquier error (sin red, 401, etc.) se silencia y
 * el principal queda como vino del token.
 */
async function fetchMyName(
  provider: AuthProvider,
): Promise<{
  nombre?: string;
  apellido?: string;
  creado_en?: string;
  ultimo_acceso_en?: string;
  debe_cambiar_password?: boolean;
  auth_provider?: string;
} | null> {
  const token = provider.getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      nombre?: string | null;
      apellido?: string | null;
      creado_en?: string | null;
      ultimo_acceso_en?: string | null;
      debe_cambiar_password?: boolean | null;
      auth_provider?: string | null;
    };
    return {
      nombre: data.nombre ?? undefined,
      apellido: data.apellido ?? undefined,
      creado_en: data.creado_en ?? undefined,
      ultimo_acceso_en: data.ultimo_acceso_en ?? undefined,
      debe_cambiar_password: data.debe_cambiar_password ?? undefined,
      auth_provider: data.auth_provider ?? undefined,
    };
  } catch {
    return null;
  }
}

interface AuthState {
  status: AuthStatus;
  principal: Principal | null;
  token: string | null;

  /** Hidrata el store desde el provider activo. */
  hydrateFromProvider: (provider: AuthProvider) => void;

  /** Inicia sesión con credenciales. */
  login: (creds?: { username: string; password: string }) => Promise<void>;

  /**
   * Adopta una sesión emitida por el backend vía tokens (landing LTI, C-75 §7.1).
   * Persiste los tokens en el provider e hidrata el store. Devuelve true si quedó
   * autenticado. Falla cerrado: si el provider no soporta seedSession o el token
   * no decodifica, no autentica.
   */
  loginWithTokens: (accessToken: string, refreshToken?: string) => boolean;

  /** Cierra sesión en el provider activo. */
  logout: () => void;

  /** True si el principal tiene AL MENOS uno de los roles dados. */
  hasRole: (roles: Rol[]) => boolean;

  /** Actualiza la foto de perfil del principal (fuente única — C-73). Sin efecto si no hay principal. */
  setFotoPerfil: (dataUrl: string) => void;

  /** Marca que el usuario ya definió su contraseña (limpia el gate de clave temporal). */
  markPasswordChanged: () => void;
}

// Guardamos referencia al provider activo para que login/logout puedan delegar.
// Se setea en hydrateFromProvider().
let _activeProvider: AuthProvider | null = null;

export const useAuth = create<AuthState>((set, get) => ({
  status: 'loading',
  principal: null,
  token: null,

  hydrateFromProvider: (provider: AuthProvider) => {
    _activeProvider = provider;
    const principal = provider.getPrincipal();
    const token = provider.getToken() ?? null;
    if (principal) {
      set({ status: 'authenticated', principal, token });
      // El JWT propio no incluye `name` → el principal recién hidratado tiene
      // `nombre = username` como fallback. Enriquecemos en background
      // con GET /auth/me para mostrar "Hola, Nombre Apellido" en lugar del
      // legajo. Si la llamada falla, el principal queda como estaba.
      void fetchMyName(provider).then((extra) => {
        if (!extra) return;
        const current = get().principal;
        if (!current) return;
        // Siempre fusionamos fechas. El nombre solo se actualiza si el principal
        // todavía tiene el fallback (username): si el provider ya entregó
        // un nombre humano, lo respetamos.
        const nombreActualizado =
          extra.nombre && current.nombre === current.username
            ? extra.nombre
            : current.nombre;
        set({
          principal: {
            ...current,
            nombre: nombreActualizado,
            apellido: extra.apellido ?? current.apellido,
            creado_en: extra.creado_en ?? current.creado_en,
            ultimo_acceso_en: extra.ultimo_acceso_en ?? current.ultimo_acceso_en,
            debe_cambiar_password: extra.debe_cambiar_password ?? current.debe_cambiar_password,
            auth_provider: extra.auth_provider ?? current.auth_provider,
          },
        });
      });
    } else {
      set({ status: 'unauthenticated', principal: null, token: null });
    }
  },

  login: async (creds?: { username: string; password: string }) => {
    if (!_activeProvider) return;
    await _activeProvider.login(creds);
    // Invalidar el enrollment cacheado del usuario anterior ANTES de hidratar el nuevo
    // principal: sin esto, un usuario nuevo hereda el `perfil_completo`/acuses del
    // usuario previo (cache en api.ts + store) y ve "disponible" hasta que el servidor
    // lo corrige (flash de estado stale).
    resetEnrollmentCache();
    useApp.getState().clearEnrollment();
    // Actualizar el store tras login exitoso.
    get().hydrateFromProvider(_activeProvider);
  },

  loginWithTokens: (accessToken: string, refreshToken?: string) => {
    if (!_activeProvider || typeof _activeProvider.seedSession !== 'function') {
      return false;
    }
    // Mismo saneamiento que login(): que el alumno LTI no herede el enrollment
    // cacheado de una sesión previa en la misma pestaña.
    resetEnrollmentCache();
    useApp.getState().clearEnrollment();
    _activeProvider.seedSession(accessToken, refreshToken);
    get().hydrateFromProvider(_activeProvider);
    return get().status === 'authenticated';
  },

  logout: () => {
    // Limpiar el enrollment cacheado al cerrar sesión (mismo motivo que en login):
    // que el próximo usuario no arranque con el perfil del anterior.
    resetEnrollmentCache();
    useApp.getState().clearEnrollment();
    if (!_activeProvider) {
      set({ status: 'unauthenticated', principal: null, token: null });
      return;
    }
    void _activeProvider.logout().then(() => {
      set({ status: 'unauthenticated', principal: null, token: null });
    });
  },

  hasRole: (roles) => {
    const p = get().principal;
    return !!p && roles.some((r) => p.roles.includes(r));
  },

  setFotoPerfil: (dataUrl) =>
    set((s) => ({ principal: s.principal ? { ...s.principal, foto_perfil: dataUrl } : s.principal })),

  markPasswordChanged: () =>
    set((s) => ({
      principal: s.principal ? { ...s.principal, debe_cambiar_password: false } : s.principal,
    })),
}));
