/**
 * Cliente de navegación del catálogo académico (C-69) — datos REALES.
 *
 * Funciones puras que pegan al backend real para que el alumno navegue
 * materia → comisión → examen importado. Inyectan apiBase + token para tests.
 * Degradación silenciosa: ante error de red/servidor devuelven [] (no rompen el flujo).
 * D3: la respuesta de exámenes NUNCA incluye es_correcta ni opciones.
 */

import type { Materia, Comision, ExamenContenidoResumen } from './types';

function buildHeaders(token: string | undefined): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function getJson<T>(url: string, token: string | undefined): Promise<T[]> {
  try {
    const res = await fetch(url, { method: 'GET', headers: buildHeaders(token) });
    if (!res.ok) return [];
    return (await res.json()) as T[];
  } catch {
    return [];
  }
}

/** GET /exam-content/materias → materias disponibles ({id, codigo, nombre}). */
export function listarMateriasFn(
  apiBase: string,
  token: string | undefined,
): Promise<Materia[]> {
  return getJson<Materia>(`${apiBase}/exam-content/materias`, token);
}

/** GET /exam-content/materias/{materiaId}/comisiones → comisiones de la materia. */
export function listarComisionesFn(
  apiBase: string,
  token: string | undefined,
  materiaId: string,
): Promise<Comision[]> {
  return getJson<Comision>(
    `${apiBase}/exam-content/materias/${encodeURIComponent(materiaId)}/comisiones`,
    token,
  );
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
