import { Avatar, Badge } from '../../../ui/components';
import type { SesionRevision } from '../../../lib/types';

interface ReviewQueueItemProps {
  sesion: SesionRevision;
  selected: boolean;
  onClick: () => void;
}

export function ReviewQueueItem({ sesion, selected, onClick }: ReviewQueueItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-sm rounded-xl border transition-all ${selected ? 'bg-primary-fixed/40 border-primary-container' : 'border-outline-variant/40 hover:bg-surface-container-low'}`}
    >
      <div className="flex gap-sm items-center">
        <Avatar src={sesion.foto} alt={sesion.estudiante} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-base">
            <span className="text-label-md font-semibold text-on-surface truncate">{sesion.estudiante}</span>
            <Badge tone="error">Score {sesion.score}%</Badge>
          </div>
          <p className="text-label-sm text-on-surface-variant">{sesion.examen} · {sesion.fecha}</p>
          <p className="text-label-sm text-on-surface-variant mt-base">{sesion.id} · {sesion.eventos.length} incidencias</p>
        </div>
      </div>
    </button>
  );
}
