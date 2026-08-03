/**
 * Cliente de API para resultados de exámenes y sincronización con Moodle (C-69).
 *
 * Funciones puras exportadas para testabilidad:
 *  - listarResultadosFn   → GET /exam-content/{id}/resultados (paginado + filtrado)
 *  - sincronizarMoodleFn  → POST /exam-content/{id}/sincronizar-moodle
 *  - getExamenHeaderFn    → GET /exam-content/{id}/resumen (metadatos del encabezado)
 */

import type { ExamenContenidoResumen } from './types';

// Enum de dominio CERRADO — espeja WritebackEstado (backend/app/application/moodle/
// writeback_service.py) + el alias de display ESTADO_SIN_TOKEN (resultados_query.py).
// Las etiquetas legibles de estos 4 valores tienen fuente única en el backend:
// app/application/stats/labels.py::ETIQUETA_ESTADO_MOODLE (con test de cobertura
// en tests/test_stats_labels.py que falla si el backend agrega/quita un estado).
export type EstadoMoodle = 'pendiente' | 'enviado' | 'fallido' | 'sin_token';

export interface ResultadoExamen {
  session_id: string;
  alumno_idnumber: string;
  alumno_email: string;
  alumno_nombre: string | null;
  nota: number | null;
  estado_moodle: EstadoMoodle;
  actualizado_en: string;
  /**
   * Motivo por el que la nota queda RETENIDA y no se sincroniza (gate D15):
   * 'en_riesgo' | 'anulada'. `null`/ausente = nada la retiene.
   * Es ortogonal a `estado_moodle`: una fila retenida sigue en 'pendiente'.
   */
  retenido_por?: string | null;
}

// Motivos de retención que SÍ corresponden a una revisión humana pendiente o
// resuelta (score de proctoring vs umbral, o un veredicto de un revisor).
// 'sin_destino' y 'sin_credencial_docente' son retenciones de CONFIGURACIÓN
// del campus — no tienen relación con el riesgo de la sesión ni con revisión
// alguna. Antes se contaban todas juntas bajo "N notas retenidas por
// revisión", así que un alumno que aprobó/desaprobó SIN superar el umbral
// (retenido solo por falta de destino Moodle) se mostraba como si su nota
// estuviera pendiente de revisión por riesgo — nunca lo estuvo.
const MOTIVOS_RETENCION_POR_REVISION = new Set(['en_riesgo', 'anulada']);

/**
 * Separa los resultados retenidos en dos contadores: los que están frenados
 * por una revisión humana (riesgo/caso/veredicto) y los que están frenados
 * por configuración faltante del campus (destino, credencial docente).
 * Un motivo desconocido cuenta como revisión (mismo comportamiento por
 * defecto que `EstadoBadge` para motivos no mapeados).
 */
export function contarRetencionesPorRevision(
  resultados: Pick<ResultadoExamen, 'retenido_por'>[],
): { revision: number; configuracion: number } {
  let revision = 0;
  let configuracion = 0;
  for (const r of resultados) {
    if (!r.retenido_por) continue;
    if (MOTIVOS_RETENCION_POR_REVISION.has(r.retenido_por)) {
      revision += 1;
    } else {
      configuracion += 1;
    }
  }
  return { revision, configuracion };
}

export interface ResultadosPaginados {
  items: ResultadoExamen[];
  total: number;
  page: number;
  page_size: number;
}

export interface SincronizarMoodleResponse {
  enviadas: number;
  fallidas: number;
  sin_token: number;
  total: number;
  mensaje?: string;
}

function authHeaders(token: string | undefined): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Lista los resultados de un examen con paginación y filtros serverside.
 * Lanza en error HTTP para que el caller muestre el error en pantalla.
 */
export async function listarResultadosFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  params: { q?: string; estado?: string; page?: number; page_size?: number } = {},
): Promise<ResultadosPaginados> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.estado) qs.set('estado', params.estado);
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  const qStr = qs.toString();
  const url = `${apiBase}/exam-content/${encodeURIComponent(examenId)}/resultados${qStr ? '?' + qStr : ''}`;
  const res = await fetch(url, { method: 'GET', headers: authHeaders(token) });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<ResultadosPaginados>;
}

/**
 * Dispara la sincronización de notas con Moodle para un examen.
 * POST /exam-content/{id}/sincronizar-moodle (sin body).
 * Lanza en error HTTP.
 */
export async function sincronizarMoodleFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<SincronizarMoodleResponse> {
  const res = await fetch(
    `${apiBase}/exam-content/${encodeURIComponent(examenId)}/sincronizar-moodle`,
    { method: 'POST', headers: authHeaders(token) },
  );
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<SincronizarMoodleResponse>;
}

/**
 * Obtiene los metadatos de encabezado de un examen para mostrar en el detalle.
 * GET /exam-content/{id}/resumen — read-model de resumen (cantidad_preguntas +
 * materia/comisión vía LEFT JOIN). Normaliza a ExamenContenidoResumen.
 * Lanza en error HTTP.
 */
export async function getExamenHeaderFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<ExamenContenidoResumen> {
  const res = await fetch(
    `${apiBase}/exam-content/${encodeURIComponent(examenId)}/resumen`,
    { method: 'GET', headers: authHeaders(token) },
  );
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  const data = await res.json() as Record<string, unknown>;
  return {
    id: (data['id'] as string) ?? examenId,
    titulo: (data['titulo'] as string) ?? '—',
    cantidad_preguntas: (data['cantidad_preguntas'] as number) ?? 0,
    comision_id: (data['comision_id'] as string | null) ?? null,
    comision_nombre: (data['comision_nombre'] as string | null) ?? null,
    materia_nombre: (data['materia_nombre'] as string | null) ?? null,
  };
}
