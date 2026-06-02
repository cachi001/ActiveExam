import { Card, Badge, Icon } from '../../../ui/components';
import type { Inscripcion } from '../../../lib/types';

const ESTADO_BADGE: Record<Inscripcion['estado'], { label: string; tone: 'neutral' | 'primary' | 'success' | 'warning' | 'error' }> = {
  inscripto: { label: 'Inscripto', tone: 'primary' },
  pendiente: { label: 'Pendiente', tone: 'warning' },
  habilitado: { label: 'Habilitado', tone: 'success' },
  rendido: { label: 'Rendido', tone: 'neutral' },
};

interface ExamenProximoCardProps {
  inscripcion: Inscripcion;
}

export function ExamenProximoCard({ inscripcion }: ExamenProximoCardProps) {
  const badge = ESTADO_BADGE[inscripcion.estado];
  const fecha = new Date(inscripcion.fecha);

  return (
    <Card className="flex items-center gap-md">
      <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name="event" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-label-md font-semibold text-on-surface truncate">{inscripcion.nombre_examen}</p>
        <p className="text-label-sm text-on-surface-variant">
          {inscripcion.nombre_materia} · {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}
        </p>
      </div>
      <Badge tone={badge.tone} dot>{badge.label}</Badge>
    </Card>
  );
}
