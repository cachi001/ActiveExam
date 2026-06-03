/**
 * EventLog — log de eventos del harness con filtro por severidad, export y
 * detalle por evento (sink, store, red, payload colapsable).
 *
 * Presentacional: recibe las entries, filtros y callbacks por props.
 */

import { Icon, Card, Button, Badge, SeverityBadge, SectionTitle } from '../../ui/components';
import { SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from '../../lib/api';
import type { Severidad, TipoEvento } from '../../lib/types';
import { LOG_MAX, type HarnessLogEntry, type HarnessState } from './types';
import { formatRelativeTs, SEVERITY_ORDER, SEVERITY_BADGE_COLORS } from './helpers';

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
  onExportLog: () => void;
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
  onExportLog,
}: EventLogProps) {
  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-md flex-wrap">
        <SectionTitle sub={
          isFilterActive
            ? `${logEntries.length} eventos (${filteredEntries.length} visibles)`
            : `${logEntries.length} evento${logEntries.length !== 1 ? 's' : ''}`
        }>
          Log de eventos
        </SectionTitle>
        <div className="flex items-center gap-sm flex-wrap">
          <Button variant="outline" size="sm" icon="download" onClick={onExportLog} className="text-label-sm">
            Exportar log
          </Button>
        </div>
      </div>

      {logTruncated && (
        <div className="flex items-center gap-base p-sm rounded-lg bg-warning-container/40 border border-warning/30 text-label-sm text-warning">
          <Icon name="warning" className="text-[16px] shrink-0" fill />
          Log truncado a {LOG_MAX} entradas. Las entradas más antiguas fueron descartadas.
        </div>
      )}

      {/* Filtro por severidad (task 8.1) */}
      <div className="flex items-center gap-base flex-wrap">
        <span className="text-label-sm text-on-surface-variant">Filtrar:</span>
        {SEVERITY_ORDER.map((sev) => (
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
            className="text-label-sm text-primary hover:underline"
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
                className={`rounded-xl border p-sm space-y-base transition-all ${
                  sev === 'alta' || sev === 'critica'
                    ? 'bg-error-container/20 border-error/30'
                    : 'bg-surface-container-low border-outline-variant/40'
                }`}
              >
                {/* Fila principal */}
                <div className="flex items-start justify-between gap-sm flex-wrap">
                  <div className="flex items-center gap-sm flex-wrap">
                    <span className="text-label-md font-semibold text-on-surface">
                      {TIPO_EVENTO_LABEL[tipo] ?? tipo}
                    </span>
                    <SeverityBadge severidad={sev} />
                    {entry.event.trigger_evidence && (
                      <Badge tone="error" dot>dispara evidencia</Badge>
                    )}
                    {entry.storeOverflow && (
                      <Badge tone="warning">store: overflow, evento anterior descartado</Badge>
                    )}
                  </div>
                  <span className="text-label-sm text-on-surface-variant font-mono">{relTs}</span>
                </div>

                {/* Indicadores de sink e inStore */}
                <div className="flex items-center gap-sm flex-wrap">
                  {entry.sinkStatus === 'ok' ? (
                    <span className="inline-flex items-center gap-base text-label-sm text-success">
                      <Icon name="check_circle" className="text-[14px]" fill /> emitido al sink
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-base text-label-sm text-error">
                      <Icon name="cancel" className="text-[14px]" fill /> error en sink: {entry.sinkError}
                    </span>
                  )}
                  {entry.inStore ? (
                    <span className="inline-flex items-center gap-base text-label-sm text-primary">
                      <Icon name="inventory_2" className="text-[14px]" fill /> en store
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
                      <Icon name="inventory_2" className="text-[14px]" /> no en store
                    </span>
                  )}
                  {/* C-46: badge de red (grabación) */}
                  {entry.networkBadge === 'ok' && (
                    <span className="inline-flex items-center gap-base text-label-sm text-success">
                      <Icon name="cloud_done" className="text-[14px]" fill />
                      grabado
                      {entry.verdictServer && (
                        <span className="text-[10px] font-mono opacity-80 ml-base">{entry.verdictServer}</span>
                      )}
                      {entry.faceCountServer != null && (
                        <span className="text-[10px] opacity-70 ml-base">srv:{entry.faceCountServer}</span>
                      )}
                    </span>
                  )}
                  {entry.networkBadge === 'net-error' && (
                    <span className="inline-flex items-center gap-base text-label-sm text-warning">
                      <Icon name="cloud_off" className="text-[14px]" />
                      ⚠ sin red
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
                      className="text-label-sm text-on-surface-variant hover:text-primary flex items-center gap-base"
                    >
                      <Icon name={isExpanded ? 'expand_less' : 'expand_more'} className="text-[16px]" />
                      payload
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
