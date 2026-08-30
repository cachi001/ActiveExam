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
import { type ExamInfo } from './helpers';

/** Nombre sentinela para sesiones sin examen del catálogo resoluble. */
export const SIN_EXAMEN = 'Sin examen asociado';
/** Sentinela cuando el examen existe pero no está asociado a una materia/comisión. */
export const SIN_MATERIA = 'Sin materia asignada';
export const SIN_COMISION = 'Sin comisión asignada';

/**
 * Resuelve el contexto académico de una sesión a partir de lo que resolvió el backend
 * (examen_contenido → comisión → materia). Si la sesión no trae contexto server-side
 * (sesión de harness sin examen real), no hay nada que mostrar → null.
 */
export function examInfoDeSesion(s: SesionProctoringResumen): ExamInfo | null {
  if (s.examen_titulo || s.examen_contenido_id) {
    return {
      examNombre: s.examen_titulo ?? SIN_EXAMEN,
      materiaNombre: s.materia_nombre ?? SIN_MATERIA,
      comisionNombre: s.comision_nombre ?? SIN_COMISION,
    };
  }
  return null;
}

/**
 * Arma el subtítulo del header de "Supervisión en vivo" a partir del contexto
 * académico de una sesión: `materia · comisión · docente`, salteando las partes
 * vacías o sentinela (una sesión sin materia/comisión asignada no debe mostrar
 * "Sin materia asignada" en el header, ni dejar un " · " colgando por el tutor
 * vacío que trae el contexto server-side).
 *
 * PURA: sin red, sin hooks. Retorna '' si no hay info o si nada aporta.
 */
export function subtituloExamen(info: ExamInfo | null): string {
  if (!info) return '';
  const sentinelas = new Set([SIN_EXAMEN, SIN_MATERIA, SIN_COMISION]);
  return [info.materiaNombre, info.comisionNombre]
    .map((p) => p?.trim() ?? '')
    .filter((p) => p !== '' && !sentinelas.has(p))
    .join(' · ');
}

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
  return item.info?.materiaNombre ?? SIN_MATERIA;
}

/** Nombre de comisión de una sesión enriquecida (sentinela si no hay info). */
function comisionDe(item: SesionEnriquecida): string {
  return item.info?.comisionNombre ?? SIN_COMISION;
}

/** Nombre de examen de una sesión enriquecida (sentinela si no hay info). */
function examenDe(item: SesionEnriquecida): string {
  return item.info?.examNombre ?? SIN_EXAMEN;
}

/**
 * c-78 D3 — DEFINICIÓN CANÓNICA de "entra a la Cola de revisión".
 *
 * Una sesión entra si tiene un examen REAL vinculado y su score alcanza el umbral
 * vivo. Las sesiones de diagnóstico (ej. "Grabar sesión" del Test de detección) no
 * entran por más que superen el umbral: no hay a quién revisarle nada.
 *
 * Vive acá y en UN solo lugar a propósito: el Panel de administración contaba
 * `flagged` sin el filtro de examen vinculado, así que mostraba un número más alto
 * que la Cola de revisión para el mismo dato. Todo consumidor que cuente "en cola"
 * SHALL usar esta función; duplicar la condición es lo que produjo el desvío.
 */
export function entraACola(s: SesionProctoringResumen, umbral: number): boolean {
  // Los ensayos del docente quedan afuera aunque disparen eventos. La Cola existe
  // para decidir sobre PERSONAS, y un ensayo se lee como un caso a revisar que
  // nunca va a tener nota ni veredicto (las sesiones de prueba no cuentan en
  // ningún lado). Mismo criterio que resultados y que el write-back a Moodle.
  if (s.es_prueba) return false;
  return s.score >= umbral && (s.exam_id != null || s.examen_contenido_id != null);
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
    .filter((s) => entraACola(s, umbral))
    .sort((a, b) => b.score - a.score || b.total_discrepancias - a.total_discrepancias)
    .map((sesion) => ({ sesion, info: examInfoDeSesion(sesion) }));
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
