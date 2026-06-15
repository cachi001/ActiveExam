/**
 * Tests de authStore (C-55, Zustand).
 *
 * Verifica:
 *   - hydrateFromProvider() sin principal → estado unauthenticated.
 *   - hydrateFromProvider() con principal → estado authenticated.
 *   - login() delega al provider y actualiza el store.
 *   - logout() delega al provider y limpia el store.
 *   - hasRole() retorna true/false según los roles del principal.
 *   - loginDemo() → DemoAdapter.loginConRol() llamado.
 *
 * El provider se mockea — no hay red ni Keycloak.
 * Zustand crea un nuevo store por describe block para evitar state leakage.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AuthProvider, AuthStatus } from './auth/provider';
import type { Principal, Rol } from './types';

// ---------------------------------------------------------------------------
// Mock del provider activo (JwtAdapter-like)
// ---------------------------------------------------------------------------

function _makeMockProvider(principal: Principal | null = null, token: string | null = null): AuthProvider & {
  _simulateAuthChange: (s: AuthStatus) => void;
} {
  const listeners: Array<(s: AuthStatus) => void> = [];
  const provider = {
    _principal: principal,
    _token: token,
    init: vi.fn().mockResolvedValue(undefined),
    login: vi.fn().mockImplementation(async () => {
      provider._principal = _fakeEstudiante();
      provider._token = 'access-token-abc';
    }),
    logout: vi.fn().mockImplementation(async () => {
      provider._principal = null;
      provider._token = null;
    }),
    getToken: () => provider._token ?? undefined,
    getPrincipal: () => provider._principal,
    onAuthChange: (cb: (s: AuthStatus) => void) => {
      listeners.push(cb);
      return () => {
        const i = listeners.indexOf(cb);
        if (i !== -1) listeners.splice(i, 1);
      };
    },
    _simulateAuthChange: (s: AuthStatus) => listeners.forEach((l) => l(s)),
  };
  return provider as typeof provider & AuthProvider;
}

function _fakeEstudiante(): Principal {
  return {
    id_institucional: 'FRM-23-4912',
    nombre: 'Emiliano Cáceres',
    email: 'ecaceres@uni.edu',
    roles: ['estudiante'],
    mfa_satisfecho: false,
    jurisdiccion: 'AR',
  };
}

function _fakeProctor(): Principal {
  return {
    id_institucional: 'FRM-DOC-1182',
    nombre: 'Dr. Proctor',
    email: 'proctor@uni.edu',
    roles: ['proctor'],
    mfa_satisfecho: true,
    jurisdiccion: 'AR',
  };
}

// ---------------------------------------------------------------------------
// Importar authStore — se importa DESPUÉS de crear los mocks para evitar
// que el módulo se inicialice con keycloak.ts real.
// ---------------------------------------------------------------------------

// NOTA: authStore usa módulo-level state (_activeProvider). Para evitar
// contaminación entre tests, re-importamos el módulo o reseteamos el state.
// La forma más simple: importar el store y llamar hydrateFromProvider en cada test.

import { useAuth } from './authStore';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('authStore.hydrateFromProvider()', () => {
  it('sin principal → estado unauthenticated', () => {
    const provider = _makeMockProvider(null, null);
    useAuth.getState().hydrateFromProvider(provider);

    expect(useAuth.getState().status).toBe('unauthenticated');
    expect(useAuth.getState().principal).toBeNull();
    expect(useAuth.getState().token).toBeNull();
  });

  it('con principal → estado authenticated y principal seteado', () => {
    const provider = _makeMockProvider(_fakeEstudiante(), 'token-xyz');
    useAuth.getState().hydrateFromProvider(provider);

    expect(useAuth.getState().status).toBe('authenticated');
    expect(useAuth.getState().principal?.id_institucional).toBe('FRM-23-4912');
    expect(useAuth.getState().token).toBe('token-xyz');
  });
});

describe('authStore.login()', () => {
  it('delega al provider y actualiza el store con el principal', async () => {
    const provider = _makeMockProvider(null, null);
    useAuth.getState().hydrateFromProvider(provider);

    await useAuth.getState().login({ username: 'x@uni.edu', password: 'Pass1234' });

    expect(provider.login).toHaveBeenCalledWith({ username: 'x@uni.edu', password: 'Pass1234' });
    expect(useAuth.getState().status).toBe('authenticated');
    expect(useAuth.getState().principal?.id_institucional).toBe('FRM-23-4912');
  });
});

describe('authStore.logout()', () => {
  it('delega al provider y limpia el store', async () => {
    const provider = _makeMockProvider(_fakeEstudiante(), 'token-xyz');
    useAuth.getState().hydrateFromProvider(provider);

    useAuth.getState().logout();
    // logout() hace `provider.logout().then(() => set(...))`. El `.then` es un
    // microtask; un setTimeout(0) macro-task corre DESPUÉS de que el microtask
    // resolvió, así que para entonces el store ya quedó limpio. (Antes esto
    // usaba `vi.runAllTimersAsync?.()`, que en vitest v4 existe y se invoca,
    // pero sin fake timers activados LANZA — por eso fallaba.)
    await new Promise((r) => setTimeout(r, 0));

    expect(useAuth.getState().status).toBe('unauthenticated');
    expect(useAuth.getState().principal).toBeNull();
    expect(useAuth.getState().token).toBeNull();
  });
});

describe('authStore.hasRole()', () => {
  it('retorna true si el principal tiene el rol', () => {
    const provider = _makeMockProvider(_fakeProctor(), 'tok');
    useAuth.getState().hydrateFromProvider(provider);

    expect(useAuth.getState().hasRole(['proctor'])).toBe(true);
    expect(useAuth.getState().hasRole(['admin_sistema'])).toBe(false);
    expect(useAuth.getState().hasRole(['proctor', 'admin_sistema'])).toBe(true);
  });

  it('retorna false sin principal', () => {
    const provider = _makeMockProvider(null, null);
    useAuth.getState().hydrateFromProvider(provider);

    expect(useAuth.getState().hasRole(['estudiante'])).toBe(false);
  });
});

describe('authStore.loginDemo()', () => {
  it('llama loginConRol en el DemoAdapter y actualiza el store', () => {
    // OJO: NO spreadear el mock — `getPrincipal` es un closure que lee el
    // `_principal` del objeto ORIGINAL; un spread crea otro objeto y el closure
    // seguiría leyendo null. Mutamos el MISMO objeto que el closure observa.
    const provider = _makeMockProvider(null, null);
    const loginConRol = vi.fn().mockImplementation(() => {
      // Simular que el DemoAdapter, al loguear, deja el principal en el provider.
      (provider as { _principal: Principal | null })._principal = _fakeEstudiante();
    });
    (provider as { loginConRol?: (r: Rol) => void }).loginConRol = loginConRol;

    useAuth.getState().hydrateFromProvider(provider);
    // Antes de loginDemo no hay principal → unauthenticated.
    expect(useAuth.getState().status).toBe('unauthenticated');

    useAuth.getState().loginDemo('estudiante');

    expect(loginConRol).toHaveBeenCalledWith('estudiante');
    // loginDemo → loginConRol setea el principal → re-hidrata → authenticated.
    expect(useAuth.getState().status).toBe('authenticated');
  });
});
