import { Icon, Button, Card } from '../../ui/components';
import { createPortal } from 'react-dom';

interface LockdownOverlayProps {
  onVolverAPantallaCompleta: () => void;
}

export function LockdownOverlay({ onVolverAPantallaCompleta }: LockdownOverlayProps) {
  // Portal a document.body: la pantalla del examen se envuelve en `animate-in`, que
  // crea un contexto de apilamiento y atrapa adentro a cualquier `position: fixed`.
  // Atrapado, este overlay deja de compararse con lo que hay fuera de ese contexto
  // (por ejemplo el banner de pausa, que sí va por portal) y su z-index no alcanza.
  // Conserva su z propio: los overlays del examen se apilan entre ellos.
  return createPortal(
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="lockdown-overlay-titulo"
      className="fixed inset-0 z-[95] bg-inverse-surface/90 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-sm w-full text-center space-y-md border-warning/40">
        <div className="w-14 h-14 rounded-full bg-warning-container text-warning flex items-center justify-center mx-auto">
          <Icon name="fullscreen_exit" className="text-[30px]" fill />
        </div>
        <h3 id="lockdown-overlay-titulo" className="font-headline text-headline-sm text-on-surface">
          Volvé a pantalla completa
        </h3>
        <p className="text-body-sm text-on-surface-variant">
          El examen requiere pantalla completa. Esta salida quedó registrada.
        </p>
        <Button
          icon="fullscreen"
          onClick={onVolverAPantallaCompleta}
          className="mx-auto"
        >
          Volver a pantalla completa
        </Button>
      </Card>
    </div>,
    document.body,
  );
}
