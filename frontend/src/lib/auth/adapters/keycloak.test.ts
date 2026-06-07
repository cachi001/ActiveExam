/**
 * Tests de KeycloakAdapter (C-55, D6).
 *
 * Verifica que el adapter delega correctamente a los helpers de keycloak.ts:
 *   - init() llama initKeycloak() y notifica el estado según keycloak.authenticated.
 *   - login() llama kcLogin() (no acepta credenciales directas — redirige al IdP).
 *   - logout() llama kcLogout().
 *   - getToken() delega a kcGetToken().
 *   - getPrincipal() delega a principalFromToken().
 *
 * lib/auth/keycloak.ts se mockea completamente (sin red ni DOM).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock keycloak.ts ANTES de importar KeycloakAdapter.
vi.mock('../keycloak', () => ({
  keycloak: {
    authenticated: false,
    onAuthSuccess: undefined as (() => void) | undefined,
    onAuthRefreshSuccess: undefined as (() => void) | undefined,
    onAuthLogout: undefined as (() => void) | undefined,
    onTokenExpired: undefined as (() => void) | undefined,
    updateToken: vi.fn().mockResolvedValue(true),
  },
  initKeycloak: vi.fn().mockResolvedValue(undefined),
  principalFromToken: vi.fn().mockReturnValue(null),
  login: vi.fn(),
  logout: vi.fn(),
  getToken: vi.fn().mockReturnValue(undefined),
}));

import { KeycloakAdapter } from './keycloak';
import * as kcModule from '../keycloak';

beforeEach(() => {
  vi.clearAllMocks();
  // Resetear keycloak.authenticated a false por defecto.
  (kcModule.keycloak as { authenticated: boolean }).authenticated = false;
});

describe('KeycloakAdapter.init()', () => {
  it('llama initKeycloak() y notifica unauthenticated si no está autenticado', async () => {
    (kcModule.keycloak as { authenticated: boolean }).authenticated = false;

    const adapter = new KeycloakAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.init();

    expect(kcModule.initKeycloak).toHaveBeenCalledOnce();
    expect(events).toContain('unauthenticated');
  });

  it('notifica authenticated cuando keycloak.authenticated es true', async () => {
    (kcModule.keycloak as { authenticated: boolean }).authenticated = true;

    const adapter = new KeycloakAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.init();

    expect(events).toContain('authenticated');
  });

  it('notifica unauthenticated si initKeycloak lanza', async () => {
    vi.mocked(kcModule.initKeycloak).mockRejectedValueOnce(new Error('red error'));

    const adapter = new KeycloakAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.init();

    expect(events).toContain('unauthenticated');
  });
});

describe('KeycloakAdapter.login()', () => {
  it('llama kcLogin() (sin credenciales directas)', async () => {
    const adapter = new KeycloakAdapter();
    await adapter.login();
    expect(kcModule.login).toHaveBeenCalledOnce();
  });

  it('ignora credenciales si se pasan — igualmente llama kcLogin()', async () => {
    const adapter = new KeycloakAdapter();
    await adapter.login({ username: 'u', password: 'p' });
    expect(kcModule.login).toHaveBeenCalledOnce();
  });
});

describe('KeycloakAdapter.logout()', () => {
  it('delega a kcLogout()', async () => {
    const adapter = new KeycloakAdapter();
    await adapter.logout();
    expect(kcModule.logout).toHaveBeenCalledOnce();
  });
});

describe('KeycloakAdapter.getToken()', () => {
  it('delega a kcGetToken()', () => {
    vi.mocked(kcModule.getToken).mockReturnValue('kc-token-abc');
    const adapter = new KeycloakAdapter();
    expect(adapter.getToken()).toBe('kc-token-abc');
  });
});

describe('KeycloakAdapter.getPrincipal()', () => {
  it('delega a principalFromToken()', () => {
    const fakePrincipal = {
      id_institucional: 'kc-user',
      nombre: 'KC User',
      email: 'kc@uni.edu',
      roles: ['proctor'] as const,
      mfa_satisfecho: true,
      jurisdiccion: 'AR',
    };
    vi.mocked(kcModule.principalFromToken).mockReturnValue(fakePrincipal);

    const adapter = new KeycloakAdapter();
    expect(adapter.getPrincipal()).toEqual(fakePrincipal);
  });
});
