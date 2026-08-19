import { Icon, Card, SeverityBadge } from '../../ui/components';
import { pesoEvento } from '../../proctoring/scoringWeights';
import { getEffectiveConfig } from '../../config/effectiveConfigCache';
import { UMBRAL_REVISION_MIN } from '../../config/umbralRevision';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import type { EventoSesion, Severidad, Examen } from '../../lib/types';

const SEV_CARD: Record<string, string> = {
  critica: 'bg-error-container border-error/40',
  alta: 'bg-error-container border-error/40',
  media: 'bg-warning-container border-warning-200',
  baja: 'bg-blue-50 border-blue-200',
};
const SEV_ICON: Record<string, { name: string; cls: string }> = {
  critica: { name: 'gpp_bad', cls: 'text-error' },
  alta: { name: 'gpp_bad', cls: 'text-error' },
  media: { name: 'warning', cls: 'text-warning' },
  baja: { name: 'info', cls: 'text-blue-600' },
};

interface Props {
  activo: boolean;
  eventCount: number;
  score: number;
  eventos: EventoSesion[];
  examen: Examen | null;
}

/** Panel de Integridad del examen: estado de supervisión + score + últimos eventos. */
export function IntegridadPanel({ activo, eventCount, score, eventos, examen }: Props) {
  const umbral = getEffectiveConfig()?.umbral_cola_revision ?? examen?.umbral_score ?? UMBRAL_REVISION_MIN;
  const enRiesgo = score >= umbral;
  const ultimosEventos = eventos.slice(0, 4);

  return (
    <Card className="space-y-sm h-full">
      <div className="flex items-center justify-between">
        <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
          Supervisión
        </h3>
        <div className="flex items-center gap-xs">
          <span className={`w-2 h-2 rounded-full ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
          <span className={`text-label-md font-bold ${enRiesgo ? 'text-error' : 'text-on-surface'}`}>
            {score} pts
          </span>
        </div>
      </div>

      {enRiesgo && (
        <p className="text-label-xs text-error font-semibold">
          Tu sesión va a revisión de un tutor.
        </p>
      )}

      <div className="space-y-xs">
        {ultimosEventos.length === 0 ? (
          <p className="text-label-xs text-success flex items-center gap-xs">
            <Icon name="check_circle" className="text-[13px]" fill /> Sin incidencias · {eventCount} eventos
          </p>
        ) : ultimosEventos.map((ev) => {
          const card = SEV_CARD[ev.severidad] ?? SEV_CARD.baja;
          const ic = SEV_ICON[ev.severidad] ?? SEV_ICON.baja;
          const pts = pesoEvento(ev.tipo, ev.severidad as Severidad);
          return (
            <div key={ev.id} className={`flex items-center gap-xs p-xs rounded-lg border ${card}`}>
              <Icon name={ic.name} className={`${ic.cls} shrink-0 text-[14px]`} fill />
              <span className="text-label-xs text-on-surface flex-1 min-w-0 truncate">
                {TIPO_EVENTO_LABEL[ev.tipo]}
              </span>
              <div className="flex items-center gap-xs shrink-0">
                <span className="text-[10px] font-mono">+{pts}</span>
                <SeverityBadge severidad={ev.severidad} />
              </div>
            </div>
          );
        })}
        {eventos.length > 4 && (
          <p className="text-label-xs text-on-surface-variant text-right">
            +{eventos.length - 4} más
          </p>
        )}
      </div>
    </Card>
  );
}
