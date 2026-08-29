/**
 * AvisoImpactoBaja — qué se lleva puesto una baja, dicho ANTES de confirmarla.
 *
 * c-78, Opción C (decisión del dueño): dar de baja algo que ya se rindió se
 * puede — la evidencia se conserva igual — pero quien lo hace tiene que saber
 * cuánta historia hay atrás. Este componente NO decide ni bloquea: muestra lo
 * que el backend ya calculó. La autoridad sigue siendo el servidor.
 *
 * Dos mensajes bien distintos, a propósito:
 *   - gente rindiendo AHORA → es un bloqueo. El DELETE va a responder 409.
 *   - rendiciones ya hechas → es un aviso. La baja se hace igual.
 *
 * Presentación pura: recibe el impacto ya consultado, no llama a ningún
 * endpoint. Quien lo usa se encarga de pedirlo (ver `impactoBajaMateria` y
 * compañía en examContentAdmin).
 */
import type { ImpactoBaja } from '../lib/examContentAdmin';

export interface AvisoImpactoBajaProps {
  impacto: ImpactoBaja | null;
  cargando: boolean;
}

function plural(n: number, singular: string, plural_: string): string {
  return `${n} ${n === 1 ? singular : plural_}`;
}

export function AvisoImpactoBaja({ impacto, cargando }: AvisoImpactoBajaProps) {
  if (cargando) {
    return (
      <p className="mt-2 text-body-sm text-on-surface-variant/80">
        Revisando qué se lleva puesto esta baja…
      </p>
    );
  }
  if (!impacto) return null;

  const { sesiones_en_curso, rendiciones, examenes, comisiones } = impacto;
  const inscriptos = impacto.inscriptos ?? 0;

  // El alcance solo se nombra cuando aporta: "alcanza a 1 comisión" al dar de
  // baja esa misma comisión no le dice nada a nadie.
  const alcance: string[] = [];
  if (comisiones > 1) alcance.push(plural(comisiones, 'comisión', 'comisiones'));
  if (examenes > 1) alcance.push(plural(examenes, 'examen', 'exámenes'));

  const hayAlgoQueDecir = sesiones_en_curso > 0 || rendiciones > 0 || inscriptos > 0;
  if (!hayAlgoQueDecir) return null;

  return (
    <>
      {sesiones_en_curso > 0 && (
        <p
          role="alert"
          className="mt-2 rounded-lg bg-error-container/60 text-on-error-container
            px-3 py-2 text-body-sm"
        >
          <strong>
            Hay {plural(sesiones_en_curso, 'alumno rindiendo', 'alumnos rindiendo')} en
            este momento.
          </strong>{' '}
          No se puede dar de baja hasta que terminen: la baja les cortaría el examen a
          mitad de camino.
        </p>
      )}

      {/* Los inscriptos AVISAN, no bloquean: la baja se hace igual y sus
          inscripciones quedan intactas. Pero son gente que mañana no va a poder
          entrar, así que quien confirma tiene que verlos antes. */}
      {inscriptos > 0 && (
        <p
          role="note"
          className="mt-2 rounded-lg bg-warning-container/50 text-on-surface
            px-3 py-2 text-body-sm"
        >
          Hay <strong>{plural(inscriptos, 'alumno inscripto', 'alumnos inscriptos')}</strong>
          {comisiones > 1 && <> en {plural(comisiones, 'comisión', 'comisiones')}</>}. Van a
          dejar de ver sus exámenes. No se borra la inscripción: vuelve al reactivar.
        </p>
      )}

      {rendiciones > 0 && (
        <p
          role="note"
          className="mt-2 rounded-lg bg-warning-container/50 text-on-surface
            px-3 py-2 text-body-sm"
        >
          Ya tiene <strong>{plural(rendiciones, 'rendición', 'rendiciones')}</strong>
          {alcance.length > 0 && <> en {alcance.join(' y ')}</>}. No se borra nada: las
          notas y la evidencia quedan consultables igual.
        </p>
      )}
    </>
  );
}

export default AvisoImpactoBaja;
