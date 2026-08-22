/**
 * Cliente de catálogo de exámenes de contenido (C-69).
 *
 * Función pura para listar los exámenes importados desde Moodle XML.
 * Testeable de forma aislada (exporta la función raw con parámetros inyectables).
 * D3: la respuesta NUNCA incluye es_correcta ni opciones — solo metadatos.
 */

import type { ExamenContenidoResumen } from './types';

import { fetchAutenticado } from './fetchAutenticado';
/** Respuesta paginada del catálogo (C-69 admin-sync, tarea 4). */
export interface CatalogoExamenesPaginado {
  items: ExamenContenidoResumen[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Función pura que llama a GET /exam-content y devuelve la lista de exámenes.
 * Exportada para tests unitarios — permite inyectar apiBase y token.
 *
 * Contrato del backend (C-69 admin-sync, tarea 4): respuesta paginada
 * { items, total, page, page_size }. Esta función desempaqueta `items` y es
 * TOLERANTE: si el backend devolviera un array plano (contrato legacy) lo usa
 * tal cual. Sin params, el backend usa un page_size amplio (1000) → devuelve todo.
 *
 * @param apiBase  - Base de la API (ej: '/api/v1')
 * @param token    - JWT de acceso (undefined si no hay sesión)
 * @returns Lista de exámenes importados, o [] si hay error de red/servidor.
 */
export async function listarExamenesContenidoFn(
  apiBase: string,
  token: string | undefined,
  strict = false,
): Promise<ExamenContenidoResumen[]> {
  try {
    const res = await fetchAutenticado(`${apiBase}/exam-content`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) {
      if (strict) throw new Error(`HTTP ${res.status}`);
      return [];
    }
    const body = await res.json();
    // Forma paginada { items, ... } o, por tolerancia, un array plano legacy.
    if (Array.isArray(body)) return body as ExamenContenidoResumen[];
    return (body?.items ?? []) as ExamenContenidoResumen[];
  } catch (e) {
    // `strict` PROPAGA el fallo. Sin él, un error de red devolvía [] y la pantalla
    // mostraba "0 exámenes" — indistinguible de "no hay exámenes". El helper
    // `statExamenesValue` no podía arreglarlo porque el error moría acá, una capa
    // más abajo: el hook recibía un ÉXITO con lista vacía.
    if (strict) throw e;
    return [];
  }
}

/**
 * Versión paginada de listarExamenesContenidoFn con soporte de búsqueda serverside.
 * Acepta q (búsqueda por título/materia/comisión), page y page_size.
 * Retorna la respuesta paginada completa (items + metadatos de paginación).
 *
 * En error de red retorna una respuesta vacía sin propagar.
 */
export async function listarExamenesContenidoPaginadoFn(
  apiBase: string,
  token: string | undefined,
  params: { q?: string; page?: number; page_size?: number; materia_id?: string; comision_id?: string } = {},
): Promise<CatalogoExamenesPaginado> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  if (params.materia_id) qs.set('materia_id', params.materia_id);
  if (params.comision_id) qs.set('comision_id', params.comision_id);
  const qStr = qs.toString();
  const fallback: CatalogoExamenesPaginado = {
    items: [],
    total: 0,
    page: params.page ?? 1,
    page_size: params.page_size ?? 25,
  };
  try {
    const res = await fetchAutenticado(`${apiBase}/exam-content${qStr ? '?' + qStr : ''}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) return fallback;
    const body = await res.json();
    if (Array.isArray(body)) {
      return { items: body as ExamenContenidoResumen[], total: body.length, page: 1, page_size: body.length || fallback.page_size };
    }
    return {
      items: (body?.items ?? []) as ExamenContenidoResumen[],
      total: body?.total ?? 0,
      page: body?.page ?? 1,
      page_size: body?.page_size ?? fallback.page_size,
    };
  } catch {
    return fallback;
  }
}
