/**
 * CaptureOverlay — chrome del overlay inmersivo de captura biométrica (presentacional).
 *
 * Owns el contenedor raíz `fixed inset-0 z-[60]` (con `containerRef` reenviado para
 * que el padre pueda pedir requestFullscreen) y compone los sub-componentes
 * presentacionales: botón Cancelar, etiqueta contextual, spinner de carga, óvalo,
 * banner de fallback y sección de progreso.
 *
 * Sin lógica propia: TODO el estado, refs de cámara, loop RAF y callbacks viven en
 * BiometricCapture y se reenvían por props. El `videoRef` se pasa hasta el <video>
 * de CaptureOval para que el loop del padre lea el MISMO elemento.
 */

import { forwardRef } from 'react';
import { Icon } from '../components';
import { CaptureLoading } from './CaptureLoading';
import { CaptureOval } from './CaptureOval';
import { CaptureProgress } from './CaptureProgress';
import type { ActiveChallenge } from '../../vision/liveness';

export interface CaptureOverlayProps {
  /** Ref reenviado al <video> dentro de CaptureOval (loop RAF del padre). */
  videoRef: React.Ref<HTMLVideoElement>;
  contextLabel?: string;
  listoParaMostrar: boolean;
  motorError: string | null;
  enExito: boolean;
  motorListo: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  desafios: ActiveChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  getLabel: (id: ActiveChallenge) => string;
  onResolverManual: (id: string) => void;
  onCancel: () => void;
}

export const CaptureOverlay = forwardRef<HTMLDivElement, CaptureOverlayProps>(
  function CaptureOverlay(props, containerRef) {
    const {
      videoRef,
      contextLabel,
      listoParaMostrar,
      motorError,
      enExito,
      motorListo,
      fallbackManual,
      retoActualLabel,
      desafios,
      resueltos,
      totalResueltos,
      totalDesafios,
      getLabel,
      onResolverManual,
      onCancel,
    } = props;

    return (
      // Overlay full-screen, fondo claro estilo app de banco (portal a body — escapa el stacking context del shell)
      <div
        ref={containerRef}
        className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6"
      >
        {/* Cancelar — discreto, arriba a la derecha */}
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
        >
          Cancelar <Icon name="close" className="text-[18px]" />
        </button>

        {/* Etiqueta contextual opcional — oculta durante la carga para no competir con el spinner */}
        {contextLabel && listoParaMostrar && (
          <p className="text-sm text-neutral-500 mb-6 text-center max-w-xs">{contextLabel}</p>
        )}

        {/* Bug 1: estado de carga LIMPIO — solo un spinner centrado, sin óvalo,
            sin frame de cámara, sin jerga técnica. El <video> sigue montado abajo
            (opacity-0) para que el stream se inicialice, pero no se ve. */}
        {!listoParaMostrar && !motorError && <CaptureLoading />}

        {/* Óvalo con la cámara — el videoRef se reenvía para que el loop RAF y la
            inicialización de cámara sigan leyendo el MISMO elemento <video>. */}
        <CaptureOval
          ref={videoRef}
          listoParaMostrar={listoParaMostrar}
          enExito={enExito}
          motorListo={motorListo}
          fallbackManual={fallbackManual}
        />

        {/* Banner de fallback manual */}
        {fallbackManual && !enExito && (
          <div className="mt-4 w-full max-w-xs bg-amber-50 border border-amber-300 rounded-xl px-3 py-2 text-center">
            <p className="text-sm text-amber-800">
              Motor de visión no disponible — <strong>modo de prueba manual</strong>
            </p>
          </div>
        )}

        {/* Sección inferior — paso actual + progreso. Oculta durante la carga. */}
        {listoParaMostrar && (
          <CaptureProgress
            enExito={enExito}
            fallbackManual={fallbackManual}
            retoActualLabel={retoActualLabel}
            desafios={desafios}
            resueltos={resueltos}
            totalResueltos={totalResueltos}
            totalDesafios={totalDesafios}
            getLabel={getLabel}
            onResolverManual={onResolverManual}
          />
        )}
      </div>
    );
  },
);
