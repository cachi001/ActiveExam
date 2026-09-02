/**
 * Tests — BloqueoCuentaCard
 *
 * Qué se sostiene acá:
 *  a) una cuenta bloqueada se VE, con cuánto falta (antes no se veía en ningún lado)
 *  b) una cuenta sana no muestra alarma ni botón
 *  c) el botón destraba de verdad y avisa
 *  d) los intentos acumulados se muestran aunque el bloqueo ya haya vencido:
 *     el contador no se limpia solo, así que un error más vuelve a bloquear
 *  e) si la API falla, NO se dice que se destrabó
 *
 * Framework: vitest + @testing-library/react
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockToast = { success: vi.fn(), error: vi.fn() };
vi.mock('../../../ui/toast', () => ({
  useToast: () => mockToast,
}));

const mockDesbloquear = vi.fn();
vi.mock('../../../lib/apiAdmin', () => ({
  adminApi: {
    desbloquearUsuario: (...args: unknown[]) => mockDesbloquear(...args),
  },
}));

import { BloqueoCuentaCard } from './BloqueoCuentaCard';
import type { UsuarioAdmin } from '../../../lib/types';

const BASE: UsuarioAdmin = {
  id: 'u-1',
  username: 'coordinador1',
  email: 'coordinador1@uni.edu',
  nombre: 'Ana',
  apellido: 'Pérez',
  roles: ['coordinador'],
  auth_provider: 'local',
  eliminado_en: null,
};

function usuario(extra: Partial<UsuarioAdmin>): UsuarioAdmin {
  return { ...BASE, ...extra };
}

beforeEach(() => {
  mockDesbloquear.mockReset();
  mockToast.success.mockReset();
  mockToast.error.mockReset();
});

afterEach(cleanup);

describe('BloqueoCuentaCard', () => {
  it('muestra la cuenta bloqueada y cuánto falta', () => {
    render(
      <BloqueoCuentaCard
        usuario={usuario({
          bloqueado: true,
          bloqueo_segundos_restantes: 615,
          intentos_fallidos: 5,
        })}
      />,
    );

    expect(screen.getByRole('alert').textContent).toMatch(/bloqueada/i);
    // 615 s = 10:15
    expect(screen.getByText(/10:15/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /desbloquear/i })).toBeTruthy();
  });

  it('una cuenta sin bloqueos no muestra alarma ni botón', () => {
    render(
      <BloqueoCuentaCard usuario={usuario({ bloqueado: false, intentos_fallidos: 0 })} />,
    );

    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('button', { name: /desbloquear/i })).toBeNull();
  });

  it('muestra los intentos acumulados aunque el bloqueo haya vencido', () => {
    // Triangulación: el contador NO se limpia con el tiempo. Con 4 encima, el
    // próximo error bloquea, y el admin tiene que poder verlo y limpiarlo.
    render(
      <BloqueoCuentaCard usuario={usuario({ bloqueado: false, intentos_fallidos: 4 })} />,
    );

    expect(screen.getByText(/4 intentos fallidos/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /desbloquear/i })).toBeTruthy();
  });

  it('desbloquea, avisa y le pide a la pantalla que se refresque', async () => {
    mockDesbloquear.mockResolvedValue({ estaba_bloqueada: true });
    const onDesbloqueado = vi.fn();

    render(
      <BloqueoCuentaCard
        usuario={usuario({ bloqueado: true, bloqueo_segundos_restantes: 300, intentos_fallidos: 5 })}
        onDesbloqueado={onDesbloqueado}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /desbloquear/i }));

    await waitFor(() => expect(mockDesbloquear).toHaveBeenCalledWith('u-1'));
    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());
    expect(onDesbloqueado).toHaveBeenCalled();
    // Ya no hay nada que destrabar.
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('no dice que se destrabó cuando la API falla', async () => {
    mockDesbloquear.mockRejectedValue(new Error('HTTP 500'));

    render(
      <BloqueoCuentaCard
        usuario={usuario({ bloqueado: true, bloqueo_segundos_restantes: 300, intentos_fallidos: 5 })}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /desbloquear/i }));

    await waitFor(() => expect(mockToast.error).toHaveBeenCalled());
    expect(mockToast.success).not.toHaveBeenCalled();
    // El aviso sigue: la cuenta sigue bloqueada.
    expect(screen.getByRole('alert').textContent).toMatch(/bloqueada/i);
  });

  it('el reloj corre hacia abajo', async () => {
    vi.useFakeTimers();
    try {
      render(
        <BloqueoCuentaCard
          usuario={usuario({ bloqueado: true, bloqueo_segundos_restantes: 120, intentos_fallidos: 5 })}
        />,
      );

      expect(screen.getByText(/02:00/)).toBeTruthy();
      await vi.advanceTimersByTimeAsync(3000);
      expect(screen.getByText(/01:57/)).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});
