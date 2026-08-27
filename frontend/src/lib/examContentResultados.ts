/**
 * Cliente de API para resultados de exámenes y sincronización con Moodle (C-69).
 *
 * Funciones puras exportadas para testabilidad:
 *  - listarResultadosFn   → GET /exam-content/{id}/resultados (paginado + filtrado)
 *  - sincronizarMoodleFn  → POST /exam-content/{id}/sincronizar-moodle
 *  - getExamenHeaderFn    → GET /exam-content/{id}/resumen (metadatos del encabezado)
 */

import type { ExamenContenidoResumen } from './types';

import { fetchAutenticado } from './fetchAutenticado';
// Enum de dominio CERRADO — espeja WritebackEstado (backend/app/application/moodle/
// writeback_service.py) + el alias de display ESTADO_SIN_TOKEN (resultados_query.py).
// Las etiquetas legibles de estos 4 valores tienen fuente única en el backend:
// app/application/stats/labels.py::ETIQUETA_ESTADO_MOODLE (con test de cobertura
// en tests/test_stats_labels.py que falla si el backend agrega/quita un estado).
// c-78 D14: 'manual' = una persona dice que cargó la nota en el campus. NO es
// 'enviado' (que significa "el campus confirmó"): la diferencia importa justo
// cuando hay un reclamo por una nota que no aparece en la libreta.
export type EstadoMoodle = 'pendiente' | 'enviado' | 'fallido' | 'sin_token' | 'manual';

// Estado de la ENTREGA (C-76 tarea 14), DERIVADO server-side (nunca persistido) —
// ORTOGONAL a `estado_moodle` (estado de sync con el campus). Espeja el enum
// backend `ESTADOS_ENTREGA_VALIDOS` (resultados_query.py).
export type EstadoEntrega = 'no_finalizada' | 'en_revision' | 'revisada' | 'finalizada';

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
  /** Estado de la entrega (derivado). Ausente en fixtures viejos → tratar como 'finalizada'. */
  estado_entrega?: EstadoEntrega;
  /** Soft-hide administrativo del panel de resultados (no disciplinario). */
  archivado?: boolean;
  /**
   * c-78 D14: quién marcó a mano que la nota se cargó en el campus, y cuándo.
   * null = nunca se marcó a mano. Sirve para distinguir en pantalla
   * "confirmado por el campus" de "marcado por {persona} el {fecha}".
   */
  marcada_manual_por?: string | null;
  marcada_manual_en?: string | null;
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

/** Valores del filtro tri-estado de archivado (c-78 D6). */
export type ArchivadoFiltro = 'false' | 'true' | 'todas';

/**
 * Lista los resultados de un examen con paginación y filtros serverside.
 * Lanza en error HTTP para que el caller muestre el error en pantalla.
 */
export async function listarResultadosFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  params: {
    q?: string;
    estado?: string;
    estado_entrega?: string;
    /**
     * c-78 D6: tri-estado — 'false' (default del backend, solo NO archivadas) |
     * 'true' (solo archivadas) | 'todas' (ambas). Era un booleano, con lo cual
     * "incluir archivadas" era inexpresable: `true` traía SOLO las archivadas.
     */
    archivado?: ArchivadoFiltro;
    fecha_desde?: string;
    fecha_hasta?: string;
    page?: number;
    page_size?: number;
  } = {},
): Promise<ResultadosPaginados> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.estado) qs.set('estado', params.estado);
  if (params.estado_entrega) qs.set('estado_entrega', params.estado_entrega);
  if (params.archivado !== undefined) qs.set('archivado', params.archivado);
  if (params.fecha_desde) qs.set('fecha_desde', params.fecha_desde);
  if (params.fecha_hasta) qs.set('fecha_hasta', params.fecha_hasta);
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  const qStr = qs.toString();
  const url = `${apiBase}/exam-content/${encodeURIComponent(examenId)}/resultados${qStr ? '?' + qStr : ''}`;
  const res = await fetchAutenticado(url, { method: 'GET', headers: authHeaders(token) });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<ResultadosPaginados>;
}

/**
 * Dispara la sincronización de notas con Moodle para un examen.
 * POST /exam-content/{id}/sincronizar-moodle
 *
 * Body opcional:
 * - Sin sessionIds (o array vacío): sincroniza TODAS las notas pendientes/fallidas.
 * - Con sessionIds: sincroniza SOLO esas sesiones específicas (individual = array de 1).
 *   Las retenciones por riesgo/config siguen aplicándose aunque la sesión esté en la lista.
 *
 * Retrocompatible: los callers anteriores sin sessionIds siguen funcionando igual.
 * Lanza en error HTTP.
 */
export async function sincronizarMoodleFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  sessionIds?: string[],
): Promise<SincronizarMoodleResponse> {
  const hasIds = sessionIds && sessionIds.length > 0;
  const res = await fetchAutenticado(
    `${apiBase}/exam-content/${encodeURIComponent(examenId)}/sincronizar-moodle`,
    {
      method: 'POST',
      headers: authHeaders(token),
      ...(hasIds ? { body: JSON.stringify({ session_ids: sessionIds }) } : {}),
    },
  );
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<SincronizarMoodleResponse>;
}

/**
 * Archiva o desarchiva una fila de resultados (C-76 tarea 14) — soft-hide
 * administrativo, NO disciplinario (no es un veredicto sobre la sesión).
 * PATCH /exam-content/{examenId}/resultados/{sessionId}/archivar
 * Lanza en error HTTP.
 */
export async function archivarResultadoFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  sessionId: string,
  archivado: boolean,
): Promise<{ session_id: string; archivado: boolean }> {
  const res = await fetchAutenticado(
    `${apiBase}/exam-content/${encodeURIComponent(examenId)}/resultados/${encodeURIComponent(sessionId)}/archivar`,
    {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify({ archivado }),
    },
  );
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<{ session_id: string; archivado: boolean }>;
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
  const res = await fetchAutenticado(
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
    materia_id: (data['materia_id'] as string | null) ?? null,
    materia_nombre: (data['materia_nombre'] as string | null) ?? null,
    // c-78 §18.4. `?? null` a propósito: un backend viejo que no manda el campo
    // queda en "no se sabe", no en "falta el tutor".
    comision_sin_tutor: (data['comision_sin_tutor'] as boolean | null) ?? null,
    // Este mapeo copia campo por campo, así que lo que no se nombra acá se
    // PIERDE aunque el backend lo mande y el tipo lo declare. Faltaban dos, y
    // los dos apagaban una sección entera del detalle sin ningún error visible:
    //   - `modo_preguntas`: sin esto el detalle no sabía que el examen era
    //     sorteado, así que igual mostraba la selección manual de preguntas con
    //     "0 de 30 seleccionadas".
    //   - `borrador`: el aviso de "examen sin habilitar" no aparecía NUNCA, que
    //     es justo lo primero que hay que saber al abrir un examen (c-78 E-07).
    modo_preguntas: (data['modo_preguntas'] as string | undefined) ?? undefined,
    borrador: (data['borrador'] as boolean | undefined) ?? undefined,
    apertura: (data['apertura'] as string | null) ?? null,
    cierre: (data['cierre'] as string | null) ?? null,
    eliminado_en: (data['eliminado_en'] as string | null) ?? null,
  };
}


/**
 * Marca a mano que la nota ya se cargó en el campus (c-78 §13.6, D14).
 *
 * Existe porque hay campus SIN API: la nota se carga a mano y en ActiveExam
 * quedaba 'pendiente' para siempre. El estado resultante es `manual`, NO
 * `enviado`: una afirmación humana y una confirmación del sistema no valen lo
 * mismo, y el backend rechaza (409) marcar a mano una nota ya confirmada.
 */
export async function marcarNotaCargadaFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  sessionId: string,
): Promise<{ session_id: string; estado_moodle: string; marcada_manual_por: string | null }> {
  const res = await fetchAutenticado(
    `${apiBase}/exam-content/${encodeURIComponent(examenId)}/resultados/${encodeURIComponent(
      sessionId,
    )}/marcar-cargada`,
    { method: 'PATCH', headers: authHeaders(token) },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detalle = (body as { detail?: { mensaje?: string } })?.detail?.mensaje;
    const err = new Error(detalle ?? `No se pudo marcar la nota (HTTP ${res.status}).`);
    (err as Error & { status?: number }).status = res.status;
    throw err;
  }
  return res.json();
}
