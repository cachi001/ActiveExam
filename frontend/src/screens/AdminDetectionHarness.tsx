/**
 * AdminDetectionHarness — Herramienta DIAGNÓSTICA para administradores (C-23).
 *
 * Ruta: /admin/detection-test  (roles: admin_examenes | coordinador)
 * Acceso: protegido por el guard de roles del router; sin examen activo, sin sesión
 * de alumno, sin emisión al backend de producción.
 *
 * Reutiliza el pipeline completo de visión sin duplicar lógica:
 *   MediaPipeVisionEngine → VisionPipeline → StateTransitionRules → LocalHarnessEventSink
 *
 * RESTRICCIÓN DE AISLAMIENTO (D-4):
 * Este módulo NO instancia StudentEventChannel ni ResilientStudentEventChannel.
 * NO realiza ninguna llamada HTTP ni WebSocket al backend de producción.
 * El LocalHarnessEventSink es "air-gapped" del transporte real.
 *
 * Refactor estructural (C-23): la lógica vive en useDetectionHarness; el render
 * se compone de paneles presentacionales en ./harness.
 */

import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { DEFAULT_CONFIG } from '../proctoring/stateTransitionRules';
import { getEffectiveConfig } from '../config/effectiveConfigCache';
// C-30/C-32: loaders del motor real para el botón "Reintentar"
import { loadRealEngine, disposeRealEngine } from '../vision/harnessEngineLoader';

import { useDetectionHarness } from './harness/useDetectionHarness';
import HarnessHeader from './harness/HarnessHeader';
import CameraPanel from './harness/CameraPanel';
import VisionSignalsPanel from './harness/VisionSignalsPanel';
import EnvSignalsPanel from './harness/EnvSignalsPanel';
import ThresholdsConfig from './harness/ThresholdsConfig';
import RiskMeter from './harness/RiskMeter';
import EventLog from './harness/EventLog';
import CoverageChecklist from './harness/CoverageChecklist';

const AYUDA = (
  <HelpButton title="¿Para qué sirve esta prueba?">
    <p>
      Sirve para comprobar que el sistema detecta bien las situaciones sospechosas <strong className="text-on-surface">antes</strong> de
      usarlo en un examen real. Al encender la cámara, el sistema analiza en vivo lo que ve —tu rostro,
      hacia dónde mirás y tu postura— y lo que pasa en la pantalla: si cambiás de pestaña, si salís de
      pantalla completa o si copiás y pegás.
    </p>
    <div>
      <p className="font-semibold text-on-surface mb-2">Probá haciendo esto:</p>
      <ul className="list-disc list-inside space-y-1 ml-2">
        <li>Moverte frente a la cámara o alejarte</li>
        <li>Taparte la cara o tapar la cámara con la mano</li>
        <li>Cambiar de pestaña o abrir otra aplicación</li>
        <li>Copiar o pegar un texto</li>
        <li>Salir de la pantalla completa</li>
      </ul>
      <p className="mt-2 text-on-surface-variant">Cada acción debería aparecer como un evento en la lista de la derecha.</p>
    </div>
    <div>
      <p className="font-semibold text-on-surface mb-2">Hay dos formas de probar:</p>
      <ul className="list-disc list-inside space-y-1 ml-2">
        <li><strong className="text-on-surface">Probar (local):</strong> todo queda en este dispositivo y no se guarda nada.</li>
        <li><strong className="text-on-surface">Iniciar sesión:</strong> los eventos quedan registrados para poder revisarlos, pero sigue siendo una prueba — no es un examen real.</li>
      </ul>
    </div>
    <p className="border-t border-outline-variant/40 pt-2">
      Es una <strong className="text-on-surface">herramienta solo para administradores</strong>: no hay examen
      real ni un alumno rindiendo, y el sistema <strong className="text-on-surface">nunca sanciona por su cuenta</strong> —
      siempre decide una persona. Nada de lo que pase acá se guarda como evidencia de un examen.
    </p>
  </HelpButton>
);

export default function AdminDetectionHarness() {
  const h = useDetectionHarness();

  // C-32 Task 2.3: botón Reintentar llama disposeRealEngine() antes de re-invocar loadRealEngine()
  const handleRetryEngine = async () => {
    h.setEngineMode('loading');
    h.setEngineError(null);
    await disposeRealEngine();
    try {
      const engine = await loadRealEngine();
      h.engineRef.current = engine;
      if (h.sinkRef.current) {
        h.pipelineRef.current = h.createPipeline(engine, h.sinkRef.current, h.config);
      }
      h.setEngineMode('real-active');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      h.setEngineMode('load-error');
      h.setEngineError(msg);
    }
  };

  // Opción A: "Volver a la config del sistema" descarta los cambios de prueba y
  // restaura los umbrales VIVOS del sistema (config efectiva), no los defaults
  // hardcodeados. Si la config efectiva no cargó, cae a DEFAULT_CONFIG.
  const handleRestoreSystem = () => {
    const cfg = getEffectiveConfig();
    const thresholds = cfg
      ? {
          face_absent_ms: cfg.face_absent_ms,
          multiple_faces_frames: cfg.multiple_faces_frames,
          gaze_deviation_threshold: cfg.gaze_deviation_threshold,
          gaze_sustained_ms: cfg.gaze_sustained_ms,
          gaze_fixation_tolerance: cfg.gaze_fixation_tolerance,
        }
      : { ...DEFAULT_CONFIG };
    h.setConfigDraft(thresholds);
    h.setConfig(thresholds);
    h.setConfigErrors({});
    if (h.engineRef.current && h.sinkRef.current) {
      h.pipelineRef.current = h.createPipeline(h.engineRef.current, h.sinkRef.current, thresholds);
    }
  };

  return (
    <StaffShell nav={STAFF_NAV} title="Test de detección" subtitle="Probá el motor de detección en vivo — herramienta diagnóstica, no afecta exámenes reales ni guarda datos." help={AYUDA}>
      <div className="space-y-lg animate-in fade-in duration-300">

        {/* Aviso de importancia (una sola vez, arriba de todo): todo es de prueba, no toca la config real */}
        <Card className="flex items-start gap-sm border-l-4 border-l-warning bg-warning-container/30">
          <Icon name="info" className="text-[20px] shrink-0 mt-px text-warning" fill />
          <p className="text-label-sm text-on-surface">
            Todo lo que cambies en esta pantalla es <strong>solo para esta prueba</strong> y no modifica la configuración real. Para cambiar lo que se aplica a los exámenes, andá a <strong>Configuración</strong>.
          </p>
        </Card>

        <HarnessHeader
          engineMode={h.engineMode}
          engineError={h.engineError}
          isFirstEngineLoad={h.isFirstEngineLoad}
          harnessState={h.harnessState}
          modoSesion={h.modoSesion}
          eventosEnviados={h.eventosEnviados}
          harnessScore={h.harnessScore}
          onStart={h.startHarness}
          onStop={h.stopHarness}
          onRetryEngine={handleRetryEngine}
        />

        {/* ================================================================
            GRID PRINCIPAL
            Layout: cámara protagonista (2/3 de ancho) + panel lateral (1/3).
            Fila superior: cámara grande a la izquierda, medidor de riesgo a la derecha.
            Fila inferior: señales/config a la izquierda, log/cobertura a la derecha.
        ================================================================ */}
        <div className="grid lg:grid-cols-3 gap-lg">

          {/* ---- Cámara (2 cols) — protagonista visual ---- */}
          <div className="lg:col-span-2 space-y-lg">
            <CameraPanel
              videoRef={h.videoRef}
              engineMode={h.engineMode}
              harnessState={h.harnessState}
              rawSignals={h.rawSignals}
              showPose={h.showPose}
              setShowPose={h.setShowPose}
              showFullMesh={h.showFullMesh}
              setShowFullMesh={h.setShowFullMesh}
            />

            {/* Señales de visión y entorno debajo de la cámara */}
            <div className="grid sm:grid-cols-2 gap-lg">
              <VisionSignalsPanel
                rawSignals={h.rawSignals}
                engineMode={h.engineMode}
                harnessState={h.harnessState}
              />

              <EnvSignalsPanel
                envSignals={h.envSignals}
                harnessState={h.harnessState}
                monitorPermission={h.monitorPermission}
                onRequestMonitorPermission={h.handleRequestMonitorPermission}
              />
            </div>

            <ThresholdsConfig
              configDraft={h.configDraft}
              configErrors={h.configErrors}
              harnessState={h.harnessState}
              onConfigChange={h.applyConfigChange}
              onResetRules={h.resetRules}
              onRestoreSystem={handleRestoreSystem}
            />
          </div>

          {/* ---- Panel lateral (1 col): medidor de riesgo + leyenda + store + log + cobertura ---- */}
          <div className="space-y-lg">

            <RiskMeter
              harnessScore={h.harnessScore}
              riskThreshold={h.riskThreshold}
              onThresholdChange={h.setRiskThreshold}
              onResetScore={() => h.setHarnessScore(0)}
            />

            {/* Contador del store (tasks 7.1, 7.2) */}
            <Card className="space-y-md">
              <SectionTitle sub="Eventos recientes en memoria (máx. 50); los más viejos se descartan cuando se llena.">
                Buffer de eventos
              </SectionTitle>
              <div className="flex items-center justify-between gap-md flex-wrap">
                <div className="flex items-center gap-sm">
                  <div className="w-10 h-10 rounded-xl bg-surface-container text-on-surface-variant flex items-center justify-center shrink-0">
                    <Icon name="storage" />
                  </div>
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Eventos en memoria</p>
                    <p className="font-headline text-headline-md text-on-surface">
                      {h.anomaliasVivo.length} <span className="text-label-sm text-on-surface-variant font-normal">/ 50</span>
                    </p>
                  </div>
                </div>
                {h.anomaliasVivo.length >= 50 && (
                  <Badge tone="warning" dot>Store lleno — overflow activo</Badge>
                )}
              </div>
            </Card>

            <EventLog
              logEntries={h.logEntries}
              filteredEntries={h.filteredEntries}
              logTruncated={h.logTruncated}
              isFilterActive={h.isFilterActive}
              severityFilter={h.severityFilter}
              expandedPayloads={h.expandedPayloads}
              setExpandedPayloads={h.setExpandedPayloads}
              harnessState={h.harnessState}
              elapsed={h.elapsed}
              sessionStart={h.sessionStart}
              onToggleSeverityFilter={h.toggleSeverityFilter}
              onShowAllSeverities={h.showAllSeverities}
              onExportLog={h.exportLog}
            />

            <CoverageChecklist
              coverage={h.coverage}
              monitorPermission={h.monitorPermission}
              sessionStart={h.sessionStart}
              legendRows={h.legendRows}
              legendError={h.legendError}
            />
          </div>
        </div>

      </div>
    </StaffShell>
  );
}
