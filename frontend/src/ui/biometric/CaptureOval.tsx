/**
 * CaptureOval — óvalo dominante con la cámara + anillo de progreso (presentacional).
 *
 * Renderiza: el contenedor del óvalo con fade-in, el clip-path ellipse que recorta
 * el <video>, la capa de éxito (animada) y un anillo SVG que se va llenando a
 * medida que el alumno completa pasos.
 *
 * El `videoRef` se reenvía (forwardRef) al elemento <video> para que el loop RAF
 * y la inicialización de cámara del padre sigan leyendo el MISMO elemento.
 *
 * C-67 (fix por feedback del dueño):
 *  - El anillo de progreso ahora va SOBRE LA BANDA BLANCA que rodea al óvalo, no
 *    pegado al borde interno del video. La banda blanca es el "track" que se llena.
 *  - Éxito: el óvalo se RELLENA de verde sólido (con animación `motion`, tipo
 *    confirmación de pedido) tapando la cámara, en vez de un velo translúcido.
 */

import { forwardRef } from 'react';
import { motion } from 'motion/react';
import { Icon } from '../components';

export type OvalTono = 'idle' | 'ok' | 'aviso' | 'exito';

export interface CaptureOvalProps {
  /** El óvalo + cámara solo se revelan cuando esto es true. */
  listoParaMostrar: boolean;
  /** Capa de éxito (relleno verde + check) y anillo verde. */
  enExito: boolean;
  /** Motor de visión listo (anillo azul scanning). */
  motorListo: boolean;
  /** Modo fallback manual (sin motor → anillo punteado). */
  fallbackManual: boolean;
  /**
   * Avance dentro de la captura (0..1):
   *  - Reto completado: salta a `(retosCompletos)/total` y NO retrocede.
   *  - Dentro del reto activo: avanza fraccionalmente mientras se sostiene el gesto.
   */
  progreso: number;
  /** Tono visual del anillo y el velo del óvalo según la guía de encuadre. */
  tono: OvalTono;
}

/**
 * Geometría del anillo (viewBox 100×130, centro 50,65).
 *
 * OVAL_RX/RY = borde EXTERNO del marco blanco (full viewBox).
 * El video se recorta con CSS `ellipse(50% 50%)` del div interno (tras el padding
 * `BAND` del marco), así que su borde queda ~BAND adentro del externo.
 * PROGRESS_RX/RY = anillo CENTRADO en la banda blanca (entre el borde del video y
 * el externo), para que se vea como que la banda blanca se rellena de color.
 */
export const OVAL_RX = 50;
export const OVAL_RY = 65;

/** Anillo de progreso: centrado en la banda blanca (un poco adentro del externo). */
export const PROGRESS_RX = 48;
export const PROGRESS_RY = 63;

/** C-67 fix: trazo más marcado para que el llenado de la banda se vea claro. */
export const PROGRESS_STROKE_WIDTH = 3;

/** Track de fondo (la banda): mismo ancho que el progreso, color tenue. */
export const TRACK_STROKE_WIDTH = 3;

// PERIMETER usando los radios del anillo (PROGRESS_RX/RY) para que
// strokeDasharray/offset coincidan con el path real del progreso (Ramanujan).
const PERIMETER = (() => {
  const a = PROGRESS_RX;
  const b = PROGRESS_RY;
  const h = ((a - b) / (a + b)) ** 2;
  return Math.PI * (a + b) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)));
})();

const STROKE_BY_TONO: Record<OvalTono, string> = {
  idle: '#cbd5e1',      // slate-300 — antes de motor listo
  ok: '#22c55e',        // green-500 — relleno tipo barra de carga durante gesto activo
  aviso: '#f59e0b',     // amber-500 — hint activo (lejos, oscuro, …)
  exito: '#22c55e',     // green-500 — éxito final
};

// Track casi imperceptible: la banda queda BLANCA (pedido del dueño); solo el
// trazo VERDE de progreso se nota al llenarse.
const TRACK_COLOR = 'rgba(15, 23, 42, 0.05)';

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
        {/* Marco BLANCO (la "banda") alrededor de la cámara. El padding define el
            ancho de la banda donde se dibuja el anillo de progreso. `p-[4%]` escala
            con el tamaño del óvalo en cualquier pantalla. */}
        <div className="relative w-full aspect-[3/4] rounded-[50%] bg-white p-[4%]">
          {/* clip-path ellipse recorta el video a la forma del óvalo interno */}
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

            {/* C-67 fix — Éxito: el óvalo se RELLENA de verde sólido (tapa la cámara)
                con una animación tipo confirmación de pedido. */}
            {enExito && (
              <motion.div
                className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-green-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                <motion.span
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.1, type: 'spring', stiffness: 300, damping: 16 }}
                >
                  <Icon name="check_circle" className="text-white text-[76px] drop-shadow-md" fill />
                </motion.span>
                <motion.span
                  className="text-base font-semibold text-white tracking-wide"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.28, duration: 0.25 }}
                >
                  Verificado
                </motion.span>
              </motion.div>
            )}
          </div>

          {/* Borde de ESTADO que LATE (ámbar = aviso). En éxito no hace falta: el
              relleno verde ya lo comunica. */}
          {!enExito && tono === 'aviso' && (
            <div className="absolute inset-0 rounded-[50%] border-2 border-amber-400 ae-oval-breathe-amber pointer-events-none" aria-hidden />
          )}

          {/* Anillo de progreso — SVG sobre la BANDA BLANCA. overflow visible para
              que el trazo no se recorte si roza el borde del viewBox. */}
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 100 130"
            preserveAspectRatio="none"
            style={{ overflow: 'visible' }}
            aria-hidden
          >
            {/* Track de fondo — sobre la banda blanca */}
            <ellipse
              cx="50"
              cy="65"
              rx={PROGRESS_RX}
              ry={PROGRESS_RY}
              fill="none"
              stroke={TRACK_COLOR}
              strokeWidth={TRACK_STROKE_WIDTH}
            />
            {/* Trazo de progreso — se llena sobre la banda blanca */}
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
                  // C-67: transición de 250ms lineal → el navegador INTERPOLA a 60fps
                  // entre las actualizaciones del acumulador, que en mobile llegan a
                  // 5-10fps. Así el llenado se ve fluido en CUALQUIER dispositivo (no
                  // depende del fps del loop de detección). 250ms bridgea los huecos
                  // de un teléfono lento sin lag perceptible en desktop.
                  transition: 'stroke-dashoffset 250ms linear, stroke 250ms ease-out',
                }}
              />
            ) : (
              <ellipse
                cx="50"
                cy="65"
                rx={PROGRESS_RX}
                ry={PROGRESS_RY}
                fill="none"
                stroke="#cbd5e1"
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
