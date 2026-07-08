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
    }).format(new Date(iso));
  } catch {
    return iso;
  }
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
  return { ...base, habilitado: true };
}
