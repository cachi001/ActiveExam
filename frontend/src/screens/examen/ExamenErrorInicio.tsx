import { Icon, Card, Button } from '../../ui/components';
import type { SessionInitError } from '../../proctoring/useExamProctoring';

/**
 * Overlay BLOQUEANTE cuando NO se pudo iniciar la sesión de examen.
 *
 * Sin sesión de proctoring, rendir es imposible de forma segura: las respuestas
 * no se guardan server-side y la nota nunca se calcula. Antes el alumno entraba
 * igual a un examen "fantasma" (chat deshabilitado, pausas mudas, entrega en el
 * vacío). Este overlay corta ese camino: explica el motivo en lenguaje claro y
 * ofrece salir (o reintentar si el fallo es de red, no una regla de negocio).
 */
export function ExamenErrorInicio({
  error,
  onVolver,
  onReintentar,
}: {
  error: SessionInitError;
  onVolver: () => void;
  onReintentar?: () => void;
}) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="examen-error-inicio-titulo"
      className="fixed inset-0 z-[100] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-lg w-full text-center space-y-md border-error/40">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name={error.reintentable ? 'wifi_off' : 'block'} className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 id="examen-error-inicio-titulo" className="font-headline text-headline-md text-on-surface">
            {error.titulo}
          </h3>
          <p className="text-body-md text-on-surface-variant">{error.mensaje}</p>
          <p className="text-label-sm text-on-surface-variant">
            No podés rendir sin una sesión de supervisión activa: tus respuestas no se
            guardarían. No perdiste ningún intento por este error.
          </p>
        </div>
        <div className="flex items-center justify-center gap-base flex-wrap">
          {error.reintentable && onReintentar && (
            <Button icon="refresh" onClick={onReintentar}>
              Reintentar
            </Button>
          )}
          <Button variant="outline" icon="arrow_back" onClick={onVolver}>
            Volver a Mis exámenes
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default ExamenErrorInicio;
