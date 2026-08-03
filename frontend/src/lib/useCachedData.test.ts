/**
 * Cache liviano stale-while-revalidate (C-73, sección 5). Lo crítico:
 *  - volver a una query ya cargada sirve lo último BUENO de inmediato y revalida
 *    en background (no parpadea a "loading");
 *  - el dato que debe ser fresco (rendición/supervisión en vivo) NO se sirve stale;
 *  - una mutación invalida la clave y la query montada se revalida;
 *  - una revalidación que falla NO degrada el dato bueno a error/cero (filosofía C-73).
 *
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useCachedData, invalidateCache } from './useCachedData';

describe('useCachedData (stale-while-revalidate)', () => {
  it('primera carga sin cache: loading → ready con la data (no stale)', async () => {
    const fetcher = vi.fn(() => Promise.resolve([1, 2, 3]));
    const { result } = renderHook(() => useCachedData('k-first', fetcher, []));

    expect(result.current.status === 'loading' || result.current.status === 'idle').toBe(true);
    expect(result.current.stale).toBe(false);

    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual([1, 2, 3]);
    expect(result.current.stale).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('segunda montada con misma clave: sirve lo último bueno de inmediato + revalida en background', async () => {
    const fetcher = vi.fn(() => Promise.resolve(['ultimo-bueno']));
    // Primera montada: puebla el cache.
    const first = renderHook(() => useCachedData('k-swr', fetcher, []));
    await waitFor(() => expect(first.result.current.status).toBe('ready'));
    first.unmount();

    // Segunda montada (misma clave): debe entregar ready + data SIN pasar por loading.
    const { result } = renderHook(() => useCachedData('k-swr', fetcher, []));
    expect(result.current.status).toBe('ready');
    expect(result.current.data).toEqual(['ultimo-bueno']);
    expect(result.current.stale).toBe(true);

    // Y dispara una revalidación en background → tras resolver, deja de ser stale.
    await waitFor(() => expect(result.current.stale).toBe(false));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('fresh: true → NO sirve del cache stale (arranca loading aunque haya cache)', async () => {
    const fetcher = vi.fn(() => Promise.resolve(['fresco']));
    // Puebla el cache para la clave.
    const seed = renderHook(() => useCachedData('k-live', fetcher, []));
    await waitFor(() => expect(seed.result.current.status).toBe('ready'));
    seed.unmount();

    // Con fresh:true NO debe servir el stale: arranca loading, data null hasta resolver.
    const { result } = renderHook(() => useCachedData('k-live', fetcher, [], { fresh: true }));
    expect(result.current.status).toBe('loading');
    expect(result.current.data).toBeNull();
    expect(result.current.stale).toBe(false);

    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toEqual(['fresco']);
  });

  it('invalidateCache(key) revalida una query montada (tras una mutación)', async () => {
    const fetcher = vi.fn(() => Promise.resolve(['v']));
    const { result } = renderHook(() => useCachedData('k-inv', fetcher, []));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(fetcher).toHaveBeenCalledTimes(1);

    act(() => invalidateCache('k-inv'));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it('revalidación en background que FALLA no degrada el dato bueno (sigue ready con data cacheada)', async () => {
    let intento = 0;
    const fetcher = vi.fn(() => {
      intento += 1;
      return intento === 1 ? Promise.resolve(['bueno']) : Promise.reject(new Error('revalidación falló'));
    });
    // Primera montada: puebla el cache con dato bueno.
    const first = renderHook(() => useCachedData('k-fail', fetcher, []));
    await waitFor(() => expect(first.result.current.status).toBe('ready'));
    first.unmount();

    // Segunda montada: sirve stale y revalida → la revalidación falla.
    const { result } = renderHook(() => useCachedData('k-fail', fetcher, []));
    expect(result.current.data).toEqual(['bueno']);

    await waitFor(() => expect(result.current.error).toBe('revalidación falló'));
    // Clave: NO degrada a error/cero — sigue mostrando el dato bueno.
    expect(result.current.status).toBe('ready');
    expect(result.current.data).toEqual(['bueno']);
  });
});
