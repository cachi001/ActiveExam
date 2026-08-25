/**
 * Cliente de navegación del catálogo académico (C-69) — datos REALES.
 *
 * Funciones puras que pegan al backend real para que el alumno navegue
 * materia → comisión → examen importado. Inyectan apiBase + token para tests.
 * Degradación silenciosa por default: ante error de red/servidor devuelven []
 * (no rompen el flujo del alumno navegando el catálogo).
 *
 * c-78 E-13 / D16: ese default es EXACTAMENTE lo que hacía que la pantalla de
 * Materias dijera "No hay materias registradas" ante un 401 — una afirmación
 * falsa sobre los datos de alguien, que invita a recrear lo que ya existe. Por
 * eso cada función acepta `strict`: con `true` PROPAGA el fallo (con su `status`)
 * para que la pantalla pueda distinguir "cargó y está vacío" de "no pudo cargar".
 * Mismo precedente que `listarExamenesContenidoFn`.
 *
 * D3: la respuesta de exámenes NUNCA incluye es_correcta ni opciones.
 */

import type { Materia, Comision, ComisionConMateria, ExamenContenidoResumen } from './types';

import { fetchAutenticado } from './fetchAutenticado';
function buildHeaders(token: string | undefined): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** Error de carga del catálogo, con el status HTTP para poder traducirlo. */
export class CatalogoCargaError extends Error {
  readonly status?: number;
  constructor(mensaje: string, status?: number) {
    super(mensaje);
    this.name = 'CatalogoCargaError';
    this.status = status;
  }
}

async function getJson<T>(
  url: string,
  token: string | undefined,
  strict = false,
): Promise<T[]> {
  try {
    const res = await fetchAutenticado(url, { method: 'GET', headers: buildHeaders(token) });
    if (!res.ok) {
      if (strict) throw new CatalogoCargaError(`HTTP ${res.status}`, res.status);
      return [];
    }
    return (await res.json()) as T[];
  } catch (e) {
    if (strict) throw e;
    return [];
  }
}

/** GET /exam-content/materias → materias disponibles ({id, codigo, nombre}). */
export function listarMateriasFn(
  apiBase: string,
  token: string | undefined,
  strict = false,
): Promise<Materia[]> {
  return getJson<Materia>(`${apiBase}/exam-content/materias`, token, strict);
}

/** GET /exam-content/materias/{materiaId}/comisiones → comisiones de la materia. */
export function listarComisionesFn(
  apiBase: string,
  token: string | undefined,
  materiaId: string,
  strict = false,
): Promise<Comision[]> {
  return getJson<Comision>(
    `${apiBase}/exam-content/materias/${encodeURIComponent(materiaId)}/comisiones`,
    token,
    strict,
  );
}

/** GET /exam-content/comisiones → TODAS las comisiones, con su materia embebida.
 * Selector combinado único ("CÓDIGO - Materia"), sin elegir materia primero. */
export function listarTodasComisionesFn(
  apiBase: string,
  token: string | undefined,
): Promise<ComisionConMateria[]> {
  return getJson<ComisionConMateria>(`${apiBase}/exam-content/comisiones`, token);
}

/** GET /exam-content/comisiones/{comisionId}/examenes → exámenes importados de la comisión. */
export function listarExamenesDeComisionFn(
  apiBase: string,
  token: string | undefined,
  comisionId: string,
): Promise<ExamenContenidoResumen[]> {
  return getJson<ExamenContenidoResumen>(
    `${apiBase}/exam-content/comisiones/${encodeURIComponent(comisionId)}/examenes`,
    token,
  );
}

/** Resultado de la auto-matriculación por código (C-70). */
export interface InscripcionPorCodigoResult {
  comision_id: string;
  comision_nombre: string;
  materia_nombre: string;
  ya_inscripto: boolean;
}

/**
 * POST /exam-content/inscribirme → el alumno se auto-matricula con un código (C-70).
 * A diferencia de los GET del catálogo, NO degrada en silencio: lanza un Error con
 * `.status` (404/422 = código inválido) para que la UI muestre el mensaje correcto.
 * 200 → resultado (incluye `ya_inscripto` para el caso idempotente).
 */
export async function inscribirmePorCodigoFn(
  apiBase: string,
  token: string | undefined,
  codigoMatriculacion: string,
): Promise<InscripcionPorCodigoResult> {
  const res = await fetchAutenticado(`${apiBase}/exam-content/inscribirme`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ codigo_matriculacion: codigoMatriculacion }),
  });
  if (!res.ok) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body: any = await res.json().catch(() => ({}));
    const msg: string = body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`;
    throw Object.assign(new Error(msg), { status: res.status });
  }
  return (await res.json()) as InscripcionPorCodigoResult;
}
