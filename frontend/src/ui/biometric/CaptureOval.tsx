/**
 * CaptureOval — óvalo dominante con la cámara + anillo de progreso (presentacional).
 *
 * Renderiza: el contenedor del óvalo con fade-in, el clip-path ellipse que recorta
 * el <video>, la capa de éxito y un anillo SVG que se va llenando a medida que
 * el alumno completa pasos.
 *
 * El `videoRef` se reenvía (forwardRef) al elemento <video> para que el loop RAF
 * y la inicialización de cámara del padre sigan leyendo el MISMO elemento.
 *
 * Mejoras de UX:
 *  - Anillo SVG con `strokeDasharray` controlado por `progreso` (0..1). Antes era
 *    sólo un anillo plano de color: no comunicaba avance dentro de un paso.
 *  - `tono` cambia el color del trazo según el estado de la guía de encuadre
 *    ('ok' azul, 'aviso' ámbar para hints como "acercate", "más luz", 'exito' verde).
 *  - Color del clip de fondo del óvalo también responde al tono — un cliff visual
 *    suave para que el alumno asocie color con instrucción.
 */

import { forwardRef } from 'react';
import { Icon } from '../components';

export type OvalTono = 'idle' | 'ok' | 'aviso' | 'exito';

export interface CaptureOvalProps {
  /** El óvalo + cámara solo se revelan cuando esto es true. */
  listoParaMostrar: boolean;
  /** Capa de éxito (velo verde + check) y anillo verde. */
  enExito: boolean;
  /** Motor de visión listo (anillo azul scanning). */
  motorListo: boolean;
  /** Modo fallback manual (sin motor → anillo punteado). */
  fallbackManual: boolean;
  /**
   * Avance dentro de la captura (0..1):
   *  - Reto completado: salta a `(retoIdx+1)/total`.
   *  - Dentro del reto activo: avanza fraccionalmente con `framesCumplidos/framesMin`.
   * Para alumno: ve el anillo llenándose en vivo, no sólo dots.
   */
  progreso: number;
  /** Tono visual del anillo y el velo del óvalo según la guía de encuadre. */
  tono: OvalTono;
}

// El SVG usa una elipse con perímetro aproximado constante. La fórmula de
// Ramanujan (h = ((a-b)/(a+b))^2) es suficiente para nuestro caso.

/** Radio horizontal del clip del video (en % del viewBox 100x130). */
export const OVAL_RX = 50;
/** Radio vertical del clip del video (en % del viewBox 100x130). */
export const OVAL_RY = 65;

/**
 * C-67: El anillo de progreso va EXACTO sobre el borde del óvalo (rx=OVAL_RX,
 * ry=OVAL_RY). Antes estaba en +2 y se salía del viewBox 100×130 → se cortaba
 * en las esquinas. Sobre el borde no se recorta y coincide con el clip del video.
 */
export const PROGRESS_RX = OVAL_RX; // 50
export const PROGRESS_RY = OVAL_RY; // 65

/** C-67: Trazo fino del anillo de progreso (minimalista). */
export const PROGRESS_STROKE_WIDTH = 1.4;

/** C-67: Trazo fino del track de fondo. */
export const TRACK_STROKE_WIDTH = 1.2;

// PERIMETER usando los radios del anillo exterior (PROGRESS_RX, PROGRESS_RY)
// para que strokeDasharray/offset coincidan con el path real del progreso.
const PERIMETER = (() => {
  const a = PROGRESS_RX;
  const b = PROGRESS_RY;
  const h = ((a - b) / (a + b)) ** 2;
  return Math.PI * (a + b) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)));
})();

const STROKE_BY_TONO: Record<OvalTono, string> = {
  idle: '#cbd5e1',      // slate-300 — antes de motor listo
  ok: '#22c55e',        // C-67: green-500 — relleno tipo barra de carga durante gesto activo
  aviso: '#f59e0b',     // amber-500 — hint activo (lejos, oscuro, …)
  exito: '#22c55e',     // green-500 — éxito final
};

const TRACK_COLOR = 'rgba(15, 23, 42, 0.08)'; // slate-900 al 8%

export const CaptureOval = forwardRef<HTMLVideoElement, CaptureOvalProps>(
  function CaptureOval(
    { listoParaMostrar, enExito, motorListo, fallbackManual, progreso, tono },
    videoRef,
  ) {
    // En éxito el anillo se llena del todo y vira a verde, sin importar el estado previo.
    const tonoFinal: OvalTono = enExito ? 'exito' : tono;
    const stroke = STROKE_BY_TONO[tonoFinal];
    const progresoClamp = enExito ? 1 : Math.max(0, Math.min(1, progreso));
    const offset = PERIMETER * (1 - progresoClamp);

    return (
      <div
        className={`relative transition-all duration-500 ease-out ${
          listoParaMostrar ? 'opacity-100 scale-100' : 'opacity-0 scale-95 absolute pointer-events-none'
        }`}
        style={{ width: 'min(80vw, 300px)', filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.15))' }}
        aria-hidden={!listoParaMostrar}
      >
        {/* C-67: marco BLANCO alrededor de la cámara (contenedor que el dueño quería).
            El video va recortado a una elipse un poco más chica, dejando un anillo
            blanco entre la cámara y el borde del óvalo. */}
        <div className="relative w-full aspect-[3/4] rounded-[50%] bg-white p-[6px]">
        {/* clip-path ellipse recorta el video a la forma del óvalo */}
        <div
          className="relative w-full h-full overflow-hidden bg-neutral-100 rounded-[50%]"
          style={{ clipPath: 'ellipse(50% 50% at 50% 50%)' }}
        >
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            style={{ transform: 'scaleX(-1)' }}
            aria-label="Vista de cámara para captura biométrica"
          />

          {/* Velo de color sutil en aviso, para reforzar la guía visualmente */}
          {!enExito && tono === 'aviso' && (
            <div className="absolute inset-0 bg-amber-500/10 pointer-events-none" aria-hidden />
          )}

          {/* Éxito: tinte verde sutil + check grande + "Verificado" */}
          {enExito && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-green-500/20 animate-in fade-in duration-300">
              <Icon name="check_circle" className="text-green-500 text-[72px] drop-shadow-md" fill />
              <span className="text-sm font-semibold text-white drop-shadow-md tracking-wide">Verificado</span>
            </div>
          )}
        </div>

        {/* C-67: borde de ESTADO que LATE — va DETRÁS del anillo de progreso. Sólo
            ámbar = aviso (lejos / poca luz / etc.) y verde = éxito. El azul de "todo
            OK" se quitó: se mezclaba con el anillo verde de progreso y quedaba feo;
            cuando está todo OK el avance ya se comunica con el relleno verde del anillo.
            rounded-[50%] = elipse real (coincide con el clip del video). */}
        {!enExito && tono === 'aviso' && (
          <div className="absolute inset-0 rounded-[50%] border-2 border-amber-400 ae-oval-breathe-amber pointer-events-none" aria-hidden />
        )}
        {enExito && (
          <div className="absolute inset-0 rounded-[50%] border-2 border-green-400 pointer-events-none" aria-hidden />
        )}

        {/* Anillo de progreso — SVG superpuesto al óvalo. El stroke se llena con
            strokeDashoffset. Si motor no listo y no es fallback, mostramos un
            anillo punteado idle (sin progreso) usando strokeDasharray fijo. */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="-3 -3 106 136"
          preserveAspectRatio="none"
          aria-hidden
        >
          {/* Track de fondo — en el borde exterior del óvalo */}
          <ellipse
            cx="50"
            cy="65"
            rx={PROGRESS_RX}
            ry={PROGRESS_RY}
            fill="none"
            stroke={TRACK_COLOR}
            strokeWidth={TRACK_STROKE_WIDTH}
          />
          {/* Trazo de progreso — en el borde exterior del óvalo (C-67) */}
          {motorListo && !fallbackManual ? (
            <ellipse
              cx="50"
              cy="65"
              rx={PROGRESS_RX}
              ry={PROGRESS_RY}
              fill="none"
              stroke={stroke}
              strokeWidth={PROGRESS_STROKE_WIDTH}
              strokeLinecap="round"
              strokeDasharray={PERIMETER}
              strokeDashoffset={offset}
              style={{
                // C-67: transición corta y lineal → el llenado sigue el acumulador
                // por frame de forma FLUIDA (como llenando un vaso), sin el lag del
                // ease-out de 350ms que lo hacía trabar.
                transition: 'stroke-dashoffset 90ms linear, stroke 250ms ease-out',
              }}
            />
          ) : (
            <ellipse
              cx="50"
              cy="65"
              rx={PROGRESS_RX}
              ry={PROGRESS_RY}
              fill="none"
              stroke={fallbackManual ? '#cbd5e1' : '#cbd5e1'}
              strokeWidth={TRACK_STROKE_WIDTH}
              strokeDasharray="3 4"
            />
          )}
        </svg>
        </div>
      </div>
    );
  },
);
