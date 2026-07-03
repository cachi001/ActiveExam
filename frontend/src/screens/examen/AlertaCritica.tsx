import { Icon, Button, Card } from '../../ui/components';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import type { EventoSesion } from '../../lib/types';

interface AlertaCriticaProps {
  ev: EventoSesion;
  onClose: () => void;
}

export function AlertaCritica({ ev, onClose }: AlertaCriticaProps) {
  return (
    <div className="fixed inset-0 z-[90] bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-lg animate-in fade-in">
      <Card className="max-w-md w-full text-center space-y-md border-error/30">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name="gpp_maybe" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 className="font-headline text-headline-md text-on-surface">Atención: incidencia detectada</h3>
          <p className="text-body-md text-on-surface-variant">
            Se registró <strong>{TIPO_EVENTO_LABEL[ev.tipo]}</strong>. {ev.descripcion}
          </p>
          <p className="text-label-sm text-on-surface-variant">
            Esto quedó registrado como señal (no es una sanción). Corregí la situación para continuar con normalidad.
          </p>
        </div>
        <Button icon="check" onClick={onClose} className="mx-auto">Entendido, continuar</Button>
      </Card>
    </div>
  );
}
