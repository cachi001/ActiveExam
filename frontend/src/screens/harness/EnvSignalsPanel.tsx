/**
 * EnvSignalsPanel — señales de entorno en vivo del navegador (foco, pestaña,
 * pantalla completa, portapapeles) + flujo de permiso de monitores.
 *
 * Presentacional: recibe envSignals, harnessState, monitorPermission y el
 * callback de solicitud de permiso por props.
 */

import { Icon, Card, SectionTitle } from '../../ui/components';
import type { EnvSignals, HarnessState, MonitorPermission } from './types';

interface EnvSignalsPanelProps {
  envSignals: EnvSignals;
  harnessState: HarnessState;
  monitorPermission: MonitorPermission;
  onRequestMonitorPermission: () => void;
}

export default function EnvSignalsPanel({
  envSignals,
  harnessState,
  monitorPermission,
  onRequestMonitorPermission,
}: EnvSignalsPanelProps) {
  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-sm flex-wrap">
        <SectionTitle sub="Detectores de contexto reales del navegador">Señales de entorno</SectionTitle>
        {/* task 6.2: badge "Señal REAL" */}
        <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-success-container text-success text-label-sm font-bold border border-success/30 shrink-0">
          <Icon name="sensors" className="text-[14px]" />
          Señal REAL
        </span>
      </div>

      {harnessState !== 'running' ? (
        <div className="text-center py-md text-on-surface-variant space-y-base">
          <Icon name="sensors_off" className="text-[32px]" />
          <p className="text-label-sm">Inicia la cámara para activar los detectores de entorno.</p>
        </div>
      ) : (
        <div className="space-y-base">
          {/* Foco de ventana */}
          <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
            envSignals.focusLost
              ? 'bg-warning-container/60 border-warning/40 text-warning'
              : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
          }`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-base">
                <Icon name={envSignals.focusLost ? 'visibility_off' : 'visibility'} className="text-[16px]" />
                <span className="font-semibold">Foco de ventana</span>
              </div>
              <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno abandonó la ventana del examen.</p>
            </div>
            <span className="shrink-0 ml-sm">{envSignals.focusLost ? 'PERDIDO' : 'activo'}</span>
          </div>

          {/* Cambio de pestaña */}
          <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
            envSignals.tabChanged
              ? 'bg-warning-container/60 border-warning/40 text-warning'
              : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
          }`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-base">
                <Icon name="tab" className="text-[16px]" />
                <span className="font-semibold">Cambio de pestaña</span>
              </div>
              <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno abrió otro sitio o aplicación.</p>
            </div>
            <span className="shrink-0 ml-sm">{envSignals.tabChanged ? 'OCULTA' : 'visible'}</span>
          </div>

          {/* Pantalla completa */}
          <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
            envSignals.fullscreenExited
              ? 'bg-warning-container/60 border-warning/40 text-warning'
              : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
          }`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-base">
                <Icon name={envSignals.fullscreenExited ? 'fullscreen_exit' : 'fullscreen'} className="text-[16px]" />
                <span className="font-semibold">Pantalla completa</span>
              </div>
              <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno salió de la vista de examen completa.</p>
            </div>
            <span className="shrink-0 ml-sm">{envSignals.fullscreenExited ? 'SALIDA detectada' : 'activa o no usada'}</span>
          </div>

          {/* Clipboard */}
          <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
            envSignals.clipboardAction
              ? 'bg-error-container/60 border-error/40 text-on-error-container'
              : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
          }`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-base">
                <Icon name="content_paste" className="text-[16px]" />
                <span className="font-semibold">Portapapeles</span>
              </div>
              <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno intentó copiar o pegar contenido.</p>
            </div>
            <span className="shrink-0 ml-sm">
              {envSignals.clipboardAction
                ? `DETECTADO: ${envSignals.clipboardAction.toUpperCase()}`
                : 'sin actividad'}
            </span>
          </div>

          {/* C-32 Task 6.3: tarjeta de monitores con flujo de permiso */}
          {monitorPermission === 'unsupported' && (
            <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-surface-container-low border-outline-variant/40 text-on-surface-variant">
              <Icon name="info" className="text-[16px] shrink-0 mt-px text-primary" fill />
              <div className="min-w-0">
                <span className="font-semibold block">Monitor adicional</span>
                <p className="text-[11px] mt-px opacity-80">
                  La detección de pantallas adicionales no está disponible en este navegador.
                  Requiere Chrome o Edge sobre HTTPS.
                </p>
              </div>
            </div>
          )}

          {monitorPermission === 'idle' && (
            <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-surface-container-low border-outline-variant/40 text-on-surface-variant">
              <Icon name="monitor" className="text-[16px] shrink-0 mt-px" />
              <div className="min-w-0 flex-1">
                <span className="font-semibold block">Monitor adicional</span>
                <p className="text-[11px] mt-px opacity-80">
                  Para detectar si hay más de un monitor conectado, el navegador necesita tu permiso.
                </p>
                <button
                  type="button"
                  onClick={onRequestMonitorPermission}
                  className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-primary text-on-primary text-label-sm font-semibold hover:opacity-90 transition-opacity"
                >
                  <Icon name="monitor" className="text-[14px]" />
                  Detectar pantallas
                </button>
              </div>
            </div>
          )}

          {monitorPermission === 'requesting' && (
            <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-primary-container/40 border-primary/30 text-on-primary-container">
              <Icon name="progress_activity" className="text-[16px] shrink-0 mt-px text-primary animate-spin" />
              <div className="min-w-0">
                <span className="font-semibold block">Monitor adicional</span>
                <p className="text-[11px] mt-px opacity-80">Solicitando permiso al navegador…</p>
                <button
                  type="button"
                  disabled
                  className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-primary/50 text-on-primary text-label-sm font-semibold opacity-60 cursor-not-allowed"
                >
                  <Icon name="progress_activity" className="text-[14px] animate-spin" />
                  Detectar pantallas
                </button>
              </div>
            </div>
          )}

          {monitorPermission === 'denied' && (
            <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-warning-container/40 border-warning/40 text-warning">
              <Icon name="block" className="text-[16px] shrink-0 mt-px" />
              <div className="min-w-0 flex-1">
                <span className="font-semibold block">Monitor adicional</span>
                <p className="text-[11px] mt-px opacity-80">Permiso denegado. Podés intentarlo de nuevo.</p>
                <button
                  type="button"
                  onClick={onRequestMonitorPermission}
                  className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-warning text-white text-label-sm font-semibold hover:opacity-90 transition-opacity"
                >
                  <Icon name="refresh" className="text-[14px]" />
                  Reintentar
                </button>
              </div>
            </div>
          )}

          {monitorPermission === 'granted' && (
            <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
              envSignals.extraMonitor === true
                ? 'bg-error-container/60 border-error/40 text-on-error-container'
                : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
            }`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-base">
                  <Icon name="desktop_windows" className="text-[16px]" />
                  <span className="font-semibold">Monitor adicional</span>
                </div>
                <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si hay más de una pantalla conectada.</p>
              </div>
              <span className="shrink-0 ml-sm">
                {envSignals.extraMonitor === true
                  ? 'MONITOR ADICIONAL detectado'
                  : envSignals.extraMonitor === false
                  ? 'solo un monitor'
                  : 'determinando…'}
              </span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
