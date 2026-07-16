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
        <Button variant="outline" className="flex-1" icon="thumb_up" onClick={() => onResolver('sin_hallazgos', 'sin hallazgos (falso positivo)')}>Sin observaciones</Button>
        <Button variant="secondary" className="flex-1" icon="verified" onClick={() => onResolver('aprobado', 'aprobado con nota')}>Aprobar con nota</Button>
        <Button variant="danger" className="flex-1" icon="gavel" onClick={() => onResolver('caso_abierto', 'caso abierto (derivar)')}>Abrir caso (derivar)</Button>
      </div>
      <button onClick={onVerDetalle} className="text-label-md text-on-surface-variant hover:text-on-surface inline-flex items-center gap-base transition-colors">
        <Icon name="open_in_full" className="text-[18px]" /> Ver detalle forense completo
      </button>
    </div>
  );
}
