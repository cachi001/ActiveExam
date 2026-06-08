/**
 * CaptureOverlay — chrome del overlay inmersivo de captura biométrica (presentacional).
 *
 * Owns el contenedor raíz `fixed inset-0 z-[60]` (con `containerRef` reenviado para
 * que el padre pueda pedir requestFullscreen) y compone los sub-componentes
 * presentacionales: botón Cancelar, spinner de carga, óvalo,
 * banner de fallback y sección de progreso.
 *
 * Sin lógica propia: TODO el estado, refs de cámara, loop RAF y callbacks viven en
 * BiometricCapture y se reenvían por props.
 *
 * Nuevos props (mejora UX): `progreso` (0..1) para el anillo, `tono` para el color
 * del anillo y velo del óvalo, `framingHint` y `retoActualId` para que el panel
 * inferior pueda enseñar guía contextual.
 */

import { forwardRef } from 'react';
import { Icon } from '../components';
import { CaptureLoading } from './CaptureLoading';
import { CaptureOval } from './CaptureOval';
import type { OvalTono } from './CaptureOval';
import { CaptureProgress } from './CaptureProgress';
import type { SequentialChallenge } from '../../vision/liveness';
import type { FramingHint } from './framingGuide';

export interface CaptureOverlayProps {
  videoRef: React.Ref<HTMLVideoElement>;
  listoParaMostrar: boolean;
  motorError: string | null;
  enExito: boolean;
  motorListo: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  retoActualId: SequentialChallenge | null;
  desafios: SequentialChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  getLabel: (id: SequentialChallenge) => string;
  onResolverManual: (id: string) => void;
  onCancel: () => void;
  cooldownActivo: boolean;
  retoRecienResueltoLabel: string | null;
  /** Progreso 0..1 (suma de retos completos + fracción del reto activo). */
  progreso: number;
  /** Tono del anillo del óvalo según el estado de la guía. */
  tonoOvalo: OvalTono;
  /** Hint de encuadre vigente — null si todo está OK. */
  framingHint: FramingHint | null;
}

export const CaptureOverlay = forwardRef<HTMLDivElement, CaptureOverlayProps>(
  function CaptureOverlay(props, containerRef) {
    const {
      videoRef,
      listoParaMostrar,
      motorError,
      enExito,
      motorListo,
      fallbackManual,
      retoActualLabel,
      retoActualId,
      desafios,
      resueltos,
      totalResueltos,
      totalDesafios,
      getLabel,
      onResolverManual,
      onCancel,
      cooldownActivo,
      retoRecienResueltoLabel,
      progreso,
      tonoOvalo,
      framingHint,
    } = props;

    return (
      <div
        ref={containerRef}
        className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6"
      >
        {listoParaMostrar && (
          <div className="absolute top-0 inset-x-0 flex items-center justify-end gap-3 px-5 py-4">
            <button
              onClick={onCancel}
              className="shrink-0 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
            >
              Cancelar <Icon name="close" className="text-[18px]" />
            </button>
          </div>
        )}

        {!listoParaMostrar && !motorError && <CaptureLoading />}

        <CaptureOval
          ref={videoRef}
          listoParaMostrar={listoParaMostrar}
          enExito={enExito}
          motorListo={motorListo}
          fallbackManual={fallbackManual}
          progreso={progreso}
          tono={tonoOvalo}
        />

        {fallbackManual && !enExito && (
          <div className="mt-4 w-full max-w-xs bg-amber-50 border border-amber-300 rounded-xl px-3 py-2 text-center">
            <p className="text-sm text-amber-800">
              Motor de visión no disponible — <strong>modo de prueba manual</strong>
            </p>
          </div>
        )}

        {listoParaMostrar && (
          <CaptureProgress
            enExito={enExito}
            fallbackManual={fallbackManual}
            retoActualLabel={retoActualLabel}
            retoActualId={retoActualId}
            desafios={desafios}
            resueltos={resueltos}
            totalResueltos={totalResueltos}
            totalDesafios={totalDesafios}
            getLabel={getLabel}
            onResolverManual={onResolverManual}
            cooldownActivo={cooldownActivo}
            retoRecienResueltoLabel={retoRecienResueltoLabel}
            framingHint={framingHint}
          />
        )}
      </div>
    );
  },
);
