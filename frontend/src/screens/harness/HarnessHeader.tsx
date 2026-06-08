/**
 * HarnessHeader — banner del motor, panel "¿para qué sirve?", disclaimer
 * diagnóstico, botones de inicio/detener e indicador en vivo.
 *
 * Presentacional: recibe estado y callbacks del hook por props.
 */

import { Icon, Button } from '../../ui/components';
import { Term } from '../../ui/Term';
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
  propositoPanelOpen: boolean;
  setPropositoPanelOpen: (fn: (v: boolean) => boolean) => void;
  onStart: (conSesion: boolean) => void;
  onStop: () => void;
  onRetryEngine: () => void;
}

export default function HarnessHeader({
  engineMode,
  engineError,
  isFirstEngineLoad,
  harnessState,
  modoSesion,
  eventosEnviados,
  harnessScore,
  propositoPanelOpen,
  setPropositoPanelOpen,
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
      {/* C-32 Tasks 3.1–3.4: spinner amigable, sin jerga técnica */}
      {engineMode === 'loading' && (
        <div className="flex items-start gap-sm p-md rounded-xl bg-primary-container border-2 border-primary/30 text-on-primary-container" role="status" aria-live="polite">
          <Icon name="progress_activity" className="text-[22px] shrink-0 mt-px text-primary animate-spin" />
          <div className="min-w-0">
            <p className="font-bold text-label-md">Preparando la cámara…</p>
            {/* Task 3.3: subtítulo solo en la primera carga */}
            {isFirstEngineLoad && (
              <p className="text-label-sm mt-base">
                Esto puede tardar unos segundos la primera vez.
              </p>
            )}
          </div>
        </div>
      )}
      {engineMode === 'real-active' && (
        <div className="flex items-start gap-sm p-md rounded-xl bg-success-container border-2 border-success/40 text-on-primary-container" role="status" aria-live="polite">
          <Icon name="sensors" className="text-[22px] shrink-0 mt-px text-success" fill />
          <div className="min-w-0">
            <p className="font-bold text-label-md text-success">VISIÓN REAL (MediaPipe)</p>
            <p className="text-label-sm mt-base text-on-surface-variant">
              Motor MediaPipe real activo —{' '}
              <strong>FaceDetector + FaceLandmarker + PoseLandmarker</strong> procesando frames reales de la cámara.
            </p>
          </div>
        </div>
      )}
      {engineMode === 'load-error' && (
        <div className="flex items-start gap-sm p-md rounded-xl bg-error-container border-2 border-error/50 text-on-error-container" role="alert" aria-live="assertive">
          <Icon name="error" className="text-[22px] shrink-0 mt-px text-error" fill />
          <div className="min-w-0 flex-1">
            <p className="font-bold text-label-md">ERROR AL CARGAR EL MOTOR MEDIAPIPE</p>
            <p className="text-label-sm mt-base font-mono break-all">{engineError}</p>
            <p className="text-label-sm mt-sm">
              Las señales de visión corresponden al motor de respaldo (sin MediaPipe). Verificá que ejecutaste{' '}
              <code className="bg-error/10 px-base rounded font-mono text-[11px]">scripts/download-mediapipe-models.sh</code>{' '}
              (o <code className="bg-error/10 px-base rounded font-mono text-[11px]">.ps1</code> en Windows) y que WebGL está habilitado.
            </p>
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
          PANEL DE PROPÓSITO — colapsable (DD-29-04, tasks 4.1–4.4)
      ================================================================ */}
      <div className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest overflow-hidden">
        <button
          type="button"
          onClick={() => setPropositoPanelOpen((v) => !v)}
          className="w-full flex items-center justify-between gap-sm px-md py-sm text-left hover:bg-surface-container-low transition-colors"
          aria-expanded={propositoPanelOpen}
        >
          <div className="flex items-center gap-sm">
            <Icon name="help_outline" className="text-primary text-[20px] shrink-0" />
            <span className="font-semibold text-label-md text-on-surface">¿Para qué sirve esta prueba?</span>
          </div>
          <Icon name={propositoPanelOpen ? 'expand_less' : 'expand_more'} className="text-on-surface-variant text-[20px] shrink-0" />
        </button>
        {propositoPanelOpen && (
          <div className="px-md pb-md pt-sm space-y-sm border-t border-outline-variant/40 text-label-sm text-on-surface-variant">
            <p>
              Esta herramienta verifica que el sistema detecta señales correctamente antes de un examen real.
              Al iniciar la cámara, el motor de visión (MediaPipe) procesa los frames en vivo: rostros, mirada y
              postura. Las señales del navegador (pestaña, pantalla completa, portapapeles) también son reales.
            </p>
            <div>
              <p className="font-semibold text-on-surface mb-base">Acciones sugeridas para probar:</p>
              <ul className="list-disc list-inside space-y-base ml-sm">
                <li>Moverse frente a la cámara o alejarse</li>
                <li>Tapar la cámara con la mano</li>
                <li>Cambiar de pestaña o abrir otra aplicación</li>
                <li>Copiar o pegar texto en cualquier campo</li>
                <li>Salir de la vista de pantalla completa (si aplica)</li>
              </ul>
            </div>
            <div className="flex items-start gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40">
              <Icon name="info" className="text-[16px] shrink-0 mt-px text-primary" fill />
              <span>
                <strong className="text-on-surface">Señales de visión</strong> (rostros, <Term termKey="gaze_vector">mirada</Term>, <Term termKey="pose_keypoints">cuerpo</Term>): del motor MediaPipe procesando la cámara en vivo. &nbsp;
                <strong className="text-on-surface">Señales de navegador</strong> (pestaña, pantalla completa, portapapeles): <em>reales</em>.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ================================================================
          HEADER DIAGNÓSTICO — badge prominente (task 2.1 / D-4)
      ================================================================ */}
      {/* C-30 / C-29: Advertencia de herramienta diagnóstica siempre visible (admin-detection-test-harness spec) */}
      <div className="flex items-center gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40 text-label-sm text-on-surface-variant">
        <Icon name="admin_panel_settings" className="text-[16px] shrink-0 text-primary" fill />
        <span>
          <strong className="text-on-surface">Herramienta diagnóstica admin.</strong>{' '}
          En <strong className="text-on-surface">modo test</strong> la detección corre solo localmente.
          En <strong className="text-on-surface">modo sesión</strong> los eventos se registran en el backend de proctoring para revisión —{' '}
          <em>NO es evidencia de un examen real</em>.
        </span>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-md">
        <div className="flex items-center gap-sm">
          <div className="inline-flex items-center gap-sm px-md py-sm rounded-xl bg-error-container text-on-error-container font-bold text-label-md border border-error/30">
            <Icon name="bug_report" className="text-[20px]" fill />
            MODO DIAGNÓSTICO — sin examen real
          </div>
        </div>
        <div className="flex items-center gap-sm flex-wrap">
          {harnessState === 'running' && (
            <span className="inline-flex items-center gap-base text-label-sm text-success bg-success-container px-sm py-base rounded-full font-semibold">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              Cámara activa
            </span>
          )}
          {(harnessState === 'idle' || harnessState === 'stopped') && (
            <>
              <Button icon="sensors" onClick={() => onStart(true)}>Iniciar sesión</Button>
              <Button variant="outline" icon="science" onClick={() => onStart(false)}>Probar (local)</Button>
            </>
          )}
          {harnessState === 'initializing' && (
            <Button icon="hourglass_empty" disabled>Inicializando…</Button>
          )}
          {/* Indicador en vivo — visible solo mientras la detección está corriendo */}
          {harnessState === 'running' && modoSesion && (
            <>
              <span className="inline-flex items-center gap-base text-label-sm text-on-primary bg-primary px-sm py-base rounded-full font-semibold shadow-sm">
                <span className="w-2 h-2 rounded-full bg-on-primary animate-pulse" />
                Transmitiendo en vivo · {eventosEnviados} evento{eventosEnviados !== 1 ? 's' : ''} enviado{eventosEnviados !== 1 ? 's' : ''}
              </span>
              <span
                className="inline-flex items-center gap-base text-label-sm font-bold
                  bg-surface-container-lowest text-on-surface px-sm py-base rounded-full
                  border border-outline-variant/60 shadow-sm"
                title="Score acumulado de esta sesión (igual al que persiste el backend)"
              >
                <Icon name="speed" className="text-[16px] text-primary" fill />
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
