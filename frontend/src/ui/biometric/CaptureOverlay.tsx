/**
 * CaptureOverlay — chrome del overlay inmersivo de captura biométrica (presentacional).
 *
 * Owns el contenedor raíz `fixed inset-0 z-[60]` (con `containerRef` reenviado para
 * que el padre pueda pedir requestFullscreen) y compone los sub-componentes
 * presentacionales: botón Cancelar, spinner de carga, óvalo,
 * banner de fallback y sección de progreso.
 *
 * Sin lógica propia: TODO el estado, refs de cámara, loop RAF y callbacks viven en
 * BiometricCapture y se reenvían por props. El `videoRef` se pasa hasta el <video>
 * de CaptureOval para que el loop del padre lea el MISMO elemento.
 *
 * C-54: agrega props `cooldownActivo` y `retoRecienResueltoLabel`
 * para mostrar la confirmación de paso.
 * C-58 D4: se eliminaron `contextLabel` y `turnDirection` — chrome redundante.
 */

import { forwardRef } from 'react';
import { Icon } from '../components';
import { CaptureLoading } from './CaptureLoading';
import { CaptureOval } from './CaptureOval';
import { CaptureProgress } from './CaptureProgress';
import type { SequentialChallenge } from '../../vision/liveness';

export interface CaptureOverlayProps {
  /** Ref reenviado al <video> dentro de CaptureOval (loop RAF del padre). */
  videoRef: React.Ref<HTMLVideoElement>;
  listoParaMostrar: boolean;
  motorError: string | null;
  enExito: boolean;
  motorListo: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  desafios: SequentialChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  getLabel: (id: SequentialChallenge) => string;
  onResolverManual: (id: string) => void;
  onCancel: () => void;
  /** C-54: true cuando el cooldown de 350ms entre pasos está activo. */
  cooldownActivo: boolean;
  /** C-54: label del reto recién resuelto (para mostrar en cooldown). null si no hay. */
  retoRecienResueltoLabel: string | null;
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
      desafios,
      resueltos,
      totalResueltos,
      totalDesafios,
      getLabel,
      onResolverManual,
      onCancel,
      cooldownActivo,
      retoRecienResueltoLabel,
    } = props;

    return (
      // Overlay full-screen, fondo claro estilo app de banco (portal a body — escapa el stacking context del shell)
      <div
        ref={containerRef}
        className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6"
      >
        {/* Barra superior: botón Cancelar alineado a la derecha.
            Solo se muestra cuando el óvalo ya cargó (listoParaMostrar). Durante el
            spinner de carga NO hay barra ni Cancelar: pantalla limpia con el spinner
            centrado. El fallback manual entra en listoParaMostrar y conserva su barra.
            C-58 D4: se eliminó el contextLabel — era chrome redundante. */}
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
            cooldownActivo={cooldownActivo}
            retoRecienResueltoLabel={retoRecienResueltoLabel}
          />
        )}
      </div>
    );
  },
);
