/**
 * AvisoUsoCategoria — en qué exámenes se usa una categoría, dicho ANTES de
 * renombrarla o darla de baja.
 *
 * Decisión: AVISAR, NO BLOQUEAR. Renombrar o dar de baja una categoría del banco
 * no cambia ninguna nota ni saca preguntas de un examen ya armado: las preguntas
 * se copian al examen (`pregunta_examen`) y la baja de la categoría es lógica.
 * Lo único que se degrada es la trazabilidad de un examen ya rendido, que pasa a
 * mostrar el nombre nuevo o una categoría que salió del árbol.
 *
 * Presentación pura: recibe el uso ya consultado y no llama a ningún endpoint
 * (mismo contrato que `AvisoImpactoBaja`). El TEXTO del aviso lo escribe el
 * backend: es una regla del dominio y tiene que decir lo mismo en el diálogo de
 * renombrar, en el de dar de baja y en cualquier cliente de la API.
 */
import type { UsoDeCategoria } from '../lib/apiAdmin/bancoPreguntasApi';

export interface AvisoUsoCategoriaProps {
  uso: UsoDeCategoria | null;
  cargando: boolean;
  /** Mensaje si la consulta falló. Se muestra: un aviso perdido en silencio es
   *  peor que no tenerlo, porque el docente confirma creyendo que no hay nada. */
  error?: string | null;
}

export function AvisoUsoCategoria({ uso, cargando, error }: AvisoUsoCategoriaProps) {
  if (cargando) {
    return (
      <p className="mt-2 text-body-sm text-on-surface-variant/80">
        Revisando en qué exámenes se usa…
      </p>
    );
  }
  if (error) {
    return (
      <p
        role="note"
        className="mt-2 rounded-lg bg-warning-container/50 text-on-surface px-3 py-2 text-body-sm"
      >
        No se pudo comprobar en qué exámenes se usa esta categoría.
      </p>
    );
  }
  if (!uso || !uso.aviso) return null;

  return (
    <div
      role="note"
      className="mt-2 rounded-lg bg-warning-container/50 text-on-surface px-3 py-2 text-body-sm
        flex flex-col gap-1"
    >
      <p>{uso.aviso}</p>
      {uso.examenes.length > 0 && (
        <ul className="list-disc pl-5">
          {uso.examenes.map((e) => (
            <li key={e.examen_id}>
              {e.titulo}
              {e.rendido ? ' (ya rendido)' : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AvisoUsoCategoria;
