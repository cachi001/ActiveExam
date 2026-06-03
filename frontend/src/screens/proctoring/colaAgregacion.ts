/**
 * Agregación pura de sesiones de proctoring por la jerarquía del catálogo académico.
 *
 * Toma las sesiones reales (api.listarSesionesProctoring), las filtra a alto riesgo,
 * las enriquece UNA sola vez con joinExamInfo (exam_id → materia/comisión/examen) y
 * provee funciones de agrupación por nivel para la navegación drill-down de la Cola
 * de revisión (Materia → Comisión → Examen → Persona).
 *
 * FUNCIONES PURAS: sin React, sin hooks, sin llamadas HTTP. Operan sobre arrays.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { joinExamInfo, type ExamInfo } from './helpers';

/** Nombre sentinela para sesiones sin examen del catálogo resoluble. */
export const SIN_EXAMEN = 'Sin examen asociado';

/** Un nodo de un nivel del drill-down (materia, comisión o examen). */
export interface NodoCola {
  /** Clave estable para React keys y para bajar de nivel (= nombre, único por nivel). */
  clave: string;
  /** Nombre legible mostrado en la card. */
  nombre: string;
  /** Cantidad de sesiones (personas) en riesgo bajo este nodo. */
  enRiesgo: number;
}

/** Una sesión ya enriquecida con su contexto académico (o null si no resuelve). */
export interface SesionEnriquecida {
  sesion: SesionProctoringResumen;
  info: ExamInfo | null;
}

/** Nombre de materia de una sesión enriquecida (sentinela si no hay info). */
function materiaDe(item: SesionEnriquecida): string {
  return item.info?.materiaNombre ?? SIN_EXAMEN;
}

/** Nombre de comisión de una sesión enriquecida (sentinela si no hay info). */
function comisionDe(item: SesionEnriquecida): string {
  return item.info?.comisionNombre ?? SIN_EXAMEN;
}

/** Nombre de examen de una sesión enriquecida (sentinela si no hay info). */
function examenDe(item: SesionEnriquecida): string {
  return item.info?.examNombre ?? SIN_EXAMEN;
}

/**
 * Filtra a alto riesgo (score ≥ umbral), enriquece con joinExamInfo y ordena por
 * score descendente (mayor riesgo primero; desempate por más discrepancias).
 */
export function enriquecerYFiltrar(
  sesiones: SesionProctoringResumen[],
  umbral: number,
): SesionEnriquecida[] {
  return sesiones
    .filter((s) => s.score >= umbral)
    .sort((a, b) => b.score - a.score || b.total_discrepancias - a.total_discrepancias)
    .map((sesion) => ({ sesion, info: joinExamInfo(sesion.exam_id) }));
}

/**
 * Agrupa una lista enriquecida por una clave (nombre de nivel), preservando el
 * orden de primera aparición (que ya viene ordenado por riesgo), y produce nodos
 * con el contador de sesiones en riesgo. Ordena los nodos por contador desc.
 */
function agrupar(
  items: SesionEnriquecida[],
  claveDe: (item: SesionEnriquecida) => string,
): NodoCola[] {
  const conteo = new Map<string, number>();
  for (const item of items) {
    const k = claveDe(item);
    conteo.set(k, (conteo.get(k) ?? 0) + 1);
  }
  return [...conteo.entries()]
    .map(([nombre, enRiesgo]) => ({ clave: nombre, nombre, enRiesgo }))
    .sort((a, b) => b.enRiesgo - a.enRiesgo || a.nombre.localeCompare(b.nombre));
}

/** Nivel 1: materias con sesiones en riesgo. */
export function materiasEnRiesgo(items: SesionEnriquecida[]): NodoCola[] {
  return agrupar(items, materiaDe);
}

/** Nivel 2: comisiones en riesgo de una materia. */
export function comisionesEnRiesgo(
  items: SesionEnriquecida[],
  materiaNombre: string,
): NodoCola[] {
  return agrupar(
    items.filter((i) => materiaDe(i) === materiaNombre),
    comisionDe,
  );
}

/** Nivel 3: exámenes en riesgo de una materia + comisión. */
export function examenesEnRiesgo(
  items: SesionEnriquecida[],
  materiaNombre: string,
  comisionNombre: string,
): NodoCola[] {
  return agrupar(
    items.filter((i) => materiaDe(i) === materiaNombre && comisionDe(i) === comisionNombre),
    examenDe,
  );
}

/** Nivel 4: personas (sesiones) en riesgo de un examen puntual. */
export function personasEnRiesgo(
  items: SesionEnriquecida[],
  materiaNombre: string,
  comisionNombre: string,
  examNombre: string,
): SesionEnriquecida[] {
  return items.filter(
    (i) =>
      materiaDe(i) === materiaNombre &&
      comisionDe(i) === comisionNombre &&
      examenDe(i) === examNombre,
  );
}
