/**
 * Funciones puras de soporte para los dashboards de admin y alumno.
 * Exportadas separadas de los componentes para ser testeables sin DOM.
 */
import type { ExamenContenidoResumen } from '../lib/types';

/**
 * Construye la línea de subtítulo para un ExamenContenidoResumen en el listado.
 * Prioriza materia_nombre · comision_nombre; si ninguno está disponible cae a
 * "N preguntas" para que la fila siempre tenga contexto.
 */
export function examenContenidoSubtitulo(e: ExamenContenidoResumen): string {
  const partes = [e.materia_nombre, e.comision_nombre].filter(
    (s): s is string => typeof s === 'string' && s.length > 0,
  );
  if (partes.length > 0) return partes.join(' · ');
  return `${e.cantidad_preguntas} preguntas`;
}
