import { Icon, Card, SeverityBadge } from '../../ui/components';
import { ChatBox } from '../../ui/ChatBox';
import { PausaAlumno } from '../PausaAlumno';
import { pesoEvento } from '../../proctoring/scoringWeights';
import { getEffectiveConfig } from '../../config/effectiveConfigCache';
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
  sessionId: string | null;
  chatHabilitado: boolean;
  pausasHabilitadas: boolean;
  onActivaChange: (activa: boolean) => void;
}

export function ProctoringPanel({
  activo, eventCount, score, eventos,
  examen, sessionId, chatHabilitado, pausasHabilitadas,
  onActivaChange,
}: Props) {
  const umbral = getEffectiveConfig()?.umbral_cola_revision ?? examen?.umbral_score ?? 70;
  const enRiesgo = score >= umbral;
  const ultimosEventos = eventos.slice(-4);

  return (
    <div className="space-y-md">

      {/* Integridad */}
      <Card className="space-y-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
            Integridad
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
            Tu sesión va a revisión de un docente.
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

      {pausasHabilitadas && <PausaAlumno sessionId={sessionId} onActivaChange={onActivaChange} />}
      {chatHabilitado && (
        <ChatBox sessionId={sessionId} yo="alumno" titulo="Canal con el proctor" altura="h-[140px]" />
      )}
    </div>
  );
}
