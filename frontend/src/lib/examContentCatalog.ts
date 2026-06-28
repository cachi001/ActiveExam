/**
 * Cliente de catálogo de exámenes de contenido (C-69).
 *
 * Función pura para listar los exámenes importados desde Moodle XML.
 * Testeable de forma aislada (exporta la función raw con parámetros inyectables).
 * D3: la respuesta NUNCA incluye es_correcta ni opciones — solo metadatos.
 */

import type { ExamenContenidoResumen } from './types';

/**
 * Función pura que llama a GET /exam-content y devuelve la lista.
 * Exportada para tests unitarios — permite inyectar apiBase y token.
 *
 * @param apiBase  - Base de la API (ej: '/api/v1')
 * @param token    - JWT de acceso (undefined si no hay sesión)
 * @returns Lista de exámenes importados, o [] si hay error de red/servidor.
 */
export async function listarExamenesContenidoFn(
  apiBase: string,
  token: string | undefined,
): Promise<ExamenContenidoResumen[]> {
  try {
    const res = await fetch(`${apiBase}/exam-content`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) return [];
    return (await res.json()) as ExamenContenidoResumen[];
  } catch {
    // Error de red o de parseo: degradación silenciosa (no bloquea el flujo).
    return [];
  }
}
