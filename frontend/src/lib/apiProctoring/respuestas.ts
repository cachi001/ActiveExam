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
   *
   * PROPAGA el error (c-78). Antes degradaba a `null` todo lo que no fuera un 409
   * de plazo, y eso dejaba MUERTO el manejo de error de los dos llamadores de
   * `Examen.tsx`:
   *
   *   - `entregar()` tiene una rama explícita para el error de red en la entrega
   *     manual — "revertir para permitir reintento, no finalizamos", con el
   *     comentario "terminarle el examen sin haber guardado nada sería el peor
   *     resultado posible". Como esto nunca lanzaba por red, esa rama no corría
   *     jamás: el examen se finalizaba igual, con las respuestas sin llegar.
   *   - El autoguardado enciende `guardadoEnRiesgo` para avisarle al alumno. Como
   *     el POST resolvía con `null` en vez de rechazar, corría el `.then` y el
   *     aviso se APAGABA justo cuando había que encenderlo.
   *
   * Quien decide qué hacer con el fallo es la pantalla, que sabe si es una entrega
   * manual (reintentable) o por tiempo agotado (best-effort). Esta capa informa.
   *
   * Devuelve null SOLO sin `sessionId`: ahí no hay nada que mandar.
   *
   * `identidad` (alumno_idnumber/email) es opcional: alimenta el write-back a Moodle
   * (D9). Si se omite, el backend usa la identidad del JWT.
   */
  async enviarRespuestasProctoring(
    sessionId: string,
    respuestas: RespuestaEnvio[],
  ): Promise<{ session_id: string; respuestas_guardadas: number } | null> {
    if (!sessionId) return null;
    // H4 (seguridad): NO se envía identidad del cliente. El backend usa la
    // identidad del alumno persistida server-side al crear la sesión (JWT);
    // SubmitRespuestasIn rechaza (extra='forbid') cualquier campo extra.
    const body = { respuestas };
    return await realFetch<{ session_id: string; respuestas_guardadas: number }>(
      `/proctoring/sessions/${sessionId}/respuestas`,
      { method: 'POST', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Obtiene las respuestas YA guardadas de una sesión (vuln reload/restart).
   *
   * Al reanudar una sesión ACTIVA (el backend devuelve la misma sesión ante un
   * reload, en vez de crear una zombie), el cliente usa esto para restaurar el
   * estado `respuestas` de Examen.tsx en vez de volver a arrancar en blanco.
   *
   * Real: GET /proctoring/sessions/{sessionId}/respuestas
   *
   * PROPAGA el error (c-78). Devolver `[]` ante un fallo de red decía "no
   * contestaste nada": el alumno que recargaba la página a mitad del examen veía
   * un examen EN BLANCO aunque el servidor tuviera sus respuestas, y lo empujaba
   * a contestar todo de nuevo. Es la misma clase de mentira que el resto de las
   * pantallas que muestran "no hay nada" ante un error.
   *
   * Devuelve [] SOLO sin `sessionId`: ahí no hay nada que restaurar.
   */
  async obtenerRespuestasProctoring(
    sessionId: string,
  ): Promise<RespuestaGuardada[]> {
    if (!sessionId) return [];
    const data = await realFetch<{
      session_id: string;
      respuestas: RespuestaGuardada[];
    }>(`/proctoring/sessions/${sessionId}/respuestas`, { method: 'GET' }, 'demo');
    return data.respuestas;
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
   * Lista todas las sesiones de proctoring del backend activeexam (C-46).
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
