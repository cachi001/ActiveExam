/**
 * CoverageChecklist — checklist de cobertura integral de actividad sospechosa (C-25).
 *
 * Presentacional: recibe el mapa de cobertura, monitorPermission y sessionStart.
 */

import { Icon, Card, SectionTitle } from '../../ui/components';
import { SUSPICIOUS_ACTIVITY_CATALOG } from '../../proctoring/suspiciousActivityCatalog';
import type { CoverageEntry, MonitorPermission } from './types';

interface CoverageChecklistProps {
  coverage: Partial<Record<string, CoverageEntry>>;
  monitorPermission: MonitorPermission;
  sessionStart: number;
}

export default function CoverageChecklist({
  coverage,
  monitorPermission,
  sessionStart,
}: CoverageChecklistProps) {
  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-md flex-wrap">
        <SectionTitle sub="Ejercitá cada tipo en esta sesión para confirmar captura y registro">
          Cobertura integral de actividad sospechosa
        </SectionTitle>
        {(() => {
          // C-32 Task 6.5: monitorApiUnavailable reemplazado por monitorPermission === 'unsupported'
          const testableCatalog = SUSPICIOUS_ACTIVITY_CATALOG.filter(
            (e) => !(e.requiereApiOpcional && monitorPermission === 'unsupported'),
          );
          const captured = testableCatalog.filter((e) => coverage[e.tipo]);
          const allDone = testableCatalog.length > 0 && captured.length === testableCatalog.length;
          return allDone ? (
            <span className="inline-flex items-center gap-base px-md py-sm rounded-xl bg-success-container text-success font-bold text-label-md border border-success/30">
              <Icon name="verified" className="text-[18px]" fill />
              Cobertura completa
            </span>
          ) : (
            <span className="text-label-sm text-on-surface-variant font-mono">
              {captured.length}/{testableCatalog.length} tipos cubiertos
            </span>
          );
        })()}
      </div>

      <div className="space-y-base">
        {SUSPICIOUS_ACTIVITY_CATALOG.map((entry) => {
          const cap = coverage[entry.tipo];
          // C-32 Task 6.5: reemplazado por monitorPermission === 'unsupported'
          const isUntestable = entry.requiereApiOpcional && monitorPermission === 'unsupported';
          return (
            <div
              key={entry.tipo}
              className={`flex items-start justify-between gap-sm p-sm rounded-xl border text-label-sm ${
                isUntestable
                  ? 'bg-surface-container border-outline-variant/40 opacity-60'
                  : cap
                  ? 'bg-success-container/30 border-success/30'
                  : 'bg-surface-container-low border-outline-variant/40'
              }`}
            >
              <div className="flex items-start gap-sm">
                <Icon
                  name={isUntestable ? 'info' : cap ? 'check_circle' : 'radio_button_unchecked'}
                  className={`text-[18px] shrink-0 mt-px ${
                    isUntestable
                      ? 'text-on-surface-variant'
                      : cap
                      ? 'text-success'
                      : 'text-on-surface-variant'
                  }`}
                  fill={!isUntestable && !!cap}
                />
                <div className="space-y-px">
                  <div className="flex items-center gap-sm flex-wrap">
                    <span className={`font-semibold ${cap ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                      {entry.label}
                    </span>
                    <span className={`text-[10px] uppercase tracking-wide px-base py-px rounded-full font-bold ${
                      entry.categoria === 'vision'
                        ? 'bg-primary-fixed/60 text-primary'
                        : 'bg-secondary-container text-on-secondary-container'
                    }`}>
                      {entry.categoria === 'vision' ? 'Visión' : 'Navegador'}
                    </span>
                    <span className="text-[10px] text-on-surface-variant uppercase">sev: {entry.severidad}</span>
                  </div>
                  <p className="text-[11px] text-on-surface-variant">{entry.descripcion}</p>
                </div>
              </div>
              <div className="shrink-0 text-right">
                {isUntestable ? (
                  <span className="text-[10px] text-on-surface-variant italic">no testeable en este navegador</span>
                ) : cap ? (
                  <span className="text-[10px] text-success font-semibold font-mono">
                    +{((cap.capturedAt - sessionStart) / 1000).toFixed(1)}s
                  </span>
                ) : (
                  <span className="text-[10px] text-on-surface-variant">pendiente</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40 text-label-sm text-on-surface-variant">
        <Icon name="lock" className="text-[14px] shrink-0" fill />
        Modo aislado: todos los eventos de esta sesión permanecen en el dispositivo local. Ninguno se envía al backend de producción.
      </div>
    </Card>
  );
}
