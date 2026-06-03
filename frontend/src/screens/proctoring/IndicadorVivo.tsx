/**
 * IndicadorVivo — Pastilla "En vivo" con punto que late y contador de frescura.
 *
 * Muestra cuántos segundos pasaron desde el último refresh exitoso ("actualizado
 * hace Xs"). El contador avanza con un tick interno de 1s independiente del
 * polling de datos, para que la frescura se vea fluida sin re-fetchear.
 *
 * El punto deja de latir y la pastilla baja de tono cuando `activo` es false
 * (p. ej. mientras una recarga manual está en curso o tras un error).
 */
import { useEffect, useState } from 'react';

/** Formatea el lapso desde el último refresh de forma amable. */
function formatFrescura(segundos: number): string {
  if (segundos < 1) return 'recién';
  if (segundos < 60) return `hace ${segundos}s`;
  const min = Math.floor(segundos / 60);
  return `hace ${min} min`;
}

export function IndicadorVivo({
  ultimoRefresh,
  activo = true,
}: {
  /** Timestamp (ms) del último refresh exitoso, o null si todavía no hubo ninguno. */
  ultimoRefresh: number | null;
  /** false mientras hay una recarga en curso o el loop quedó degradado. */
  activo?: boolean;
}) {
  const [, forzarTick] = useState(0);

  // Tick de 1s para refrescar el contador "hace Xs" sin tocar los datos.
  useEffect(() => {
    const id = setInterval(() => forzarTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const segundos = ultimoRefresh === null
    ? null
    : Math.max(0, Math.round((Date.now() - ultimoRefresh) / 1000));

  return (
    <span
      className={`inline-flex items-center gap-base px-sm py-base rounded-full text-label-sm font-semibold
        ${activo ? 'bg-success-container text-success' : 'bg-surface-container-high text-on-surface-variant'}`}
    >
      <span className="relative flex w-2 h-2">
        {activo && (
          <span className="absolute inline-flex w-full h-full rounded-full bg-success opacity-75 animate-ping" />
        )}
        <span className={`relative inline-flex w-2 h-2 rounded-full ${activo ? 'bg-success' : 'bg-on-surface-variant'}`} />
      </span>
      En vivo
      {segundos !== null && (
        <>
          <span className="opacity-50" aria-hidden>·</span>
          <span className="font-normal">actualizado {formatFrescura(segundos)}</span>
        </>
      )}
    </span>
  );
}

export default IndicadorVivo;
