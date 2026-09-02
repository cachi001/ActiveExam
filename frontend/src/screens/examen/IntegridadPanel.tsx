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
  /**
   * c-78 D10 (E-02): si el alumno ve el DETALLE de los eventos de proctoring
   * mientras rinde. Default `false` — decisión del dueño.
   *
   * Cuando está apagado, el panel sigue mostrando que la supervisión está
   * activa (eso el alumno ya lo consintió y ocultarlo sería peor), pero no
   * enumera qué se detectó ni el puntaje. El control funciona igual y todo
   * queda registrado: lo único que cambia es qué se le muestra a él.
   */
  mostrarEventos?: boolean;
}

/** Panel de Integridad del examen: estado de supervisión + score + últimos eventos. */
export function IntegridadPanel({
  activo,
  eventCount,
  score,
  eventos,
  examen,
  mostrarEventos = false,
}: Props) {
  const umbral = getEffectiveConfig()?.umbral_cola_revision ?? examen?.umbral_score ?? UMBRAL_REVISION_MIN;
  const enRiesgo = score >= umbral;
  // TODOS los eventos, no los últimos: el puntaje de arriba los suma a todos, así
  // que mostrar solo un pedazo dejaba un total que no cerraba con la lista. Antes
  // cortaba en 4 y ofrecía un "+N más" que no era clickeable: el resto no había
  // forma de verlo. La lista scrollea (ver `lista-eventos-supervision`) para que
  // una sesión con muchas señales no estire la pantalla del examen.
  const eventosVisibles = mostrarEventos ? eventos : [];

  return (
    <Card className="space-y-sm h-full">
      <div className="flex items-center justify-between">
        <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
          Supervisión
        </h3>
        <div className="flex items-center gap-xs">
          <span className={`w-2 h-2 rounded-full ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
          {/* El puntaje es parte del detalle: con los eventos ocultos tampoco se
              muestra (un número subiendo sin explicación asusta más que informa). */}
          {mostrarEventos ? (
            <span className={`text-label-md font-bold ${enRiesgo ? 'text-error' : 'text-on-surface'}`}>
              {score} pts
            </span>
          ) : (
            <span className="text-label-md font-medium text-on-surface">
              {activo ? 'Activa' : 'Detenida'}
            </span>
          )}
        </div>
      </div>

      {mostrarEventos && enRiesgo && (
        <p className="text-label-xs text-error font-semibold">
          Tu sesión va a revisión de un tutor.
        </p>
      )}

      {!mostrarEventos && (
        <p className="text-label-xs text-on-surface-variant">
          El examen está siendo supervisado, tal como aceptaste al empezar. Seguí
          rindiendo con normalidad.
        </p>
      )}

      <div
        data-testid="lista-eventos-supervision"
        className="space-y-xs max-h-64 overflow-y-auto"
      >
        {!mostrarEventos ? null : eventosVisibles.length === 0 ? (
          <p className="text-label-xs text-success flex items-center gap-xs">
            <Icon name="check_circle" className="text-[13px]" fill /> Sin incidencias · {eventCount} eventos
          </p>
        ) : eventosVisibles.map((ev) => {
          const card = SEV_CARD[ev.severidad] ?? SEV_CARD.baja;
          const ic = SEV_ICON[ev.severidad] ?? SEV_ICON.baja;
          const pts = pesoEvento(ev.tipo, ev.severidad as Severidad);
          return (
            <div
              key={ev.id}
              data-testid="evento-supervision"
              className={`flex items-center gap-xs p-xs rounded-lg border ${card}`}
            >
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
      </div>
    </Card>
  );
}
