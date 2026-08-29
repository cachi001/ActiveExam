/**
 * Funciones puras de soporte para los dashboards de admin y alumno.
 * Exportadas separadas de los componentes para ser testeables sin DOM.
 */
import type { ExamenContenidoResumen } from '../lib/types';
import type { AsyncStatus } from '../lib/useAsyncData';

/**
 * Valor a mostrar en la stat "Exámenes" del AdminDashboard según el estado de
 * carga (C-73). Regla dura: un fetch en `error` NUNCA muestra "0" (dato fantasma)
 * — devuelve un marcador de error. `loading`/`idle` → placeholder; `ready` → la
 * cantidad real (incluye el 0 legítimo).
 */
export function statExamenesValue(status: AsyncStatus, cantidad: number): string | number {
  if (status === 'error') return '—';
  if (status === 'loading' || status === 'idle') return '…';
  return cantidad;
}

/**
 * Construye la línea de subtítulo para un ExamenContenidoResumen en el listado.
 * Prioriza materia_nombre · comision_nombre.
 *
 * `mostrarPreguntas` decide el fallback cuando no hay ni materia ni comisión, y
 * existe porque este helper lo comparten los DOS dashboards: al staff "N
 * preguntas" le sirve para detectar de un vistazo un examen vacío, pero al
 * ALUMNO no se le muestra nunca cuántas preguntas tiene el examen (decisión del
 * dueño, 28/8/2026). Sin fallback la fila queda sin subtítulo, que es preferible
 * a adelantarle el tamaño de la prueba.
 */
export function examenContenidoSubtitulo(
  e: ExamenContenidoResumen,
  { mostrarPreguntas = true }: { mostrarPreguntas?: boolean } = {},
): string {
  const partes = [e.materia_nombre, e.comision_nombre].filter(
    (s): s is string => typeof s === 'string' && s.length > 0,
  );
  if (partes.length > 0) return partes.join(' · ');
  return mostrarPreguntas ? `${e.cantidad_preguntas} preguntas` : '';
}

/** Formatea un ISO a "dd/mm HH:MM" en es-AR (corto, para chips de listado). */
function fechaCorta(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Ventana de rendición legible: "dd/mm HH:MM → dd/mm HH:MM", o "Desde …" / "Hasta …"
 * si solo hay un extremo, o "Sin ventana de fechas" si no hay ninguno.
 */
export function formatVentanaExamen(
  apertura?: string | null,
  cierre?: string | null,
): string {
  if (apertura && cierre) return `${fechaCorta(apertura)} → ${fechaCorta(cierre)}`;
  if (apertura) return `Desde ${fechaCorta(apertura)}`;
  if (cierre) return `Hasta ${fechaCorta(cierre)}`;
  return 'Sin ventana de fechas';
}

/** Duración legible del examen a partir de los minutos límite. */
export function formatDuracionExamen(min?: number | null): string {
  if (!min || min <= 0) return 'Sin límite de tiempo';
  if (min < 60) return `${min} min`;
  const horas = Math.floor(min / 60);
  const resto = min % 60;
  return resto > 0 ? `${horas} h ${resto} min` : `${horas} h`;
}
