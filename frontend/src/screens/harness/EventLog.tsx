/**
 * EventLog — log de eventos del harness con filtro por severidad, export y
 * detalle por evento (sink, store, red, payload colapsable).
 *
 * Presentacional: recibe las entries, filtros y callbacks por props.
 */

import { Icon, Card, Badge, SeverityBadge, SectionTitle } from '../../ui/components';
import { SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from '../../lib/api';
import type { Severidad, TipoEvento } from '../../lib/types';
import { LOG_MAX, type HarnessLogEntry, type HarnessState } from './types';
import { formatRelativeTs, SEVERITY_ORDER, SEVERITY_BADGE_COLORS, SEVERITY_CARD_COLORS } from './helpers';
import { formatRostrosConOrigen } from '../../lib/faceCountLabel';

interface EventLogProps {
  logEntries: HarnessLogEntry[];
  filteredEntries: HarnessLogEntry[];
  logTruncated: boolean;
  isFilterActive: boolean;
  severityFilter: Set<Severidad>;
  expandedPayloads: Set<string>;
  setExpandedPayloads: (fn: (prev: Set<string>) => Set<string>) => void;
  harnessState: HarnessState;
  elapsed: number;
  sessionStart: number;
  onToggleSeverityFilter: (sev: Severidad) => void;
  onShowAllSeverities: () => void;
  onExportLog?: () => void;
}

export default function EventLog({
  logEntries,
  filteredEntries,
  logTruncated,
  isFilterActive,
  severityFilter,
  expandedPayloads,
  setExpandedPayloads,
  harnessState,
  elapsed,
  sessionStart,
  onToggleSeverityFilter,
  onShowAllSeverities,
}: EventLogProps) {
  return (
    <Card className="space-y-md">
      <SectionTitle sub={(() => {
        // Excluir baseline del conteo visible — no aparecen en el log
        const realCount = logEntries.filter((e) => e.event.severidad !== 'baseline').length;
        return isFilterActive
          ? `${realCount} eventos (${filteredEntries.length} visibles)`
          : `${realCount} evento${realCount !== 1 ? 's' : ''}`;
      })()}>
        Log de eventos
      </SectionTitle>

      {logTruncated && (
        <div className="flex items-center gap-base p-sm rounded-lg bg-warning-container/40 border border-warning/30 text-label-sm text-warning">
          <Icon name="warning" className="text-[16px] shrink-0" fill />
          Log truncado a {LOG_MAX} entradas. Las entradas más antiguas fueron descartadas.
        </div>
      )}

      {/* Filtro por severidad (task 8.1) — excluye baseline (no aparece en log) */}
      <div className="flex items-center gap-base flex-wrap">
        <span className="text-label-sm text-on-surface-variant">Filtrar:</span>
        {SEVERITY_ORDER.filter((sev) => sev !== 'baseline').map((sev) => (
          <button
            key={sev}
            onClick={() => onToggleSeverityFilter(sev)}
            className={`px-sm py-base rounded-full text-label-sm font-semibold border transition-all ${
              severityFilter.has(sev)
                ? `${SEVERITY_BADGE_COLORS[sev]} border-transparent`
                : 'bg-surface-container text-on-surface-variant border-outline-variant/40 opacity-50'
            }`}
          >
            {SEVERIDAD_LABEL[sev]}
          </button>
        ))}
        {isFilterActive && (
          <button
            onClick={onShowAllSeverities}
            className="text-label-sm text-on-surface-variant hover:text-on-surface hover:underline"
          >
            Mostrar todos
          </button>
        )}
      </div>

      {/* Lista de eventos */}
      <div className="space-y-base max-h-[520px] overflow-y-auto">
        {filteredEntries.length === 0 ? (
          <div className="text-center py-xl text-on-surface-variant space-y-sm">
            <Icon name="check_circle" className="text-success text-[36px]" fill />
            {/* "Sin eventos aún" si han pasado más de 10s y el harness está corriendo (task 6.3) */}
            {harnessState === 'running' && elapsed >= 10 ? (
              <p className="text-label-sm">Sin eventos aún — señales dentro de umbrales</p>
            ) : (
              <p className="text-label-sm">
                {harnessState === 'idle' || harnessState === 'stopped'
                  ? 'Iniciá la cámara para comenzar el diagnóstico.'
                  : 'Esperando eventos…'}
              </p>
            )}
          </div>
        ) : (
          filteredEntries.map((entry) => {
            const relTs = formatRelativeTs(entry.event.ts_ms, sessionStart);
            const isExpanded = expandedPayloads.has(entry.id);
            const tipo = entry.event.tipo as TipoEvento;
            const sev = entry.event.severidad as Severidad;

            return (
              <div
                key={entry.id}
                className={`rounded-xl border p-sm space-y-base transition-all ${SEVERITY_CARD_COLORS[sev]}`}
              >
                {/* Fila principal */}
                <div className="flex items-start justify-between gap-sm flex-wrap">
                  <div className="flex items-center gap-sm flex-wrap">
                    <span className="text-label-md font-semibold text-on-surface">
                      {TIPO_EVENTO_LABEL[tipo] ?? tipo}
                    </span>
                    <SeverityBadge severidad={sev} />
                    {/* Puntos que este evento suma al score de riesgo — color de la severidad */}
                    <span
                      className={`inline-flex items-center gap-base text-label-sm font-bold font-mono
                        px-sm py-base rounded-full border border-transparent ${SEVERITY_BADGE_COLORS[sev]}`}
                      title="Puntos que este evento suma al score de riesgo"
                    >
                      +{entry.puntos} pts
                    </span>
                    {entry.event.trigger_evidence && (
                      <Badge tone="error" dot>genera evidencia</Badge>
                    )}
                  </div>
                  <span className="text-label-sm text-on-surface-variant font-mono">{relTs}</span>
                </div>

                {/* Estado de registro — en lenguaje claro (sin jerga interna). */}
                <div className="flex items-center gap-sm flex-wrap">
                  {entry.networkBadge === 'ok' && (
                    <span className="inline-flex items-center gap-base text-label-sm text-success">
                      <Icon name="cloud_done" className="text-[14px]" fill />
                      Guardado en el servidor
                      {entry.faceCountServer != null && (
                        <span className="text-[10px] opacity-70 ml-base">
                          ({formatRostrosConOrigen('servidor', entry.faceCountServer)})
                        </span>
                      )}
                    </span>
                  )}
                  {entry.networkBadge === 'net-error' && (
                    <span className="inline-flex items-center gap-base text-label-sm text-warning">
                      <Icon name="cloud_off" className="text-[14px]" />
                      No se pudo guardar (sin conexión)
                    </span>
                  )}
                  {entry.networkBadge === undefined && (
                    <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
                      <Icon name="science" className="text-[14px]" />
                      Prueba local — no se guarda
                    </span>
                  )}
                </div>

                {/* Payload colapsable */}
                {Object.keys(entry.event.payload).length > 0 && (
                  <div>
                    <button
                      onClick={() =>
                        setExpandedPayloads((prev) => {
                          const next = new Set(prev);
                          if (next.has(entry.id)) { next.delete(entry.id); } else { next.add(entry.id); }
                          return next;
                        })
                      }
                      className="text-label-sm text-on-surface-variant hover:text-on-surface flex items-center gap-base"
                    >
                      <Icon name={isExpanded ? 'expand_less' : 'expand_more'} className="text-[16px]" />
                      {isExpanded ? 'Ocultar detalle técnico' : 'Ver detalle técnico'}
                    </button>
                    {isExpanded && (
                      <pre className="mt-base text-label-sm font-mono bg-surface-container rounded-lg p-sm overflow-x-auto text-on-surface-variant">
                        {JSON.stringify(entry.event.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
