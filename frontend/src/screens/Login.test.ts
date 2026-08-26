/**
 * Tests de lógica de Login (C-55, FormularioJwt — único provider: JWT propio).
 *
 * Verifica el routing post-login sin renderizar el componente (no requiere
 * @testing-library/react ni jsdom).
 *
 * Qué se testea:
 *   - homePorRol(): calcula la ruta correcta para cada rol.
 *   - FormularioJwt integra correctamente con authStore: login exitoso → estado authenticated.
 *   - Manejo de error de login: el store permanece unauthenticated.
 *
 * NOTA: el render de JSX requeriría @testing-library/react (no instalado en MVP).
 * Estos tests cubren la lógica pura; los render tests se agregan cuando se
 * incorpore @testing-library/react + jsdom al setup de vitest.
 */

import { describe, expect, it, vi } from 'vitest';
import type { Rol } from '../lib/types';

// ---------------------------------------------------------------------------
// homePorRol vive en `lib/auth/homePorRol.ts` con sus propios tests.
//
// Estaba duplicada acá a mano, con un comentario que reconocía la copia, y las
// dos versiones ya habían divergido: la real mandaba al tutor a
// `/admin/examenes` y esta ni contemplaba al tutor. Un test que valida una copia
// no prueba nada sobre la función que corre en producción — y el bug que se
// escapó por ese hueco dejaba al tutor sin poder entrar al sistema.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Tests de manejo de errores de login (lógica de FormularioJwt)
// ---------------------------------------------------------------------------

describe('FormularioJwt — manejo de errores', () => {
  it('error de login con mensaje string → muestra el mensaje exacto', () => {
    // Simula la lógica del catch en handleSubmit.
    function getErrorMessage(err: unknown): string {
      return err instanceof Error ? err.message : 'Credenciales inválidas.';
    }

    expect(getErrorMessage(new Error('Credenciales inválidas.'))).toBe('Credenciales inválidas.');
    expect(getErrorMessage(new Error('Error 500'))).toBe('Error 500');
    expect(getErrorMessage('string-error')).toBe('Credenciales inválidas.');
    expect(getErrorMessage(null)).toBe('Credenciales inválidas.');
  });

  it('error desconocido → fallback "Credenciales inválidas."', () => {
    function getErrorMessage(err: unknown): string {
      return err instanceof Error ? err.message : 'Credenciales inválidas.';
    }
    expect(getErrorMessage(undefined)).toBe('Credenciales inválidas.');
    expect(getErrorMessage(42)).toBe('Credenciales inválidas.');
  });
});

// ---------------------------------------------------------------------------
// Tests de integración con authStore (sin DOM — lógica de estado)
// ---------------------------------------------------------------------------

describe('FormularioJwt — integración con authStore', () => {
  it('login exitoso → authStore pasa a authenticated', async () => {
    // Importar el store y mockear el provider.
    const { useAuth } = await import('../lib/authStore');
    const principal = {
      username: 'alumno1',
      nombre: 'Alumno 1',
      email: 'alumno1@uni.edu',
      roles: ['estudiante'] as Rol[],
      mfa_satisfecho: false,
      jurisdiccion: 'AR',
    };

    const mockProvider = {
      init: vi.fn(),
      login: vi.fn().mockImplementation(async () => {
        // simular que login seteó el principal
        mockProvider._principal = principal;
        mockProvider._token = 'access-token';
      }),
      logout: vi.fn(),
      getToken: () => mockProvider._token ?? undefined,
      getPrincipal: () => mockProvider._principal ?? null,
      onAuthChange: vi.fn().mockReturnValue(() => {}),
      _principal: null as typeof principal | null,
      _token: null as string | null,
    };

    useAuth.getState().hydrateFromProvider(mockProvider);
    await useAuth.getState().login({ username: 'alumno1@uni.edu', password: 'Pass1234' });

    expect(useAuth.getState().status).toBe('authenticated');
    expect(useAuth.getState().principal?.username).toBe('alumno1');
  });

  it('login fallido → authStore permanece unauthenticated', async () => {
    const { useAuth } = await import('../lib/authStore');

    const mockProvider = {
      init: vi.fn(),
      login: vi.fn().mockRejectedValue(new Error('Credenciales inválidas.')),
      logout: vi.fn(),
      getToken: () => undefined,
      getPrincipal: () => null,
      onAuthChange: vi.fn().mockReturnValue(() => {}),
    };

    useAuth.getState().hydrateFromProvider(mockProvider);

    await expect(useAuth.getState().login({ username: 'x@uni.edu', password: 'mal' }))
      .rejects.toThrow('Credenciales inválidas.');

    expect(useAuth.getState().status).toBe('unauthenticated');
  });
});
