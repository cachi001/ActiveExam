import type { RefObject } from 'react';
import { Icon } from '../../ui/components';

interface Props {
  /** Ref del <video> de autovigilancia. La detección lee la resolución intrínseca
   *  del stream, no el tamaño CSS, así que el PiP puede ser chico sin afectar la IA. */
  videoRef: RefObject<HTMLVideoElement>;
  activo: boolean;
  eventCount: number;
  indiceActual: number;
  total: number;
  respondidas: Set<number>;
  tiempoLimiteMin: number | null | undefined;
  segRestantes: number | null;
  /** Clase de offset del sticky: `top-0` normal, `top-16` cuando hay pausa activa
   *  (para anclarse debajo del banner de pausa full-width). */
  stickyOffsetClass: string;
}

/**
 * Barra superior del examen — sticky, siempre visible mientras se scrollea.
 * Concentra el estado que antes vivía disperso (progreso + timer en el header de
 * la card, cámara flotante que se superponía al contenido) en un solo lugar que
 * NUNCA tapa la pregunta ni el sidebar: la cámara es un PiP in-flow al final de la
 * barra, no un overlay `fixed`.
 */
export function ExamenTopBar({
  videoRef, activo, eventCount, indiceActual, total,
  respondidas, tiempoLimiteMin, segRestantes, stickyOffsetClass,
}: Props) {
  const mm = segRestantes !== null ? String(Math.floor(segRestantes / 60)).padStart(2, '0') : '00';
  const ss = segRestantes !== null ? String(segRestantes % 60).padStart(2, '0') : '00';
  const urgente = segRestantes !== null && segRestantes < 300;
  const progresoPct = total > 0 ? Math.round((respondidas.size / total) * 100) : 0;

  return (
    <div
      className={`sticky ${stickyOffsetClass} z-30 mb-lg flex items-center gap-sm sm:gap-md rounded-xl px-sm sm:px-md py-sm bg-surface/85 backdrop-blur-md ring-1 ring-outline-variant/40 shadow-sm`}
    >
      {/* Progreso — ocupa el ancho libre */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-sm">
          <p className="text-label-md font-bold text-on-surface shrink-0">
            {total > 0 ? (
              <>Pregunta {indiceActual + 1}<span className="font-normal text-on-surface-variant"> de {total}</span></>
            ) : (
              'Examen'
            )}
          </p>
          <span className="hidden sm:inline text-label-xs text-on-surface-variant truncate">
            {respondidas.size}/{total} respondidas
          </span>
        </div>
        <div className="mt-1.5 h-1.5 rounded-full bg-surface-container overflow-hidden max-w-md">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${progresoPct}%` }}
          />
        </div>
      </div>

      {/* Timer */}
      {segRestantes !== null ? (
        <span className={`inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-bold tabular-nums shrink-0 ${
          urgente ? 'bg-error-container text-on-error-container' : 'bg-warning-container text-warning'
        }`}>
          <Icon name="timer" className="text-[18px]" /> {mm}:{ss}
        </span>
      ) : tiempoLimiteMin === null ? (
        <span className="hidden sm:inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-medium bg-surface-container text-on-surface-variant shrink-0">
          <Icon name="timer_off" className="text-[18px]" /> Sin límite
        </span>
      ) : null}

      {/* Cámara — PiP compacto, in-flow (nunca overlay). */}
      <div className="relative shrink-0 w-[72px] sm:w-24 rounded-lg overflow-hidden ring-1 ring-outline-variant/40 bg-inverse-surface aspect-video">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover"
          style={{ transform: 'scaleX(-1)' }}
        />
        <div className="absolute bottom-0.5 left-0.5 inline-flex items-center gap-[3px] bg-inverse-surface/70 text-inverse-on-surface text-[8px] font-semibold px-1 py-[1px] rounded-full">
          <span className={`w-1 h-1 rounded-full shrink-0 ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
          {eventCount}
        </div>
      </div>
    </div>
  );
}
