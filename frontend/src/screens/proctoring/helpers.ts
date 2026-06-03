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
