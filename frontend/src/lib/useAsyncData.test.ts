/**
 * Contrato de carga resiliente (C-73, sección 1). Lo crítico: un error NUNCA se
 * degrada a "datos en cero" — el estado distingue loading/ready/error, y `data`
 * no se pisa con ceros cuando el fetch falla.
 *
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useAsyncData } from './useAsyncData';

describe('useAsyncData', () => {
  it('éxito con lista → status "ready" con la data', async () => {
    const { result } = renderHook(() => useAsyncData(() => Promise.resolve([1, 2, 3]), []));
    // Arranca cargando (no en cero).
    expect(result.current.status === 'loading' || result.current.status === 'idle').toBe(true);
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual([1, 2, 3]);
    expect(result.current.error).toBeNull();
  });

  it('éxito vacío → "ready" con [] (vacío-real, no error)', async () => {
    const { result } = renderHook(() => useAsyncData(() => Promise.resolve([] as number[]), []));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('error → status "error" y data NO se pisa con ceros', async () => {
    const { result } = renderHook(() =>
      useAsyncData(() => Promise.reject(new Error('boom')), []),
    );
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toBe('boom');
    expect(result.current.data).toBeNull(); // jamás [] ni 0 fantasma
  });

  it('retry() re-dispara: error → ready la segunda vez', async () => {
    let intento = 0;
    const fetcher = vi.fn(() => {
      intento += 1;
      return intento === 1 ? Promise.reject(new Error('primer fallo')) : Promise.resolve(['ok']);
    });
    const { result } = renderHook(() => useAsyncData(fetcher, []));
    await waitFor(() => expect(result.current.status).toBe('error'));

    act(() => result.current.retry());
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual(['ok']);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('anti-race: una respuesta vieja que llega tarde no pisa a la nueva', async () => {
    // Primer fetch lento que resuelve "viejo"; segundo (tras cambiar dep) rápido "nuevo".
    let resolverViejo: (v: string[]) => void = () => {};
    const lento = () => new Promise<string[]>((res) => { resolverViejo = res; });
    const rapido = () => Promise.resolve(['nuevo']);

    let usarRapido = false;
    const { result, rerender } = renderHook(
      ({ dep }: { dep: number }) => useAsyncData(() => (usarRapido ? rapido() : lento()), [dep]),
      { initialProps: { dep: 0 } },
    );

    // Cambia la dep → dispara el segundo fetch (rápido), que gana.
    usarRapido = true;
    rerender({ dep: 1 });
    await waitFor(() => expect(result.current.data).toEqual(['nuevo']));

    // Ahora resuelve el viejo: NO debe pisar a "nuevo".
    act(() => resolverViejo(['viejo']));
    await Promise.resolve();
    expect(result.current.data).toEqual(['nuevo']);
    expect(result.current.status).toBe('ready');
  });
});
