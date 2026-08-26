/**
 * AvisoSinResponsable — "esto no tiene a nadie a cargo", dicho a tiempo (c-78 §18.4).
 *
 * Encontrado probando producción el 26/8/2026: se puede armar una materia, sus
 * comisiones y sus exámenes, y hacer rendir a los alumnos, sin que nada advierta
 * que no hay quién firme las notas. El write-back al campus sale con la
 * credencial del TUTOR de la comisión: sin tutor responde `sin_docente` y la
 * nota queda retenida. Eso se descubría al final, con el examen ya rendido.
 *
 * Presentación pura: recibe lo que ya se sabe y no consulta nada.
 *
 * `sinTutor` tiene TRES estados a propósito. `null` (o ausente) significa "no se
 * consultó", y ahí el componente calla: mandar a asignar un tutor que quizá ya
 * está asignado gasta la credibilidad del aviso, y un cartel que aparece siempre
 * se vuelve parte del decorado.
 */
import { Icon } from './components';

export interface AvisoSinResponsableProps {
  /** true = la comisión de este examen no tiene tutor. false = tiene. null = no se sabe. */
  sinTutor?: boolean | null;
  /** true = la materia no tiene ni profesor ni coordinador asignado. */
  sinResponsableDeMateria?: boolean;
  /** Cómo se llama lo que está sin cubrir, para nombrarlo en el aviso. */
  nombre?: string;
}

export function AvisoSinResponsable({
  sinTutor = null,
  sinResponsableDeMateria = false,
  nombre,
}: AvisoSinResponsableProps) {
  if (sinTutor !== true && !sinResponsableDeMateria) return null;

  const quien = nombre ? <strong>«{nombre}»</strong> : null;

  return (
    <div
      role="alert"
      className="flex items-start gap-sm rounded-xl bg-warning-container/60 text-on-surface
        px-md py-sm text-label-sm"
    >
      <Icon name="person_off" className="text-[18px] shrink-0 mt-0.5" />
      <div className="space-y-1">
        {sinTutor === true && (
          <p>
            {quien ? <>{quien} no tiene </> : <>No hay </>}
            <strong>tutor</strong> asignado, así que las notas de este examen{' '}
            <strong>no se van a poder devolver al campus</strong>. Asignalo en
            Administración → Materias, en el menú de la comisión.
          </p>
        )}
        {sinResponsableDeMateria && (
          <p>
            {quien ? <>{quien} no tiene </> : <>Esta materia no tiene </>}
            <strong>profesor</strong> ni <strong>coordinador</strong> asignado. Sin ellos
            nadie puede armar sus exámenes ni revisar lo que pasó durante la rendición.
          </p>
        )}
      </div>
    </div>
  );
}

export default AvisoSinResponsable;
