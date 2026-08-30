// Lógica pura del gate de "Rendir" para exámenes importados (C-69).
// Extraída de AlumnoMisExamenes para poder testearla sin renderizar el componente
// (misma convención que ExamenLogic.ts).

import type { ExamenContenidoResumen, NotaExamen } from '../../lib/types';

export interface GateImportado {
  habilitado: boolean;
  motivo?: string;
  /** Intentos ya rendidos (sesiones finalizadas con nota) de ESTE examen. */
  usados: number;
  /** Intentos permitidos por el examen; null = sin límite configurado. */
  permitidos: number | null;
}

/** Formatea un ISO 8601 a fecha+hora legible (es-AR). */
export function formatFechaHora(iso: string): string {
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
      // 24 horas, igual que el resto de la tarjeta: es-AR devuelve "10:49 p. m."
      // con espacio duro, y la misma fecha aparecía en dos formatos distintos en
      // renglones consecutivos.
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/** Fecha y hora para la card: "29-ago-2026, 18:19 hs".
 *
 *  CON año: sin él, un examen del año pasado se lee igual que uno de esta semana,
 *  y las materias se repiten todos los años.
 *
 *  CON "hs": "18:19" suelto al lado de una fecha se lee como cualquier cosa. El
 *  sufijo es lo que lo vuelve una hora a simple vista.
 *
 *  Sin "p. m.": es-AR mete un espacio duro en el sufijo y en 12px parece un error
 *  de la pantalla. */
function fechaCorta(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const fecha = new Intl.DateTimeFormat('es-AR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(d);
  const hora = new Intl.DateTimeFormat('es-AR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
  return `${fecha}, ${hora} hs`;
}

/**
 * Las dos fechas POR SEPARADO, para que la card las etiquete una por una.
 *
 * `textoVentana` las devolvía en una sola frase corrida ("Del X al Y") y la de
 * cierre se perdía adentro: quien mira la card busca dos datos distintos, cuándo
 * abre y cuándo cierra, no una oración.
 */
export function ventanaPartes(
  apertura?: string | null,
  cierre?: string | null,
): { desde: string | null; hasta: string | null } {
  return {
    desde: apertura ? fechaCorta(apertura) : null,
    hasta: cierre ? fechaCorta(cierre) : null,
  };
}

/**
 * Ventana de rendición para mostrar EN LA CARD, antes de entrar a la ficha.
 *
 * El gate de abajo ya nombra la fecha, pero solo cuando BLOQUEA ("Disponible
 * desde…", "Cerrado el…"). Mientras el examen está disponible el alumno no
 * tenía cómo saber hasta cuándo sin abrir el examen. Devuelve `null` cuando no
 * hay fechas (o son ilegibles): sin ventana configurada no hay nada que decir,
 * y una card no puede romperse por un dato mal formado.
 */
export function textoVentana(
  apertura?: string | null,
  cierre?: string | null,
): string | null {
  const desde = apertura ? fechaCorta(apertura) : null;
  const hasta = cierre ? fechaCorta(cierre) : null;
  // "Desde X · Hasta Y" y no "Del X al Y": el alumno busca las dos fechas por
  // separado (cuándo abre y cuándo cierra), y en el formato corrido se leían como
  // una sola frase donde la de cierre pasaba desapercibida.
  if (desde && hasta) return `Desde ${desde} · Hasta ${hasta}`;
  if (hasta) return `Hasta ${hasta}`;
  if (desde) return `Desde ${desde}`;
  return null;
}

/**
 * Gate de "Rendir" para un examen importado (C-69 config):
 * 1. Ventana: antes de `apertura` → "Disponible desde…"; después de `cierre` → "Cerrado el…".
 * 2. Intentos: si el alumno ya rindió `intentos_permitidos` veces (contando ítems de
 *    `misNotas()` de ese examen — una fila POR sesión finalizada) → bloqueado.
 *
 * Devuelve SIEMPRE `usados`/`permitidos` (incluso cuando está habilitado) para que la
 * card pueda mostrar "te queda N de M" antes de agotar los intentos.
 * Función pura (acepta `ahora` inyectable) para poder testearla sin reloj real.
 */
export function gateExamenImportado(
  contenido: ExamenContenidoResumen,
  notas: NotaExamen[],
  ahora: number = Date.now(),
): GateImportado {
  const permitidos = contenido.intentos_permitidos ?? null;
  const usados = notas.filter((n) => n.examen_id === contenido.id).length;
  const base = { usados, permitidos };

  if (contenido.apertura) {
    const ap = new Date(contenido.apertura).getTime();
    if (!Number.isNaN(ap) && ahora < ap) {
      return { ...base, habilitado: false, motivo: `Disponible desde ${formatFechaHora(contenido.apertura)}` };
    }
  }
  if (contenido.cierre) {
    const ci = new Date(contenido.cierre).getTime();
    if (!Number.isNaN(ci) && ahora > ci) {
      return { ...base, habilitado: false, motivo: `Cerrado el ${formatFechaHora(contenido.cierre)}` };
    }
  }
  if (permitidos !== null && permitidos >= 1 && usados >= permitidos) {
    return { ...base, habilitado: false, motivo: `Ya rendiste este examen (${usados}/${permitidos})` };
  }
  // Un examen publicado pero sin ninguna pregunta se ofrecía con botón para
  // entrar, y al entrar el alumno llegaba a un examen vacío. Se bloquea con
  // motivo en vez de esconderlo: si el alumno espera ese parcial y no lo ve, no
  // sabe si es un error suyo o del sistema. El motivo no le pide nada a él,
  // porque no hay nada que pueda hacer.
  //
  // Va DESPUÉS de la ventana y los intentos a propósito: si además está cerrado,
  // el motivo útil es el cierre, no que falten preguntas.
  if (contenido.cantidad_preguntas === 0) {
    return {
      ...base,
      habilitado: false,
      motivo: 'Todavía no tiene preguntas cargadas. Consultá con tu docente.',
    };
  }
  return { ...base, habilitado: true };
}
