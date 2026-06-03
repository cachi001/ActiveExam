import { Button, Icon } from '../../../ui/components';
import type { SesionRevision } from '../../../lib/types';

interface ReviewDecisionPanelProps {
  sesion: SesionRevision;
  onResolver: (decision: SesionRevision['decision'], etiqueta: string) => void;
  onVerDetalle: () => void;
}

export function ReviewDecisionPanel({ sesion: _sesion, onResolver, onVerDetalle }: ReviewDecisionPanelProps) {
  return (
    <div className="bg-surface-container-low rounded-xl p-md space-y-md border border-outline-variant/40">
      <div>
        <h3 className="font-headline text-title-lg text-on-surface">Resolución de auditoría humana</h3>
        <p className="text-label-sm text-on-surface-variant mt-base">El software no sanciona automáticamente. Tu decisión es obligatoria y queda en el audit log inmutable.</p>
      </div>
      <div className="flex flex-col sm:flex-row gap-sm">
        <Button variant="outline" className="flex-1" icon="thumb_up" onClick={() => onResolver('descartada', 'descartada como falso positivo')}>Descartar (falso positivo)</Button>
        <Button variant="outline" className="flex-1 text-warning border-warning/40" icon="search" onClick={() => onResolver('escalada', 'escalada para investigación')}>Escalar (investigar)</Button>
        <Button variant="danger" className="flex-1" icon="gavel" onClick={() => onResolver('derivada', 'derivada a disciplina')}>Derivar a disciplina</Button>
      </div>
      <button onClick={onVerDetalle} className="text-label-md text-primary hover:underline inline-flex items-center gap-base">
        <Icon name="open_in_full" className="text-[18px]" /> Ver detalle forense completo
      </button>
    </div>
  );
}
