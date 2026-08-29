/**
 * Paso 3 del ingreso: calibración de la mirada.
 *
 * Antes vivía DENTRO del examen (con el cronómetro corriendo y sin mostrar cómo
 * había salido) y después dentro de la sala de espera. Decisión del dueño
 * (29/8/2026): es un paso propio del wizard, entre la verificación biométrica y
 * la sala.
 *
 * Acá el alumno todavía puede acomodar la cámara, que es justo lo que la
 * calibración necesita — el consejo de ponerla enfrente no sirve de nada una vez
 * que empezó a rendir.
 *
 * La cámara se muestra SIN espejar: el alumno tiene que ver lo mismo que ve el
 * sistema. Espejado, mover la cámara "hacia la derecha" se siente al revés.
 */
import { useRef, useState } from 'react';

import { StudentShell } from '../ui/shells';
import { Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { CalibracionPaso, type EstadoCalibracion } from './examen/CalibracionPaso';

export default function Calibracion() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null!);
  const [estado, setEstado] = useState<EstadoCalibracion>('pendiente');

  return (
    <StudentShell step={3} backTo="/biometria" ocultarNavegacion>
      <div className="max-w-2xl mx-auto space-y-lg animate-in fade-in duration-300">
        <div className="text-center space-y-base">
          <h1 className="font-headline text-headline-md text-on-surface">
            Calibración de la mirada
          </h1>
          <p className="text-body-md text-on-surface-variant">
            Un paso rápido para que el sistema sepa cómo mirás la pantalla y no confunda
            que estés leyendo con una distracción.
          </p>
        </div>

        <CalibracionPaso videoRef={videoRef} estado={estado} onEstado={setEstado} />

        {/* Mientras mide, «Continuar» NO se muestra. Antes seguía en pantalla,
            apagado y con el texto cambiado a «Calibrando…»: exactamente lo mismo
            que ya decía el botón de la tarjeta, justo arriba. Dos botones repitiendo
            el mismo cartel, uno de ellos inútil, no informan nada.

            En los demás estados sí aparece, incluso sin haber calibrado: perder
            precisión del detector es mucho menos grave que dejar a alguien trabado
            en el ingreso. */}
        {estado !== 'midiendo' && (
          <div className="flex justify-center">
            <Button icon="arrow_forward" onClick={() => navigate('/sala-espera')}>
              Continuar
            </Button>
          </div>
        )}
      </div>
    </StudentShell>
  );
}
