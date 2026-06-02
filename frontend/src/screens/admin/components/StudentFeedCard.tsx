import { Icon, ScoreChip } from '../../../ui/components';
import type { SesionEnVivo } from '../../../lib/types';

interface StudentFeedCardProps {
  sesion: SesionEnVivo;
  umbral: number;
}

export function StudentFeedCard({ sesion, umbral }: StudentFeedCardProps) {
  return (
    <div className={`rounded-xl overflow-hidden border bg-inverse-surface relative aspect-video ${sesion.score >= umbral ? 'border-error shadow-card' : 'border-outline-variant/40'}`}>
      <img src={sesion.foto} alt={sesion.estudiante} className="w-full h-full object-cover opacity-80" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-between p-sm text-white">
        <div className="flex items-start justify-between">
          <span className="bg-black/50 backdrop-blur px-sm py-base rounded-full text-[10px] font-bold">{sesion.estudiante}</span>
          <ScoreChip score={sesion.score} umbral={umbral} />
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span className="inline-flex items-center gap-base"><Icon name="sensors" className="text-[12px]" /> {sesion.ultima_senal}</span>
          <span className="opacity-80">{sesion.legajo}</span>
        </div>
      </div>
      {sesion.estado === 'escalado' && <span className="absolute top-2 left-2 bg-error text-on-error text-[9px] font-bold px-1.5 py-0.5 rounded uppercase">Escalado</span>}
    </div>
  );
}
