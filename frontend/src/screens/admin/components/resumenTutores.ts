import type { TutorInfo } from '../../../lib/types';

/** Etiqueta corta de la columna Tutor: cuántos hay, no quiénes son.
 *
 * Los nombres completos viven en "Ver detalle". En la fila iban concatenados y
 * con dos o tres tutores estiraban la tabla hasta forzar scroll horizontal, que
 * dejaba justamente esa columna tapada por la de Acciones. Contar ocupa un ancho
 * previsible sin importar los nombres. */
export function resumenTutores(tutores: TutorInfo[] | undefined): string {
  const cantidad = tutores?.length ?? 0;
  if (cantidad === 0) return 'Sin asignar';
  return cantidad === 1 ? '1 tutor' : `${cantidad} tutores`;
}
