import { Icon, Card } from '../../ui/components';

export function MonitorBloqueante() {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="monitor-bloqueante-titulo"
      className="fixed inset-0 z-[100] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-lg w-full text-center space-y-md border-error/40">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name="block" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 id="monitor-bloqueante-titulo" className="font-headline text-headline-md text-on-surface">
            Pantalla adicional detectada
          </h3>
          <p className="text-body-md text-on-surface-variant">
            El examen requiere <strong>un único monitor</strong>. Detectamos que tenés más de una
            pantalla conectada al equipo.
          </p>
          <p className="text-label-sm text-on-surface-variant">
            Desconectá la pantalla adicional para volver a habilitar el examen. Esta ventana se
            cerrará automáticamente cuando solo quede un monitor.
          </p>
        </div>
        <div className="inline-flex items-center gap-base px-sm py-base rounded-lg bg-warning-container text-warning text-label-sm">
          <Icon name="info" className="text-[16px]" fill />
          <span>Mientras tanto, no podés interactuar con el examen.</span>
        </div>
      </Card>
    </div>
  );
}
