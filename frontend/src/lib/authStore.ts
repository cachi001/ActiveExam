/**
 * authStore — Estado de autenticación (Zustand), desacoplado del provider concreto (C-55).
 *
 * En vez de importar keycloak.ts directamente, delega al provider activo
 * (JwtAdapter | KeycloakAdapter | DemoAdapter) vía la interfaz AuthProvider.
 *
 * La interfaz del store NO cambia: los componentes que usan useAuth funcionan
 * sin modificación. Solo la implementación interna cambia.
 *
 * hydrateFromProvider() reemplaza hydrateFromKeycloak() — mismo resultado,
 * agnóstico del provider.
 *
 * loginDemo() ahora usa DemoAdapter.loginConRol() en lugar de setear el estado
 * directamente — mantiene coherencia con el adapter.
 */
import { create } from 'zustand';
import type { Principal, Rol } from './types';
import type { AuthProvider, AuthStatus } from './auth/provider';
import { API_BASE, USE_REAL_BACKEND } from './api';

export type { AuthStatus };

/**
 * Trae nombre/apellido del usuario logueado desde GET /auth/me y los devuelve
 * para que el caller los fusione en el principal del store. El JWT propio
 * (C-55, own_issuer.py) NO incluye el claim `name`, así que sin esta llamada
 * el frontend cae al fallback `id_institucional` y la UI muestra "Hola, 123".
 *
 * Fire-and-forget seguro: cualquier error (sin red, 401, etc.) se silencia y
 * el principal queda como vino del token.
 */
async function fetchMyName(
  provider: AuthProvider,
): Promise<{ nombre?: string; apellido?: string } | null> {
  if (!USE_REAL_BACKEND) return null;
  const token = provider.getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { nombre?: string | null; apellido?: string | null };
    return {
      nombre: data.nombre ?? undefined,
      apellido: data.apellido ?? undefined,
    };
  } catch {
    return null;
  }
}

interface AuthState {
  status: AuthStatus;
  principal: Principal | null;
  token: string | null;

  /** Hidrata el store desde el provider activo (reemplaza hydrateFromKeycloak). */
  hydrateFromProvider: (provider: AuthProvider) => void;

  /** @deprecated Alias para hydrateFromProvider — mantiene compatibilidad con main.tsx antiguo. */
  hydrateFromKeycloak: () => void;

  /** Inicia sesión con credenciales (JwtAdapter) o redirige al IdP (Keycloak). */
  login: (creds?: { username: string; password: string }) => Promise<void>;

  /** Cierra sesión en el provider activo. */
  logout: () => void;

  /** True si el principal tiene AL MENOS uno de los roles dados. */
  hasRole: (roles: Rol[]) => boolean;

  /**
   * Bypass de desarrollo: inyecta un principal dev con los 3 roles para navegar
   * la app sin auth. SOLO se llama si AUTH_BYPASS está activo (dev). Ver devConfig.
   */
  enableDevBypass: () => void;

  /** Login de DEMO: entra con un principal demo del rol elegido (vía DemoAdapter). */
  loginDemo: (rol: Rol) => void;
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
      // `nombre = id_institucional` como fallback. Enriquecemos en background
      // con GET /auth/me para mostrar "Hola, Nombre Apellido" en lugar del
      // legajo. Si la llamada falla, el principal queda como estaba.
      void fetchMyName(provider).then((extra) => {
        if (!extra || !extra.nombre) return;
        const current = get().principal;
        if (!current) return;
        const nombreCompleto = extra.apellido
          ? `${extra.nombre} ${extra.apellido}`
          : extra.nombre;
        // Solo actualizamos si lo que tenemos sigue siendo el fallback
        // (id_institucional). Si el provider ya nos dio un nombre humano
        // (Keycloak con claim `name`), respetamos eso.
        if (current.nombre !== current.id_institucional) return;
        set({
          principal: {
            ...current,
            nombre: nombreCompleto,
            apellido: extra.apellido ?? current.apellido,
          },
        });
      });
    } else {
      set({ status: 'unauthenticated', principal: null, token: null });
    }
  },

  // Alias de retrocompatibilidad (main.tsx antiguo lo llama tras Keycloak).
  // En el nuevo main.tsx esto no se llama — se usa hydrateFromProvider.
  hydrateFromKeycloak: () => {
    if (_activeProvider) {
      get().hydrateFromProvider(_activeProvider);
    }
  },

  login: async (creds?: { username: string; password: string }) => {
    if (!_activeProvider) return;
    await _activeProvider.login(creds);
    // Actualizar el store tras login exitoso.
    get().hydrateFromProvider(_activeProvider);
  },

  logout: () => {
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

  enableDevBypass: () =>
    set({
      status: 'authenticated',
      token: null,
      principal: {
        id_institucional: 'DEV-LOCAL',
        nombre: 'Dev (bypass)',
        email: 'dev@local',
        roles: ['estudiante', 'proctor', 'admin_sistema'],
        mfa_satisfecho: true,
        jurisdiccion: 'AR',
      },
    }),

  loginDemo: (rol: Rol) => {
    // Si el provider activo es DemoAdapter, delegar.
    if (_activeProvider && 'loginConRol' in _activeProvider) {
      (_activeProvider as { loginConRol: (r: Rol) => void }).loginConRol(rol);
      get().hydrateFromProvider(_activeProvider);
    } else {
      // Fallback inline (compatibilidad cuando no hay provider inicializado).
      const DEMO_PRINCIPALS: Record<Rol, Principal> = {
        estudiante: {
          id_institucional: 'FRM-23-4912', nombre: 'Emiliano Cáceres', email: 'ecaceres@frm.utn.edu.ar',
          roles: ['estudiante'], mfa_satisfecho: true, jurisdiccion: 'AR-MZA',
        },
        proctor: {
          id_institucional: 'FRM-DOC-1182', nombre: 'Dra. Carolina Ferreyra', email: 'cferreyra@frm.utn.edu.ar',
          roles: ['proctor'], mfa_satisfecho: true, jurisdiccion: 'AR',
        },
        admin_sistema: {
          id_institucional: 'FRM-ADM-0021', nombre: 'Lucía Mendoza', email: 'lmendoza@frm.utn.edu.ar',
          roles: ['admin_sistema'], mfa_satisfecho: true, jurisdiccion: 'AR',
        },
      };
      set({ status: 'authenticated', token: 'demo', principal: DEMO_PRINCIPALS[rol] });
    }
  },
}));
