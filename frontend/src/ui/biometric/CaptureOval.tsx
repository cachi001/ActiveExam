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
const RX = 50; // radio horizontal en %
const RY = 65; // radio vertical en % (relativo al viewBox 100x130)
const PERIMETER = (() => {
  const a = RX;
  const b = RY;
  const h = ((a - b) / (a + b)) ** 2;
  return Math.PI * (a + b) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)));
})();

const STROKE_BY_TONO: Record<OvalTono, string> = {
  idle: '#cbd5e1',      // slate-300 — antes de motor listo
  ok: '#3b82f6',        // blue-500 — todo bien, evaluando reto
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
        {/* clip-path ellipse recorta el video a la forma del óvalo */}
        <div
          className="relative w-full aspect-[3/4] overflow-hidden bg-neutral-100"
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

        {/* Anillo de progreso — SVG superpuesto al óvalo. El stroke se llena con
            strokeDashoffset. Si motor no listo y no es fallback, mostramos un
            anillo punteado idle (sin progreso) usando strokeDasharray fijo. */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="0 0 100 130"
          preserveAspectRatio="none"
          aria-hidden
        >
          {/* Track de fondo */}
          <ellipse
            cx="50"
            cy="65"
            rx={RX - 2}
            ry={RY - 2}
            fill="none"
            stroke={TRACK_COLOR}
            strokeWidth={2.2}
          />
          {/* Trazo de progreso */}
          {motorListo && !fallbackManual ? (
            <ellipse
              cx="50"
              cy="65"
              rx={RX - 2}
              ry={RY - 2}
              fill="none"
              stroke={stroke}
              strokeWidth={2.6}
              strokeLinecap="round"
              strokeDasharray={PERIMETER}
              strokeDashoffset={offset}
              // El óvalo SVG empieza a la derecha; rotamos para arrancar arriba.
              transform="rotate(-90 50 65)"
              style={{
                transition: 'stroke-dashoffset 350ms ease-out, stroke 250ms ease-out',
              }}
            />
          ) : (
            <ellipse
              cx="50"
              cy="65"
              rx={RX - 2}
              ry={RY - 2}
              fill="none"
              stroke={fallbackManual ? '#cbd5e1' : '#cbd5e1'}
              strokeWidth={2.4}
              strokeDasharray="3 4"
            />
          )}
        </svg>
      </div>
    );
  },
);
