/**
 * Tests de JwtAdapter (C-55, D6 + D7).
 *
 * Verifica:
 *   - init() sin token en sessionStorage → estado unauthenticated.
 *   - init() con token válido en sessionStorage → principal hidratado.
 *   - login() exitoso → token almacenado, principal hidratado, listener notificado.
 *   - login() con respuesta 401 → lanza Error con el mensaje del backend.
 *   - logout() → limpia sessionStorage, principal null, listener notificado.
 *   - getToken() → undefined si no hay token; token si hay sesión activa.
 *   - onAuthChange → listener recibe 'authenticated' / 'unauthenticated'.
 *
 * Sin red ni DOM real. fetch se mockea con vi.fn().
 * sessionStorage se mockea con un Map en memoria.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JwtAdapter } from './jwt';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Construye un JWT HS256 fake (base64url) con los claims dados (SIN firma real). */
function _fakeJwt(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  const payload = btoa(JSON.stringify(claims))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
  return `${header}.${payload}.fakesig`;
}

const NOW_EPOCH = 1700000000; // timestamp fijo para tests

function _token(overrides: Record<string, unknown> = {}): string {
  return _fakeJwt({
    sub: 'test-sub',
    preferred_username: 'alumno1',
    email: 'alumno1@uni.edu',
    exp: NOW_EPOCH + 3600,
    realm_access: { roles: ['estudiante'] },
    ...overrides,
  });
}

// ---------------------------------------------------------------------------
// Setup: mock sessionStorage con Map en memoria
// ---------------------------------------------------------------------------

let _storage: Map<string, string>;

beforeEach(() => {
  _storage = new Map();
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => _storage.get(k) ?? null,
    setItem: (k: string, v: string) => { _storage.set(k, v); },
    removeItem: (k: string) => { _storage.delete(k); },
    clear: () => { _storage.clear(); },
  });
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('JwtAdapter.init()', () => {
  it('sin token en sessionStorage → estado unauthenticated', async () => {
    const adapter = new JwtAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.init();

    expect(adapter.getPrincipal()).toBeNull();
    expect(adapter.getToken()).toBeUndefined();
    expect(events).toContain('unauthenticated');
  });

  it('con token válido en sessionStorage → principal hidratado', async () => {
    const token = _token();
    _storage.set('jwt_access_token', token);
    _storage.set('jwt_access_token_expires_at', String(NOW_EPOCH + 3600));

    // Mockear Date.now para que el token no esté expirado.
    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    const adapter = new JwtAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.init();

    const principal = adapter.getPrincipal();
    expect(principal).not.toBeNull();
    expect(principal?.id_institucional).toBe('alumno1');
    expect(principal?.roles).toContain('estudiante');
    expect(events).toContain('authenticated');
  });
});

describe('JwtAdapter.login()', () => {
  it('login exitoso → token almacenado y principal hidratado', async () => {
    const accessToken = _token();
    const refreshToken = 'some-refresh-jti';

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: accessToken, refresh_token: refreshToken, token_type: 'Bearer' }),
    }));

    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    const adapter = new JwtAdapter();
    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.login({ username: 'alumno1@uni.edu', password: 'Pass123456' });

    expect(_storage.get('jwt_access_token')).toBe(accessToken);
    expect(_storage.get('jwt_refresh_token')).toBe(refreshToken);
    const principal = adapter.getPrincipal();
    expect(principal?.id_institucional).toBe('alumno1');
    expect(events).toContain('authenticated');
  });

  it('login fallido 401 → lanza Error con mensaje del backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Credenciales inválidas.' }),
    }));

    const adapter = new JwtAdapter();
    await expect(adapter.login({ username: 'x@uni.edu', password: 'mal' }))
      .rejects.toThrow('Credenciales inválidas.');
  });

  it('sin credenciales → lanza Error', async () => {
    const adapter = new JwtAdapter();
    await expect(adapter.login()).rejects.toThrow();
  });
});

describe('JwtAdapter.logout()', () => {
  it('limpia sessionStorage y notifica unauthenticated', async () => {
    _storage.set('jwt_access_token', _token());
    _storage.set('jwt_access_token_expires_at', String(NOW_EPOCH + 3600));
    _storage.set('jwt_refresh_token', 'some-jti');

    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    const adapter = new JwtAdapter();
    await adapter.init(); // hidrata desde storage

    const events: string[] = [];
    adapter.onAuthChange((s) => events.push(s));

    await adapter.logout();

    expect(_storage.has('jwt_access_token')).toBe(false);
    expect(_storage.has('jwt_refresh_token')).toBe(false);
    expect(adapter.getPrincipal()).toBeNull();
    expect(events).toContain('unauthenticated');
  });
});

describe('JwtAdapter.getToken()', () => {
  it('retorna undefined sin token en storage', async () => {
    const adapter = new JwtAdapter();
    expect(adapter.getToken()).toBeUndefined();
  });

  it('retorna token cuando hay sesión activa', async () => {
    const token = _token();
    _storage.set('jwt_access_token', token);
    _storage.set('jwt_access_token_expires_at', String(NOW_EPOCH + 3600));
    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    const adapter = new JwtAdapter();
    expect(adapter.getToken()).toBe(token);
  });

  it('retorna undefined cuando el token expiró', async () => {
    const token = _token({ exp: NOW_EPOCH - 100 });
    _storage.set('jwt_access_token', token);
    _storage.set('jwt_access_token_expires_at', String(NOW_EPOCH - 100));
    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    const adapter = new JwtAdapter();
    expect(adapter.getToken()).toBeUndefined();
    // Debe limpiar el storage
    expect(_storage.has('jwt_access_token')).toBe(false);
  });
});

describe('JwtAdapter.onAuthChange()', () => {
  it('retorna función de unsubscribe que detiene las notificaciones', async () => {
    const adapter = new JwtAdapter();
    const calls: string[] = [];
    const unsub = adapter.onAuthChange((s) => calls.push(s));

    await adapter.init(); // notifica unauthenticated
    unsub();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: _token(), refresh_token: 'jti', token_type: 'Bearer' }),
    }));
    vi.spyOn(Date, 'now').mockReturnValue(NOW_EPOCH * 1000);

    await adapter.login({ username: 'a@uni.edu', password: 'Pass1234' });
    // El listener fue removido antes del login, no debe recibir 'authenticated'.
    expect(calls).not.toContain('authenticated');
  });
});
