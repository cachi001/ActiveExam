import { Icon, Card } from '../../ui/components';
import { createPortal } from 'react-dom';

/**
 * Overlay de calibración de mirada al inicio del examen (pentest 2026-08-21):
 * corre mientras `useExamProctoring` captura el baseline de gaze (ver
 * `capturarBaselineGaze` / `CALIBRACION_GAZE_MS`). Sin esto, un alumno con la
 * webcam físicamente descentrada podría dispararse "mirada desviada" solo por
 * mirar bien a la pantalla — este paso corrige eso. No cuenta contra el tiempo
 * límite del examen (corre antes de que arranque el cronómetro).
 */
export function CalibracionMirada() {
  // Portal a document.body: la pantalla del examen se envuelve en `animate-in`, que
  // crea un contexto de apilamiento y atrapa adentro a cualquier `position: fixed`.
  // Atrapado, este overlay deja de compararse con lo que hay fuera de ese contexto
  // (por ejemplo el banner de pausa, que sí va por portal) y su z-index no alcanza.
  // Conserva su z propio: los overlays del examen se apilan entre ellos.
  return createPortal(
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
          {/* La postura durante ESTOS segundos define el punto contra el que se
              mide toda la rendición. Calibrar de perfil, o con la cámara apuntando
              desde un costado, fija un baseline torcido: después el alumno mira
              bien el examen y el sistema lo lee como mirada desviada. Decirlo acá
              es lo que evita ese falso positivo. */}
          <p className="text-label-md text-on-surface-variant">
            Poné la cámara <strong className="text-on-surface">enfrente tuyo</strong>, no a un
            costado, y sentate de frente a la pantalla. Si no, el sistema puede marcarte
            mirada desviada mientras rendís normalmente.
          </p>
        </div>
        <Icon name="progress_activity" className="ae-spin text-primary text-[28px] mx-auto" />
      </Card>
    </div>,
    document.body,
  );
}
