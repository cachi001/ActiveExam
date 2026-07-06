import type { RefObject } from 'react';
import { Icon, Card } from '../../ui/components';

interface Props {
  /** Ref del <video> de autovigilancia. La detección lee la resolución intrínseca
   *  del stream, no el tamaño CSS. */
  videoRef: RefObject<HTMLVideoElement>;
  activo: boolean;
  eventCount: number;
}

/**
 * Panel de cámara del alumno — vive en el sidebar del examen (grande y visible,
 * no un PiP diminuto). Muestra la autoimagen en vivo + estado de supervisión.
 */
export function ExamenCamaraPanel({ videoRef, activo, eventCount }: Props) {
  return (
    <Card className="space-y-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
          Tu cámara
        </h3>
        <span className="inline-flex items-center gap-xs text-label-xs font-semibold text-on-surface-variant">
          <span className={`w-2 h-2 rounded-full ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
          {activo ? 'En vivo' : 'Sin señal'}
        </span>
      </div>

      <div className="relative rounded-xl overflow-hidden ring-1 ring-outline-variant/40 bg-inverse-surface aspect-video">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover"
          style={{ transform: 'scaleX(-1)' }}
        />
        <div className="absolute bottom-1.5 left-1.5 inline-flex items-center gap-xs bg-inverse-surface/70 text-inverse-on-surface text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
          <Icon name="videocam" className="text-[13px]" />
          {eventCount} {eventCount === 1 ? 'evento' : 'eventos'}
        </div>
      </div>

      <p className="text-label-xs text-on-surface-variant leading-snug">
        La imagen se analiza en tu dispositivo. Mantené tu rostro visible y centrado.
      </p>
    </Card>
  );
}
