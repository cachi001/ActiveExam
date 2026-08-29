/**
 * Ventana de rendición con la que nace un examen nuevo.
 *
 * Un examen creado desde el modal nacía sin `apertura` ni `cierre`, y al alumno
 * le aparecía «Sin fecha de cierre»: un examen sin principio ni fin. El editor
 * de configuración ya las exigía (C-69), pero esa validación solo corre si
 * alguien abre esa pantalla y guarda.
 *
 * Decisión del dueño (29/8/2026): son obligatorias, o con una fecha por defecto.
 * Acá está la mitad del front — los campos llegan PRELLENADOS para que ponerlas
 * sea un clic, y el formulario no deja crear sin ellas. La otra mitad está en el
 * backend (`CrearDesdebancoRequest.completar_ventana_de_rendicion`), que las
 * completa si el body no las trae.
 *
 * Distinto del destino de Moodle (`moodle_courseid`/`moodle_cmid`), que sigue
 * siendo opcional a propósito: un examen puede cargarse a mano y no
 * sincronizarse nunca con el campus.
 */

/** Días que dura la ventana sugerida. Espeja `DIAS_VENTANA_POR_DEFECTO` del backend. */
export const DIAS_VENTANA_POR_DEFECTO = 7;

/**
 * Reloj del examen sugerido, en minutos. Espeja `MINUTOS_LIMITE_POR_DEFECTO`.
 *
 * Sin límite, la rendición vence recién en el `cierre` de la ventana: con la
 * ventana por defecto, una sesión de proctoring abierta siete días.
 */
export const MINUTOS_LIMITE_POR_DEFECTO = 60;

/**
 * Valor para un `<input type="datetime-local">`: `YYYY-MM-DDTHH:mm` en hora
 * LOCAL. Ojo: `toISOString()` devuelve UTC y correría el examen varias horas.
 */
export function aInputLocal(fecha: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return (
    `${fecha.getFullYear()}-${p(fecha.getMonth() + 1)}-${p(fecha.getDate())}` +
    `T${p(fecha.getHours())}:${p(fecha.getMinutes())}`
  );
}

/** Lo que escribe el `<input>` (hora local) convertido a ISO 8601 para la API. */
export function deInputLocalAIso(valor: string): string {
  return new Date(valor).toISOString();
}

/** Apertura sugerida: ahora, con los segundos en cero para que se lea prolijo. */
export function aperturaSugerida(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setSeconds(0, 0);
  return aInputLocal(d);
}

/** Cierre sugerido: una semana después de la apertura. */
export function cierreSugerido(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setSeconds(0, 0);
  d.setDate(d.getDate() + DIAS_VENTANA_POR_DEFECTO);
  return aInputLocal(d);
}

/**
 * Motivo por el que la ventana no sirve, o `null` si está bien.
 *
 * Se valida en el front además del backend porque acá el error se ve mientras se
 * completa el formulario, en vez de después de mandar.
 */
export function errorDeVentana(apertura: string, cierre: string): string | null {
  if (!apertura || !cierre) return 'La fecha de inicio y la de cierre son obligatorias.';
  const desde = new Date(apertura).getTime();
  const hasta = new Date(cierre).getTime();
  if (Number.isNaN(desde) || Number.isNaN(hasta)) return 'Revisá las fechas: alguna no es válida.';
  if (hasta <= desde) return 'El cierre tiene que ser posterior al inicio.';
  return null;
}
