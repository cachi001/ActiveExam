import { Card, Badge, Button, Icon } from '../../../ui/components';
import type { Examen } from '../../../lib/types';

const ESTADO_EXAMEN_LABEL: Record<Examen['estado'], string> = {
  borrador: 'Borrador',
  programado: 'Programado',
  en_curso: 'En curso',
  finalizado: 'Finalizado',
};

const ESTADO_EXAMEN_TONE: Record<Examen['estado'], 'neutral' | 'primary' | 'success' | 'warning' | 'error'> = {
  borrador: 'neutral',
  programado: 'primary',
  en_curso: 'success',
  finalizado: 'neutral',
};

interface ExamenCardProps {
  examen: Examen;
  inscripto: boolean;
  inscribiendo: boolean;
  onInscribir: () => void;
}

export function ExamenCard({ examen, inscripto, inscribiendo, onInscribir }: ExamenCardProps) {
  const fecha = new Date(examen.inicio);
  const puedeInscribirse = examen.estado === 'programado' && !inscripto;

  return (
    <Card className="flex items-center gap-md">
      <div className="flex-1 min-w-0">
        <p className="text-label-md font-semibold text-on-surface">{examen.nombre}</p>
        <p className="text-label-sm text-on-surface-variant">
          {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })} · {examen.duracion_min} min
        </p>
      </div>
      <div className="flex items-center gap-sm shrink-0">
        <Badge tone={ESTADO_EXAMEN_TONE[examen.estado]} dot>
          {ESTADO_EXAMEN_LABEL[examen.estado]}
        </Badge>
        {inscripto ? (
          <Badge tone="success" dot>Inscripto</Badge>
        ) : puedeInscribirse ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onInscribir}
            disabled={inscribiendo}
          >
            {inscribiendo ? (
              <span className="inline-flex items-center gap-xs">
                <Icon name="progress_activity" className="ae-spin text-[16px]" />
                Inscribiendo…
              </span>
            ) : 'Inscribirme'}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}
