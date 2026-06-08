/**
 * Helpers de presentación compartidos por las pantallas de proctoring (lista + detalle).
 *
 * Centraliza el formateo de fechas y la lógica de color por riesgo/score/veredicto,
 * para que los sub-componentes no dupliquen reglas y queden por debajo del límite
 * de líneas. NADA de hardcodear umbrales en cada tarjeta: la fuente es este archivo.
 */
import type { VeredictoReinferencia } from '../../lib/types';
import { EXAMENES, COMISIONES, MATERIAS } from '../../lib/api';

/** Umbral de score a partir del cual una sesión se considera de riesgo alto. */
export const SCORE_UMBRAL_ALTO = 60;
/** Umbral de score a partir del cual una sesión se considera de riesgo medio. */
export const SCORE_UMBRAL_MEDIO = 30;

/** Fecha absoluta legible (es-AR). */
export function formatFecha(iso: string, conSegundos = false): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(conSegundos ? { second: '2-digit' } : {}),
    });
  } catch {
    return iso;
  }
}

/** Fecha relativa amable ("hace 5 min", "ayer", "hace 3 d"). */
export function formatFechaRelativa(iso: string): string {
  try {
    const ahora = Date.now();
    const t = new Date(iso).getTime();
    const diffSeg = Math.round((ahora - t) / 1000);
    if (diffSeg < 60) return 'recién';
    const diffMin = Math.round(diffSeg / 60);
    if (diffMin < 60) return `hace ${diffMin} min`;
    const diffHoras = Math.round(diffMin / 60);
    if (diffHoras < 24) return `hace ${diffHoras} h`;
    const diffDias = Math.round(diffHoras / 24);
    if (diffDias === 1) return 'ayer';
    if (diffDias < 7) return `hace ${diffDias} d`;
    return formatFecha(iso);
  } catch {
    return iso;
  }
}

/** Nivel de riesgo derivado del score. */
export type NivelRiesgo = 'bajo' | 'medio' | 'alto';

export function nivelRiesgo(score: number): NivelRiesgo {
  if (score >= SCORE_UMBRAL_ALTO) return 'alto';
  if (score >= SCORE_UMBRAL_MEDIO) return 'medio';
  return 'bajo';
}

/** Clase de color de texto para el score, según su nivel de riesgo. */
export function scoreTextColor(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'text-error';
  if (nivel === 'medio') return 'text-warning';
  return 'text-success';
}

/** Clase de borde-izquierdo (acento) para la tarjeta de sesión, según riesgo. */
export function scoreAccentBorder(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'border-l-error';
  if (nivel === 'medio') return 'border-l-warning';
  return 'border-l-success';
}

/** Clase de relleno del gauge de score. */
export function gaugeFill(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'bg-error';
  if (nivel === 'medio') return 'bg-warning';
  return 'bg-success';
}

/** Tono del Badge para el modo de la sesión. */
export function modoBadgeTone(modo: string): 'primary' | 'neutral' | 'warning' {
  if (modo === 'examen') return 'primary';
  if (modo === 'diagnostico') return 'warning';
  return 'neutral';
}

/** Etiqueta legible del modo de la sesión. */
export function modoLabel(modo: string): string {
  const map: Record<string, string> = {
    diagnostico: 'Diagnóstico',
    examen: 'Examen',
    test: 'Prueba',
  };
  return map[modo] ?? modo;
}

// --- Veredicto de re-inferencia server-side (cliente = sensor no confiable) ---

export function verdictClasses(v: VeredictoReinferencia | null | undefined): string {
  if (v === 'coincide') return 'bg-success-container text-success border-success/30';
  if (v === 'discrepancia') return 'bg-error-container text-on-error-container border-error/30';
  return 'bg-surface-container text-on-surface-variant border-outline-variant/40';
}

export function verdictIcon(v: VeredictoReinferencia | null | undefined): string {
  if (v === 'coincide') return 'check_circle';
  if (v === 'discrepancia') return 'report';
  return 'help';
}

export function verdictLabel(v: VeredictoReinferencia | null | undefined): string {
  if (!v) return 'No evaluado';
  const map: Record<VeredictoReinferencia, string> = {
    coincide: 'Coincide',
    discrepancia: 'Discrepancia',
    sin_referencia: 'Sin referencia',
    error: 'Error',
  };
  return map[v] ?? v;
}

// --- Formateo de payload de eventos (legibilidad para revisión humana) ---

/**
 * Tabla de etiquetas legibles para las claves más comunes del payload de un
 * evento. Lo que NO está acá cae al fallback (key con guiones bajos a espacios,
 * capitalizada). Mantener pequeño y honesto: si una clave no aparece, no pasa
 * nada — el fallback es razonable.
 */
const PAYLOAD_KEY_LABELS: Record<string, string> = {
  sostenido_ms: 'Duración',
  duracion_ms: 'Duración',
  tiempo_ms: 'Tiempo',
  ms: 'Duración',
  face_count: 'Rostros',
  faces: 'Rostros',
  rostros: 'Rostros',
  trigger_evidence: 'Disparó evidencia',
  gaze_x: 'Mirada X',
  gaze_y: 'Mirada Y',
  yaw: 'Yaw',
  pitch: 'Pitch',
  roll: 'Roll',
};

/** Etiqueta humana para una clave de payload. */
export function formatPayloadKey(key: string): string {
  if (key in PAYLOAD_KEY_LABELS) return PAYLOAD_KEY_LABELS[key];
  // Fallback: snake_case → "Snake case"
  const limpio = key.replace(/_/g, ' ').trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}

/**
 * Convierte una duración en milisegundos a una etiqueta legible.
 *   500    → "0,5 s"
 *   3000   → "3 s"
 *   3200   → "3,2 s"
 *   75_000 → "1 min 15 s"
 * Para valores < 1 s pero ≥ 100 ms usamos décimas de segundo; bajo 100 ms
 * mostramos los milisegundos directos (señal cruda, no rotamos a "0,0 s").
 */
export function formatDuracionMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return `${ms} ms`;
  if (ms < 100) return `${Math.round(ms)} ms`;
  if (ms < 60_000) {
    const segundos = ms / 1000;
    // 1 decimal solo si aporta info (3,2 s pero no 3,0 s).
    const fmt = Number.isInteger(segundos) || segundos >= 10
      ? segundos.toFixed(0)
      : segundos.toFixed(1).replace('.', ',');
    return `${fmt} s`;
  }
  const totalSeg = Math.round(ms / 1000);
  const min = Math.floor(totalSeg / 60);
  const seg = totalSeg % 60;
  return seg === 0 ? `${min} min` : `${min} min ${seg} s`;
}

/**
 * Formatea el valor de una clave de payload pensando en lectura humana:
 * - claves que terminan en `_ms` o que son exactamente `ms` → "X s" / "X min Y s"
 * - booleanos → "Sí"/"No"
 * - números con muchos decimales → 2 decimales
 * - el resto → String(v)
 */
export function formatPayloadValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return '—';
  const esMs = key === 'ms' || /_ms$/.test(key);
  if (esMs && typeof value === 'number') return formatDuracionMs(value);
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(2).replace('.', ',');
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

// --- Join del catálogo académico: enriquece una sesión con su contexto ---

/**
 * Contexto académico de una sesión, derivado del `exam_id` contra el catálogo local.
 * Reutilizable por las tres pantallas de proctoring (cola, grabadas, en vivo).
 */
export interface ExamInfo {
  examNombre: string;
  materiaNombre: string;
  comisionNombre: string;
  docente: string;
}

/**
 * Joinea un `exam_id` con el catálogo académico local (examen → comisión → materia).
 *
 * Función PURA: opera sobre los arrays importados de `api.ts`, sin llamadas HTTP,
 * sin hooks, sin acceso al store. Retorna null si el id es falsy o si cualquier
 * eslabón del lookup no existe (sesión de harness sin examen real).
 */
export function joinExamInfo(examId: string | null | undefined): ExamInfo | null {
  if (!examId) return null;
  try {
    const examen = EXAMENES.find((e) => e.id === examId);
    if (!examen) return null;
    const comision = examen.comision_id
      ? COMISIONES.find((c) => c.id === examen.comision_id)
      : undefined;
    if (!comision) return null;
    const materia = MATERIAS.find((m) => m.id === comision.materia_id);
    if (!materia) return null;
    return {
      examNombre: examen.nombre,
      materiaNombre: materia.nombre,
      comisionNombre: comision.nombre,
      docente: comision.docente,
    };
  } catch {
    return null;
  }
}
