/**
 * Cliente de API de rendición de examen (C-69, D3).
 *
 * Fetch de preguntas y opciones para el alumno que rinde.
 * D3 (regla dura #6): la opción correcta NUNCA viaja al cliente.
 * La opción correcta sólo vive server-side; sólo se usa para corrección.
 *
 * Auth: el endpoint GET /api/v1/exam-content/{id} requiere principal autenticado.
 * Se inyecta el token desde authProvider para evitar 401 en modo real.
 */

import { authProvider } from './authProvider';

/** Opción de respuesta para la rendición (D3: campo de respuesta correcta ausente). */
export interface OpcionRendicion {
  id: string;
  texto: string;
  orden: number;
}

/** Pregunta proyectada para la rendición. */
export interface PreguntaRendicion {
  id: string;
  enunciado: string;
  tipo: string;
  orden: number;
  opciones: OpcionRendicion[];
}

/** Examen proyectado para la rendición (sin opciones correctas). */
export interface ExamenRendicion {
  id: string;
  titulo: string;
  preguntas: PreguntaRendicion[];
}

/**
 * Obtiene las preguntas del examen para la rendición del alumno.
 * D3: la respuesta jamás incluye el campo de respuesta correcta (regla dura).
 *
 * @param examenContenidoId - ID del ExamenContenido en la DB.
 * @returns ExamenRendicion con preguntas en orden estable, o null si no existe.
 */
export async function fetchExamenParaRendir(
  examenContenidoId: string,
): Promise<ExamenRendicion | null> {
  const token = authProvider.getToken();
  const res = await fetch(`/api/v1/exam-content/${examenContenidoId}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Error al cargar el examen de contenido: HTTP ${res.status}`);
  }
  return res.json() as Promise<ExamenRendicion>;
}
