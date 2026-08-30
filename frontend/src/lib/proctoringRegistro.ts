/**
 * Cliente de API del Registro de sesiones de proctoring (C-76 tarea 17).
 *
 * Funciones puras exportadas para testabilidad, mismo patrón que
 * `examContentResultados.ts` (paginación real + filtros server-side):
 *  - listarRegistroSesionesFn  → GET /proctoring/sessions/registro (paginado + filtrado)
 *  - listarExamenesConSesionesFn → GET /proctoring/sessions/registro/examenes (catálogo)
 *
 * NADA hardcodeado: el catálogo de exámenes y el nivel de riesgo salen SIEMPRE
 * del backend — el frontend solo arma el query string y renderiza la respuesta.
 */
import type { SesionProctoringResumen } from './types';

import { fetchAutenticado } from './fetchAutenticado';
export interface RegistroSesionesPaginado {
  items: SesionProctoringResumen[];
  total: number;
  page: number;
  page_size: number;
  // Agregados sobre el TOTAL filtrado (C-76 tarea 19.3/20.4), calculados
  // server-side ANTES de paginar. El frontend los usa TAL CUAL para las stat
  // cards — NUNCA los recalcula sumando sobre `items` (que solo tiene la
  // pagina actual).
  //
  // `total_eventos`/`total_discrepancias` (tarea 19) se retiraron en la tarea
  // 20 — reemplazados por `en_cola_revision`.
  riesgo_bajo: number;
  riesgo_medio: number;
  riesgo_alto: number;
  // Sesiones con score >= umbral de la Cola de revision (mismo umbral vivo
  // que usa esa cola — no uno reinventado). C-76 tarea 20.4/20.6.
  en_cola_revision: number;
}

export interface ExamenConSesiones {
  id: string;
  titulo: string;
}

/** Nivel de riesgo derivado del score — espeja `NivelRiesgo` (proctoring/helpers.ts). */
export type NivelRiesgoFiltro = 'bajo' | 'medio' | 'alto';

function authHeaders(token: string | undefined): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function lanzarSiError(res: Response): Promise<void> {
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
}

/**
 * Lista el Registro de sesiones (finalizadas) con paginación real y filtros
 * server-side. Lanza en error HTTP para que el caller muestre el error en pantalla.
 */
export async function listarRegistroSesionesFn(
  apiBase: string,
  token: string | undefined,
  params: {
    q?: string;
    exam_id?: string;
    fecha_desde?: string;
    fecha_hasta?: string;
    nivel_riesgo?: NivelRiesgoFiltro | '';
    materia_id?: string;
    comision_id?: string;
    /** Trae también los ENSAYOS del docente, ocultos por defecto. */
    incluir_pruebas?: boolean;
    page?: number;
    page_size?: number;
  } = {},
): Promise<RegistroSesionesPaginado> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.exam_id) qs.set('exam_id', params.exam_id);
  if (params.fecha_desde) qs.set('fecha_desde', params.fecha_desde);
  if (params.fecha_hasta) qs.set('fecha_hasta', params.fecha_hasta);
  if (params.nivel_riesgo) qs.set('nivel_riesgo', params.nivel_riesgo);
  if (params.materia_id) qs.set('materia_id', params.materia_id);
  if (params.comision_id) qs.set('comision_id', params.comision_id);
  if (params.incluir_pruebas) qs.set('incluir_pruebas', 'true');
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  const qStr = qs.toString();
  const url = `${apiBase}/proctoring/sessions/registro${qStr ? '?' + qStr : ''}`;
  const res = await fetchAutenticado(url, { method: 'GET', headers: authHeaders(token) });
  await lanzarSiError(res);
  return res.json() as Promise<RegistroSesionesPaginado>;
}

/**
 * Catálogo de exámenes con sesiones registradas — alimenta el <select> de
 * "Examen" del filtro. El frontend NUNCA hardcodea esta lista.
 */
export async function listarExamenesConSesionesFn(
  apiBase: string,
  token: string | undefined,
): Promise<ExamenConSesiones[]> {
  const res = await fetchAutenticado(`${apiBase}/proctoring/sessions/registro/examenes`, {
    method: 'GET',
    headers: authHeaders(token),
  });
  await lanzarSiError(res);
  return res.json() as Promise<ExamenConSesiones[]>;
}

/**
 * Elimina una sesion de DIAGNOSTICO (`modo='test'`, sin examen real vinculado)
 * — admin-only (C-76 tarea 20.1). Las sesiones `modo='examen'` (evidencia
 * academica real) quedan PERMANENTEMENTE protegidas: el backend rechaza con
 * 409 (regla dura #6/#7, cadena de custodia, tarea 16) — sin excepciones. El
 * caller (UI) solo debe ofrecer el botón en filas `modo === 'test'`.
 */
export async function eliminarSesionTestFn(
  apiBase: string,
  token: string | undefined,
  sessionId: string,
): Promise<void> {
  const res = await fetchAutenticado(`${apiBase}/proctoring/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  await lanzarSiError(res);
}
