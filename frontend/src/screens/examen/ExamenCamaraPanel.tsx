import type { RefObject } from 'react';

interface Props {
  /** Ref del <video> de autovigilancia. La detección lee la resolución intrínseca
   *  del stream, no el tamaño CSS. */
  videoRef: RefObject<HTMLVideoElement>;
}

/**
 * Panel de cámara del alumno — autoimagen en vivo, grande y visible, para que el
 * alumno controle su encuadre durante el examen. Sin etiqueta "En vivo": la
 * supervisión y su estado viven en el panel de Integridad.
 */
export function ExamenCamaraPanel({ videoRef }: Props) {
  return (
    <div className="space-y-sm">
      <p className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
        Tu cámara
      </p>

      <div className="relative rounded-xl overflow-hidden ring-1 ring-outline-variant/40 bg-inverse-surface aspect-video">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover"
          style={{ transform: 'scaleX(-1)' }}
        />
      </div>

      <p className="text-body-sm text-on-surface-variant leading-snug">
        Mantené tu rostro encuadrado. Solo se captura una imagen ante un evento sospechoso, no video.
      </p>
    </div>
  );
}
