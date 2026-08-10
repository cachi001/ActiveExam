// Respuestas del alumno y lectura de la sesion.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  SesionProctoringResumen, SesionProctoringDetalle,
} from '../types';

/**
 * Una respuesta del alumno: exactamente uno de los dos campos (C-74 §6).
 * `opcion_elegida_id` para multichoice/truefalse; `respuesta_cloze` (dict
 * blankId → valor) para preguntas cloze/ddwtos.
 */
export type RespuestaEnvio =
  | { pregunta_id: string; opcion_elegida_id: string; respuesta_cloze?: undefined }
  | { pregunta_id: string; respuesta_cloze: Record<string, string>; opcion_elegida_id?: undefined };

export interface RespuestaGuardada {
  pregunta_id: string;
  opcion_elegida_id?: string;
  respuesta_cloze?: Record<string, string>;
}

export const respuestasApi = {
  /**
   * Envía las respuestas del alumno ANTES de finalizar la sesión (C-69 sección 7).
   * El backend calcula la nota server-side a partir de estas respuestas (D8: la
   * corrección y el write-back los origina el backend, nunca el cliente; D3: la
   * opción correcta nunca viaja al cliente).
   *
   * Real: POST /proctoring/sessions/{sessionId}/respuestas
   * Mock o fallo: retorna null sin propagar (degradación silenciosa — NUNCA rompe
   * el cierre del examen). El caller DEBE await-earla antes de finalizar para que
   * la nota pueda computarse, pero un error de red no debe bloquear la entrega.
   *
   * `identidad` (alumno_idnumber/email) es opcional: alimenta el write-back a Moodle
   * (D9). Si se omite, el backend usa la identidad del JWT.
   */
  async enviarRespuestasProctoring(
    sessionId: string,
    respuestas: RespuestaEnvio[],
  ): Promise<{ session_id: string; respuestas_guardadas: number } | null> {
    if (!sessionId) return null;
    try {
      // H4 (seguridad): NO se envía identidad del cliente. El backend usa la
      // identidad del alumno persistida server-side al crear la sesión (JWT);
      // SubmitRespuestasIn rechaza (extra='forbid') cualquier campo extra.
      const body = { respuestas };
      return await realFetch<{ session_id: string; respuestas_guardadas: number }>(
        `/proctoring/sessions/${sessionId}/respuestas`,
        { method: 'POST', body: JSON.stringify(body) },
        'demo',
      );
    } catch (e) {
      // C-72 sección 7: los rechazos de PLAZO se PROPAGAN para que el alumno vea el
      // mensaje (nunca pérdida silenciosa). Otros errores (red, mock) degradan a null
      // para no romper el cierre del examen.
      const code = (e as { code?: string })?.code;
      if (code === 'tiempo_agotado' || code === 'sesion_finalizada') throw e;
      return null;
    }
  },

  /**
   * Obtiene las respuestas YA guardadas de una sesión (vuln reload/restart).
   *
   * Al reanudar una sesión ACTIVA (el backend devuelve la misma sesión ante un
   * reload, en vez de crear una zombie), el cliente usa esto para restaurar el
   * estado `respuestas` de Examen.tsx en vez de volver a arrancar en blanco.
   *
   * Real: GET /proctoring/sessions/{sessionId}/respuestas
   * Mock o fallo: retorna [] (degradación silenciosa — no bloquea el examen;
   * en el peor caso el alumno re-contesta lo que ya había contestado).
   */
  async obtenerRespuestasProctoring(
    sessionId: string,
  ): Promise<RespuestaGuardada[]> {
    if (!sessionId) return [];
    try {
      const data = await realFetch<{
        session_id: string;
        respuestas: RespuestaGuardada[];
      }>(`/proctoring/sessions/${sessionId}/respuestas`, { method: 'GET' }, 'demo');
      return data.respuestas;
    } catch {
      return [];
    }
  },

  /**
   * Obtiene el detalle de una sesión de proctoring (C-64).
   * Real: GET /proctoring/sessions/{sessionId}
   * Mock o fallo: retorna null sin propagar.
   * Alias conveniente de getSesionProctoring para uso desde Cierre.tsx.
   */
  async obtenerSesionProctoring(
    sessionId: string,
  ): Promise<SesionProctoringDetalle | null> {
    if (!sessionId) return null;
    try {
      return await realFetch<SesionProctoringDetalle>(
        `/proctoring/sessions/${sessionId}`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return null;
    }
  },

  /**
   * Lista todas las sesiones de proctoring del backend slim (C-46).
   * Real: GET /proctoring/sessions
   */
  async listarSesionesProctoring(strict = false): Promise<SesionProctoringResumen[]> {
    try {
      return await realFetch<SesionProctoringResumen[]>(
        '/proctoring/sessions',
        { method: 'GET' },
        'demo',
      );
    } catch (e) {
      // `strict` PROPAGA el fallo. Sin él, un error de red devolvía [] y el panel
      // mostraba "0 sesiones registradas": un cero por caída indistinguible de un
      // cero real. Quien no pasa `strict` conserva la degradación tolerante.
      if (strict) throw e;
      return [];
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 — Chat bidireccional proctor↔alumno
  // ─────────────────────────────────────────────────────────────────────────,
};
