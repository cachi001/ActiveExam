/**
 * authStore — Estado de autenticación (Zustand), separado de useApp (que maneja
 * estado de examen/biometría). Responsabilidad única: quién está logueado y con
 * qué roles.
 *
 * La fuente de verdad de la SESIÓN es Keycloak (maneja tokens + refresh). Este
 * store REFLEJA ese estado para que la UI reaccione sin leer keycloak.* en cada
 * componente. Se hidrata desde main.tsx tras initKeycloak() y en cada evento de
 * auth (login/logout/refresh).
 */
import { create } from 'zustand';
import type { Principal, Rol } from './types';
import {
  keycloak,
  principalFromToken,
  login as kcLogin,
  logout as kcLogout,
} from './auth/keycloak';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthState {
  status: AuthStatus;
  principal: Principal | null;
  token: string | null;
  /** Relee el estado desde Keycloak (llamar tras init y en cada evento de auth). */
  hydrateFromKeycloak: () => void;
  /** Redirige al login de Keycloak. */
  login: () => void;
  /** Cierra sesión en Keycloak. */
  logout: () => void;
  /** True si el principal tiene AL MENOS uno de los roles dados. */
  hasRole: (roles: Rol[]) => boolean;
  /**
   * Bypass de desarrollo: inyecta un principal dev con los 3 roles para navegar
   * la app sin Keycloak. SOLO se llama si AUTH_BYPASS está activo (dev). Ver devConfig.
   */
  enableDevBypass: () => void;
}

export const useAuth = create<AuthState>((set, get) => ({
  status: 'loading',
  principal: null,
  token: null,

  hydrateFromKeycloak: () => {
    if (keycloak.authenticated) {
      set({
        status: 'authenticated',
        principal: principalFromToken(),
        token: keycloak.token ?? null,
      });
    } else {
      set({ status: 'unauthenticated', principal: null, token: null });
    }
  },

  login: () => kcLogin(),
  logout: () => {
    if (keycloak.authenticated) {
      // Sesión real: Keycloak cierra la sesión y redirige a la raíz (login).
      kcLogout();
    } else {
      // Modo bypass / sin sesión real: limpiamos el estado local y volvemos al login.
      set({ status: 'unauthenticated', principal: null, token: null });
      window.location.hash = '#/login';
    }
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
}));
