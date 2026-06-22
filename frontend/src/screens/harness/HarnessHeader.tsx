/**
 * HarnessHeader — banner del motor + botones de inicio/detener e indicador en vivo.
 *
 * Presentacional: recibe estado y callbacks del hook por props.
 * El acordeón "¿Para qué sirve?" y el banner diagnóstico fueron movidos al
 * modal HelpButton en AdminDetectionHarness (punto 4).
 */

import { Icon, Button } from '../../ui/components';
import type { EngineMode, HarnessState } from './types';

interface HarnessHeaderProps {
  engineMode: EngineMode;
  engineError: string | null;
  isFirstEngineLoad: boolean;
  harnessState: HarnessState;
  modoSesion: boolean;
  eventosEnviados: number;
  /** Score acumulado en vivo (0..100). Se muestra junto al indicador en sesión. */
  harnessScore: number;
  onStart: (conSesion: boolean) => void;
  onStop: () => void;
  onRetryEngine: () => void;
}

export default function HarnessHeader({
  engineMode,
  engineError,
  harnessState,
  modoSesion,
  eventosEnviados,
  harnessScore,
  onStart,
  onStop,
  onRetryEngine,
}: HarnessHeaderProps) {
  return (
    <>
      {/* ================================================================
          C-30: BANNER CONDICIONAL DEL MOTOR — 4 estados (D-5, harness-legibility-layer)
      ================================================================ */}
      {/* Estado 'simulated' (idle): sin banner — al iniciar la cámara se activa el motor real (MediaPipe). */}
      {/* El estado "preparando" se muestra con UN solo spinner, dentro del panel de
          cámara (CameraPanel). No repetimos un banner con spinner acá. */}
      {engineMode === 'real-active' && (
        <div className="flex items-start gap-sm p-md rounded-xl bg-success-container border-2 border-success/40 text-on-surface" role="status" aria-live="polite">
          <Icon name="sensors" className="text-[22px] shrink-0 mt-px text-success" fill />
          <div className="min-w-0">
            <p className="font-bold text-label-md text-success">Cámara analizando en vivo</p>
            <p className="text-label-sm mt-base text-on-surface-variant">
              El sistema está analizando en tiempo real lo que ve la cámara: tu rostro, hacia dónde mirás y tu postura.
            </p>
          </div>
        </div>
      )}
      {engineMode === 'load-error' && (
        <div className="flex items-start gap-sm p-md rounded-xl bg-error-container border-2 border-error/50 text-on-error-container" role="alert" aria-live="assertive">
          <Icon name="error" className="text-[22px] shrink-0 mt-px text-error" fill />
          <div className="min-w-0 flex-1">
            <p className="font-bold text-label-md">No se pudo iniciar el análisis de la cámara</p>
            <p className="text-label-sm mt-sm">
              Probá tocar “Reintentar” o recargar la página. Si el problema continúa, contactá al equipo de soporte.
            </p>
            <p className="text-label-sm mt-base font-mono break-all text-on-error-container/70">{engineError}</p>
            {/* C-32 Task 2.3: botón Reintentar llama disposeRealEngine() antes de re-invocar loadRealEngine() */}
            {harnessState === 'running' && (
              <button
                type="button"
                className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-error text-on-error text-label-sm font-semibold hover:opacity-90 transition-opacity"
                onClick={onRetryEngine}
              >
                <Icon name="refresh" className="text-[16px]" />
                Reintentar
              </button>
            )}
          </div>
        </div>
      )}

      {/* ================================================================
          BOTONES DE ACCIÓN + INDICADORES EN VIVO
          Mobile: flex-col centrado; Desktop: justify-end alineado a la derecha.
      ================================================================ */}
      <div className="flex items-center justify-center sm:justify-start flex-wrap gap-md">
        <div className="flex flex-col sm:flex-row items-center gap-sm flex-wrap w-full sm:w-auto">
          {(harnessState === 'idle' || harnessState === 'stopped') && (
            <div className="grid grid-cols-2 gap-sm w-full sm:w-auto">
              <Button variant="primary" icon="videocam" onClick={() => onStart(true)} className="justify-center sm:min-w-[160px]">
                Grabar sesión
              </Button>
              <Button variant="secondary" icon="science" onClick={() => onStart(false)} className="justify-center sm:min-w-[160px]">
                Test Local
              </Button>
            </div>
          )}
          {harnessState === 'initializing' && (
            <Button disabled>Inicializando…</Button>
          )}
          {/* Indicador en vivo — visible solo mientras la detección está corriendo */}
          {harnessState === 'running' && modoSesion && (
            <>
              <span className="inline-flex items-center gap-base text-label-sm text-on-surface bg-surface-container-high px-sm py-base rounded-full font-semibold shadow-sm border border-outline-variant/60">
                <span className="w-2 h-2 rounded-full bg-on-surface-variant animate-pulse" />
                Transmitiendo en vivo · {eventosEnviados} evento{eventosEnviados !== 1 ? 's' : ''} enviado{eventosEnviados !== 1 ? 's' : ''}
              </span>
              <span
                className="inline-flex items-center gap-base text-label-sm font-bold
                  bg-surface-container-lowest text-on-surface px-sm py-base rounded-full
                  border border-outline-variant/60 shadow-sm"
                title="Puntaje de riesgo acumulado en esta prueba"
              >
                <Icon name="speed" className="text-[16px] text-on-surface-variant" fill />
                Score {harnessScore}
              </span>
            </>
          )}
          {harnessState === 'running' && !modoSesion && (
            <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant bg-surface-container px-sm py-base rounded-full font-semibold border border-outline-variant/40">
              <span className="w-2 h-2 rounded-full bg-on-surface-variant animate-pulse" />
              Modo test (local, sin registro)
            </span>
          )}
          {harnessState === 'running' && (
            <Button variant="danger" icon="stop_circle" onClick={onStop}>Detener</Button>
          )}
        </div>
      </div>
    </>
  );
}
