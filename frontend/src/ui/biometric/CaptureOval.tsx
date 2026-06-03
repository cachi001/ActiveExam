/**
 * CaptureOval — óvalo dominante con la cámara (presentacional).
 *
 * Renderiza: el contenedor del óvalo con fade-in, el clip-path ellipse que recorta
 * el <video>, la capa de éxito (velo verde + check) y el anillo de estado.
 *
 * El `videoRef` se reenvía (forwardRef) al elemento <video> para que el loop RAF
 * y la inicialización de cámara del padre sigan leyendo el MISMO elemento. Sin
 * lógica propia: solo flags por props.
 *
 * Decisión C-36 D-3: óvalo dominante aspect-[3/4], ancho explícito para que no colapse.
 * Bug 1: invisible y sin ocupar layout mientras la cámara/motor cargan; se revela
 * (opacity + scale) cuando listoParaMostrar.
 */

import { forwardRef } from 'react';
import { Icon } from '../components';

export interface CaptureOvalProps {
  /** El óvalo + cámara solo se revelan cuando esto es true. */
  listoParaMostrar: boolean;
  /** Capa de éxito (velo verde + check) y anillo verde. */
  enExito: boolean;
  /** Motor de visión listo (anillo azul scanning). */
  motorListo: boolean;
  /** Modo fallback manual (sin motor → anillo punteado). */
  fallbackManual: boolean;
}

export const CaptureOval = forwardRef<HTMLVideoElement, CaptureOvalProps>(
  function CaptureOval({ listoParaMostrar, enExito, motorListo, fallbackManual }, videoRef) {
    return (
      // Óvalo con la cámara — ancho EXPLÍCITO para que no colapse.
      // Fade-in: invisible y sin ocupar layout mientras la cámara/motor cargan;
      // se revela (opacity + scale) cuando listoParaMostrar (Bug 1).
      <div
        className={`relative transition-all duration-500 ease-out ${
          listoParaMostrar ? 'opacity-100 scale-100' : 'opacity-0 scale-95 absolute pointer-events-none'
        }`}
        style={{ width: 'min(80vw, 300px)', filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.15))' }}
        aria-hidden={!listoParaMostrar}
      >
        {/* clip-path ellipse recorta el video a la forma del óvalo (esquinas transparentes → fondo blanco) */}
        <div
          className="relative w-full aspect-[3/4] overflow-hidden bg-neutral-100"
          style={{ clipPath: 'ellipse(50% 50% at 50% 50%)' }}
        >
          {/* Video de cámara */}
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            style={{ transform: 'scaleX(-1)' }}
            aria-label="Vista de cámara para captura biométrica"
          />

          {/* Éxito: se mantiene VISIBLE la imagen de la cámara en el óvalo (tinte
              verde translúcido, NO opaco) + check grande + "Verificado". El usuario
              ve su propia imagen en verde ~1.6s antes de que el overlay cierre. */}
          {enExito && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-green-500/20 animate-in fade-in duration-300">
              <Icon name="check_circle" className="text-green-500 text-[72px] drop-shadow-md" fill />
              <span className="text-sm font-semibold text-white drop-shadow-md tracking-wide">Verificado</span>
            </div>
          )}
        </div>

        {/* Anillo de estado del óvalo */}
        <div
          className={`absolute inset-0 rounded-[50%] border-4 pointer-events-none ${
            enExito
              ? 'border-green-500'
              : motorListo && !fallbackManual
                ? 'border-blue-500 scanning-ring'
                : 'border-dashed border-neutral-300'
          }`}
        />
      </div>
    );
  },
);
