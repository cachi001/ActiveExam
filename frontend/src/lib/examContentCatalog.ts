/**
 * Cliente de catálogo de exámenes de contenido (C-69).
 *
 * Función pura para listar los exámenes importados desde Moodle XML.
 * Testeable de forma aislada (exporta la función raw con parámetros inyectables).
 * D3: la respuesta NUNCA incluye es_correcta ni opciones — solo metadatos.
 */

import type { ExamenContenidoResumen } from './types';

import { fetchAutenticado } from './fetchAutenticado';
/**
 * Estado de baja lógica del catálogo (c-78 D1). Mismo tri-estado que el filtro de
 * Usuarios: 'activo' es el default del backend, así que omitirlo devuelve solo los
 * exámenes vigentes.
 */
export type EstadoCatalogoExamen = 'activo' | 'inactivo' | 'todos';

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
  params: {
    q?: string;
    page?: number;
    page_size?: number;
    materia_id?: string;
    comision_id?: string;
    /** Baja lógica (c-78): 'activo' (default del backend) | 'inactivo' | 'todos'. */
    estado?: EstadoCatalogoExamen;
  } = {},
): Promise<CatalogoExamenesPaginado> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  if (params.materia_id) qs.set('materia_id', params.materia_id);
  if (params.comision_id) qs.set('comision_id', params.comision_id);
  if (params.estado) qs.set('estado', params.estado);
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

/**
 * Baja lógica de un examen del catálogo (c-78 D1).
 *
 * A diferencia de los listados, esto PROPAGA el error: una escritura que falla en
 * silencio le hace creer al usuario que el examen quedó de baja cuando sigue
 * publicado. 404 = no existe o ya estaba de baja.
 */
export async function darDeBajaExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<void> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`No se pudo dar de baja el examen (HTTP ${res.status}).`);
}

/**
 * Una comisión que rinde el examen (c-78 E-06, task 14.4). Bajo el modelo
 * replicado cada comisión tiene su propio examen: este item es el par
 * (comisión, examen de esa comisión).
 */
export interface ComisionDelExamen {
  examen_id: string;
  comision_id: string;
  comision_codigo: string;
  comision_nombre: string;
  titulo: string;
  dado_de_baja: boolean;
  total_intentos: number;
  es_el_actual: boolean;
}

export async function listarComisionesDelExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<ComisionDelExamen[]> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/comisiones`, {
    method: 'GET',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!res.ok) {
    throw new Error(`No se pudieron cargar las comisiones del examen (HTTP ${res.status}).`);
  }
  const body = await res.json();
  return body.items ?? [];
}

/** Suma una comisión: crea una réplica del examen con las mismas preguntas. */
export async function agregarComisionAlExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  comisionId: string,
): Promise<{ examen_id: string; comision_id: string | null; titulo: string }> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/comisiones`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ comision_id: comisionId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : (detail?.mensaje ?? `No se pudo agregar la comisión (HTTP ${res.status}).`),
    );
  }
  return res.json();
}

/** Quita una comisión. El backend la rechaza si esa comisión ya rindió. */
export async function quitarComisionDelExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  comisionId: string,
): Promise<void> {
  const res = await fetchAutenticado(
    `${apiBase}/exam-content/${examenId}/comisiones/${comisionId}`,
    {
      method: 'DELETE',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : (detail?.mensaje ?? `No se pudo quitar la comisión (HTTP ${res.status}).`),
    );
  }
}

/**
 * Habilita un examen en borrador (c-78 E-07). Es de IDA: para sacarlo de
 * circulación está la baja lógica. 404 si no existe o ya estaba habilitado.
 */
export async function habilitarExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<void> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/habilitar`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : (detail?.mensaje ?? `No se pudo habilitar el examen (HTTP ${res.status}).`),
    );
  }
}

/** Un tramo del sorteo con el estado de su pool (c-78 E-07/E-08). */
export interface TramoSorteo {
  categoria_id: string | null;
  categoria_nombre: string | null;
  incluir_subcategorias: boolean;
  tipos: string[] | null;
  cantidad: number;
  en_el_pool: number;
  en_el_banco: number;
}

export interface SorteoDelExamen {
  modo_preguntas: string;
  tramos: TramoSorteo[];
  largo_del_examen: number;
  pool_total: number;
  nuevas_en_el_banco: number;
  pool_editable: boolean;
  total_intentos: number;
}

export async function leerSorteoDelExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<SorteoDelExamen> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/sorteo`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!res.ok) {
    throw new Error(`No se pudo cargar el sorteo del examen (HTTP ${res.status}).`);
  }
  return res.json();
}

/** Incorpora al pool las preguntas nuevas del banco. 409 si el examen ya se rindió. */
export async function actualizarPoolDelExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<SorteoDelExamen> {
  const res = await fetchAutenticado(
    `${apiBase}/exam-content/${examenId}/sorteo/actualizar-pool`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : (detail?.mensaje ?? `No se pudo actualizar el pool (HTTP ${res.status}).`),
    );
  }
  return res.json();
}

export interface ExamenDuplicado {
  examen_id: string;
  titulo: string;
  comision_id: string | null;
  total_preguntas: number;
}

/**
 * Duplica un examen (c-78 E-06, task 14.2). La copia trae las preguntas y la
 * configuración de mecánica y nota; NO trae los intentos rendidos, las notas ya
 * publicadas ni el destino de write-back en Moodle.
 *
 * Sin `titulo` la copia se llama «… (copia)» y queda en la misma comisión.
 */
export async function duplicarExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
  titulo?: string,
): Promise<ExamenDuplicado> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/duplicar`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(titulo ? { titulo } : {}),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : (detail?.mensaje ?? `No se pudo duplicar el examen (HTTP ${res.status}).`),
    );
  }
  return res.json();
}

/** Reactiva un examen dado de baja (c-78 D1). 404 = no existe o ya estaba activo. */
export async function reactivarExamenFn(
  apiBase: string,
  token: string | undefined,
  examenId: string,
): Promise<void> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/${examenId}/reactivar`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`No se pudo reactivar el examen (HTTP ${res.status}).`);
}
