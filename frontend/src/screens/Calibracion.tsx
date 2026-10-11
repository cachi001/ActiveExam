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
        {/* Solo el título. La explicación vivía acá Y adentro de la tarjeta, casi
            con las mismas palabras: en un teléfono eran seis líneas repetidas antes
            de poder hacer nada. La instrucción quedó donde está el botón. */}
        <div className="text-center">
          <h1 className="font-headline text-headline-md sm:text-headline-lg text-on-surface">
            Calibración de la mirada
          </h1>
        </div>

        <CalibracionPaso videoRef={videoRef} estado={estado} onEstado={setEstado} />

        {/* Mientras mide, «Continuar» NO se muestra. Antes seguía en pantalla,
            apagado y con el texto cambiado a «Calibrando…»: exactamente lo mismo
            que ya decía el botón de la tarjeta, justo arriba. Dos botones repitiendo
            el mismo cartel, uno de ellos inútil, no informan nada.

            En los demás estados sí aparece, incluso sin haber calibrado: perder
            precisión del detector es mucho menos grave que dejar a alguien trabado
            en el ingreso. */}
        {/* La calibración es OBLIGATORIA (decisión del dueño, 6/9/2026): sin ella
            la mirada se mide contra el centro de la CÁMARA, o sea que el sistema
            espera que el alumno mire al lente mientras rinde, y lo marca por leer.
            No se puede seguir hasta que haya medición.

            No agrega un bloqueo nuevo para quien no tiene cámara: sin cámara no se
            puede rendir de todos modos, y eso ya lo corta el chequeo de requisitos. */}
        {estado === 'lista' && (
          <div className="flex justify-center sm:justify-end">
            <Button
              icon="arrow_forward"
              onClick={() => navigate('/sala-espera')}
              className="w-full sm:w-auto"
            >
              Continuar
            </Button>
          </div>
        )}

        {(estado === 'pendiente' || estado === 'sin_camara' || estado === 'fallida') && (
          <p className="text-label-md text-on-surface-variant text-center">
            Calibrá para continuar: sin esto el sistema puede marcarte por leer.
          </p>
        )}
      </div>
    </StudentShell>
  );
}
