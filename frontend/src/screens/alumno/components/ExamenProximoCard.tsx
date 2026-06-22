import { Badge, Icon } from '../../../ui/components';
import { useNavigate } from '../../../lib/router';
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
  const navigate = useNavigate();
  const badge = ESTADO_BADGE[inscripcion.estado];
  const fecha = new Date(inscripcion.fecha);

  return (
    <button
      type="button"
      onClick={() => navigate('/alumno/mis-examenes')}
      className="w-full text-left bg-white rounded-lg border border-surface-200 px-4 py-4 flex items-center gap-4 hover:border-primary/40 hover:bg-surface-50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      aria-label={`Ver detalle del examen ${inscripcion.nombre_examen}`}
    >
      <div className="w-11 h-11 rounded-lg bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name="event" className="text-[22px]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] font-semibold text-on-surface truncate leading-tight">{inscripcion.nombre_examen}</p>
        <p className="text-[13px] text-on-surface-variant leading-tight mt-1">
          {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })} · {fecha.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })} hs
        </p>
      </div>
      <Badge tone={badge.tone} dot>{badge.label}</Badge>
      <Icon name="chevron_right" className="text-[22px] text-on-surface-variant shrink-0" />
    </button>
  );
}
