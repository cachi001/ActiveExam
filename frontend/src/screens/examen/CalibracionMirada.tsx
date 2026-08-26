import { Icon, Card } from '../../ui/components';

/**
 * Overlay de calibración de mirada al inicio del examen (pentest 2026-08-21):
 * corre mientras `useExamProctoring` captura el baseline de gaze (ver
 * `capturarBaselineGaze` / `CALIBRACION_GAZE_MS`). Sin esto, un alumno con la
 * webcam físicamente descentrada podría dispararse "mirada desviada" solo por
 * mirar bien a la pantalla — este paso corrige eso. No cuenta contra el tiempo
 * límite del examen (corre antes de que arranque el cronómetro).
 */
export function CalibracionMirada() {
  return (
    <div className="fixed inset-0 z-[95] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in">
      <Card className="max-w-sm w-full text-center space-y-md">
        <div className="w-16 h-16 rounded-full bg-primary-container text-primary flex items-center justify-center mx-auto">
          <Icon name="visibility" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 className="font-headline text-headline-md text-on-surface">Mirá al centro de la pantalla</h3>
          <p className="text-body-md text-on-surface-variant">
            Estamos calibrando la cámara con tu posición. Quedate mirando el centro unos segundos.
          </p>
        </div>
        <Icon name="progress_activity" className="ae-spin text-primary text-[28px] mx-auto" />
      </Card>
    </div>
  );
}
