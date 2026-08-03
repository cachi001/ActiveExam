// Cache liviano stale-while-revalidate (C-73, sección 5). Se apoya en el mismo
// ciclo de vida que `useAsyncData` pero agrega un cache por clave a nivel de
// módulo: volver a una query ya cargada sirve lo último BUENO de inmediato y
// dispara una revalidación en background, sin parpadear a "loading".
//
// Decisión de dependencias: NO se suma una lib (react-query/swr). El objetivo de
// bundle es < 500 KB y lo que necesitamos —cache por clave, revalidación e
// invalidación por mutación— entra en un hook propio de pocas líneas. Si en el
// futuro aparecen necesidades de cache más ricas (dedup de requests en vuelo,
// TTL, garbage collection, devtools) se re-evalúa sumar la lib.
//
// Uso:
//   const { status, data, error, stale, retry } = useCachedData('examenes', () => api.listarX(), [dep]);
//   // dato que DEBE ser fresco (rendición/supervisión en vivo): fresh:true
//   const live = useCachedData('supervision', () => api.estadoVivo(id), [id], { fresh: true });
//   // tras una escritura, invalidar la clave afectada:
//   invalidateCache('examenes');
import { useCallback, useEffect, useRef, useState } from 'react';
import type { AsyncState, AsyncStatus } from './useAsyncData';

/** Último valor bueno por clave. */
const store = new Map<string, unknown>();
/** Suscriptores montados por clave: `invalidateCache` los hace revalidar. */
const subs = new Map<string, Set<() => void>>();

function mensaje(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  return 'Error inesperado';
}

export interface CachedState<T> extends AsyncState<T> {
  /**
   * `true` cuando la data mostrada viene del cache y todavía no se confirmó
   * fresca en esta corrida (se está revalidando, o la revalidación falló y se
   * mantiene el último valor bueno).
   */
  stale: boolean;
}

export interface CachedOptions {
  /**
   * Si `true`, ignora el cache stale por completo: el dato SIEMPRE se pide fresco
   * (rendición/supervisión en vivo). No lee ni escribe el cache compartido.
   */
  fresh?: boolean;
}

/**
 * Invalida la clave: descarta el último valor bueno y fuerza a revalidar a todas
 * las queries montadas con esa clave. Pensado para llamarse tras una mutación
 * que deja obsoleta la lectura (sección 5.4).
 */
export function invalidateCache(key: string): void {
  store.delete(key);
  subs.get(key)?.forEach((fn) => fn());
}

/** Helper de test: limpia el cache compartido entre casos. */
export function __resetCache(): void {
  store.clear();
  subs.clear();
}

export function useCachedData<T>(
  key: string,
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: CachedOptions = {},
): CachedState<T> {
  const { fresh = false } = options;

  // Semilla síncrona: si hay valor bueno cacheado (y no es `fresh`), la primera
  // pintura ya muestra data — sin parpadeo a "loading".
  const seeded = !fresh && store.has(key);
  const [status, setStatus] = useState<AsyncStatus>(seeded ? 'ready' : 'idle');
  const [data, setData] = useState<T | null>(seeded ? (store.get(key) as T) : null);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState<boolean>(seeded);

  // `fetcher` suele ser una arrow nueva por render; ref para no re-disparar por
  // su identidad — el disparo lo gobiernan `key`/`deps`.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  // Token del fetch vigente: descarta respuestas de fetches superados (race).
  const runId = useRef(0);

  const run = useCallback(() => {
    const id = ++runId.current;
    const servingStale = !fresh && store.has(key);
    if (servingStale) {
      // Sirve lo último bueno de inmediato y revalida en background.
      setData(store.get(key) as T);
      setStatus('ready');
      setStale(true);
    } else {
      // Sin cache utilizable: ciclo normal loading → ready | error.
      setStatus('loading');
      setStale(false);
    }
    setError(null);
    fetcherRef.current()
      .then((res) => {
        if (id !== runId.current) return;
        if (!fresh) store.set(key, res);
        setData(res);
        setStatus('ready');
        setStale(false);
      })
      .catch((e: unknown) => {
        if (id !== runId.current) return;
        if (servingStale) {
          // Revalidación fallida: NO se degrada el dato bueno a error/cero
          // (filosofía C-73). Se mantiene la data cacheada; se expone el error.
          setError(mensaje(e));
        } else {
          setError(mensaje(e));
          setStatus('error');
        }
      });
  }, [key, fresh]);

  useEffect(() => {
    run();
    if (fresh) return; // los `fresh` no participan del cache ni de la invalidación
    let set = subs.get(key);
    if (!set) {
      set = new Set();
      subs.set(key, set);
    }
    set.add(run);
    return () => {
      set!.delete(run);
      if (set!.size === 0) subs.delete(key);
    };
    // El disparo depende SÓLO de `run` (estable por `key`/`fresh`) y las `deps`.
    // eslint no puede ver el array dinámico, por eso se desactiva la regla acá.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, ...deps]);

  return { status, data, error, stale, retry: run };
}
