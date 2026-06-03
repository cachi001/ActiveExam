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
import { Icon, Card, Badge } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { DEFAULT_CONFIG } from '../proctoring/stateTransitionRules';
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

  const handleRestoreDefaults = () => {
    h.setConfigDraft({ ...DEFAULT_CONFIG });
    h.setConfig({ ...DEFAULT_CONFIG });
    h.setConfigErrors({});
    if (h.engineRef.current && h.sinkRef.current) {
      h.pipelineRef.current = h.createPipeline(h.engineRef.current, h.sinkRef.current, DEFAULT_CONFIG);
    }
  };

  return (
    <StaffShell nav={STAFF_NAV} title="Test de detección">
      <div className="space-y-lg animate-in fade-in duration-300">

        <HarnessHeader
          engineMode={h.engineMode}
          engineError={h.engineError}
          isFirstEngineLoad={h.isFirstEngineLoad}
          harnessState={h.harnessState}
          modoSesion={h.modoSesion}
          eventosEnviados={h.eventosEnviados}
          propositoPanelOpen={h.propositoPanelOpen}
          setPropositoPanelOpen={h.setPropositoPanelOpen}
          onStart={h.startHarness}
          onStop={h.stopHarness}
          onRetryEngine={handleRetryEngine}
        />

        {/* ================================================================
            GRID PRINCIPAL
        ================================================================ */}
        <div className="grid lg:grid-cols-3 gap-lg">

          {/* ---- Columna izquierda: cámara + señales crudas + config ---- */}
          <div className="space-y-lg">

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

            <ThresholdsConfig
              configDraft={h.configDraft}
              configErrors={h.configErrors}
              harnessState={h.harnessState}
              onConfigChange={h.applyConfigChange}
              onResetRules={h.resetRules}
              onRestoreDefaults={handleRestoreDefaults}
            />

          </div>

          {/* ---- Columna derecha (2 cols): medidor de riesgo + store counter + log de eventos + cobertura ---- */}
          <div className="lg:col-span-2 space-y-lg">

            <RiskMeter
              harnessScore={h.harnessScore}
              riskThreshold={h.riskThreshold}
              onThresholdChange={h.setRiskThreshold}
              onResetScore={() => h.setHarnessScore(0)}
            />

            {/* Contador del store (tasks 7.1, 7.2) */}
            <Card className="flex items-center justify-between gap-md flex-wrap">
              <div className="flex items-center gap-sm">
                <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                  <Icon name="storage" />
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">store.anomaliasVivo</p>
                  <p className="font-headline text-headline-md text-on-surface">
                    {h.anomaliasVivo.length} <span className="text-label-sm text-on-surface-variant font-normal">/ 50 (límite)</span>
                  </p>
                </div>
              </div>
              {h.anomaliasVivo.length >= 50 && (
                <Badge tone="warning" dot>Store lleno — overflow activo</Badge>
              )}
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
            />
          </div>
        </div>

        {/* ================================================================
            AVISO LEGAL L2.5
        ================================================================ */}
        <div className="bg-primary-fixed/40 rounded-xl p-sm text-label-sm text-on-primary-fixed-variant flex items-start gap-base">
          <Icon name="shield" className="text-[18px] shrink-0" fill />
          <span>
            Herramienta diagnóstica — sin examen real, sin sesión de alumno, sin sanción automática (la decisión es siempre humana).
            Los eventos generados aquí NO se almacenan en el backend de producción.
          </span>
        </div>
      </div>
    </StaffShell>
  );
}
