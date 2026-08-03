// useAutoRefresh — vuelve a ejecutar un callback en un intervalo fijo.
//
// Uso: refrescar automáticamente páginas con tablas/dashboards para que muestren
// lo último sin que el usuario tenga que apretar "Actualizar". El default son 5
// minutos; Supervisión en vivo usa un intervalo mucho más corto (es urgente).
//
// Detalles:
// - Pausa cuando la pestaña está oculta (document.hidden) y dispara un refresh al
//   volver a estar visible, para no machacar el backend con pestañas de fondo.
// - `enabled=false` desactiva el timer (útil si hay un fetch en curso o un modal).
import { useEffect, useRef } from 'react';

export const CINCO_MINUTOS_MS = 5 * 60 * 1000;

export function useAutoRefresh(
  callback: () => void,
  intervalMs: number = CINCO_MINUTOS_MS,
  enabled: boolean = true,
): void {
  // Ref al callback para no reiniciar el intervalo en cada render (el callback
  // suele recrearse por cierre sobre estado/filtros).
  const cbRef = useRef(callback);
  useEffect(() => {
    cbRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const id = window.setInterval(() => {
      if (!document.hidden) cbRef.current();
    }, intervalMs);

    // Al volver a la pestaña, refrescá enseguida (los datos pueden estar viejos).
    const onVisible = () => {
      if (!document.hidden) cbRef.current();
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [intervalMs, enabled]);
}
