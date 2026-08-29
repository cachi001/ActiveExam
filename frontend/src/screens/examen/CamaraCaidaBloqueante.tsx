/**
 * Tapa el examen cuando la cámara deja de estar disponible.
 *
 * El chequeo de requisitos no deja entrar sin cámara, pero una vez adentro nadie
 * miraba si seguía viva: desenchufarla dejaba al alumno rindiendo SIN supervisión
 * y sin que nada lo notara. Decisión del dueño (29/8/2026): se bloquea hasta que
 * la reconecte.
 *
 * NO finaliza el examen. Un cable flojo no es fraude, y cortar la rendición sola
 * sería una sanción automática (regla dura #5). El reloj sigue corriendo, así que
 * tampoco sirve para hacer tiempo — y eso se le dice, para que no lo intente.
 *
 * Mismo patrón que `MonitorBloqueante`, portal incluido: la pantalla del examen
 * se envuelve en `animate-in`, que crea un contexto de apilamiento y atrapa
 * adentro a cualquier `position: fixed`.
 */
import { createPortal } from 'react-dom';

import { Icon, Card } from '../../ui/components';

export function CamaraCaidaBloqueante() {
  return createPortal(
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="camara-caida-titulo"
      className="fixed inset-0 z-[100] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-lg w-full text-center space-y-md border-error/40">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name="videocam_off" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3
            id="camara-caida-titulo"
            className="font-headline text-headline-md text-on-surface"
          >
            Perdimos tu cámara
          </h3>
          <p className="text-body-md text-on-surface-variant">
            El examen se supervisa con la cámara, así que no podés seguir hasta reconectarla.
          </p>
          <p className="text-label-md text-on-surface-variant">
            Volvé a enchufarla, cerrá cualquier otra aplicación que la esté usando y revisá
            que el navegador siga teniendo permiso. Apenas vuelva, el examen sigue solo.
          </p>
          <p className="text-label-sm text-on-surface-variant/80">
            Tu examen no se perdió y tus respuestas están guardadas. El tiempo sigue
            corriendo.
          </p>
        </div>
      </Card>
    </div>,
    document.body,
  );
}

export default CamaraCaidaBloqueante;
