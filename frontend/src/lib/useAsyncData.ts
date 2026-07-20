// Contrato de carga resiliente (C-73). Un solo lugar que modela el ciclo de vida
// de un fetch asíncrono, para que las pantallas NUNCA degraden un error a "datos
// en cero": el estado distingue explícitamente `loading` / `ready` / `error`.
//
// Uso:
//   const { status, data, error, retry } = useAsyncData(() => api.listarX(), [dep]);
//   if (status === 'error') return <Error onRetry={retry} />;
//   if (status !== 'ready') return <Cargando />;
//   return <Vista data={data} />;   // data: T garantizado en `ready`
import { useCallback, useEffect, useRef, useState } from 'react';

export type AsyncStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface AsyncState<T> {
  status: AsyncStatus;
  /** Presente sólo cuando `status === 'ready'` (puede ser `[]` si vino vacío). */
  data: T | null;
  /** Mensaje de error cuando `status === 'error'`. */
  error: string | null;
  /** Re-dispara el fetch: `loading` → `ready` | `error`. */
  retry: () => void;
}

function mensaje(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  return 'Error inesperado';
}

/**
 * Ejecuta `fetcher` y expone su ciclo de vida. Se re-ejecuta cuando cambian las
 * `deps`. Un fetch que resuelve pisa `data` y pasa a `ready` (incluso con `[]`);
 * uno que rechaza pasa a `error` SIN tocar `data` con ceros.
 *
 * Anti-race: sólo el último fetch disparado puede escribir el estado (se ignora
 * la respuesta de un fetch viejo que llega tarde tras cambiar las deps).
 */
export function useAsyncData<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  // `fetcher` suele ser una arrow nueva por render; lo guardamos en un ref para
  // no re-disparar por su identidad — el disparo lo gobiernan las `deps`.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  // Token del fetch vigente: descarta respuestas de fetches superados (race).
  const runId = useRef(0);

  const run = useCallback(() => {
    const id = ++runId.current;
    setStatus('loading');
    setError(null);
    fetcherRef.current()
      .then((res) => {
        if (id !== runId.current) return;
        setData(res);
        setStatus('ready');
      })
      .catch((e: unknown) => {
        if (id !== runId.current) return;
        setError(mensaje(e));
        setStatus('error');
      });
  }, []);

  useEffect(() => {
    run();
    // El disparo depende SÓLO de `deps` (y `run`, estable). eslint no puede ver
    // el array dinámico, por eso se desactiva la regla acá.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, ...deps]);

  return { status, data, error, retry: run };
}
