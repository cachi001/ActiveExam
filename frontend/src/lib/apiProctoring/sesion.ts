// Ciclo de vida de la sesion: crear, eventos, biometria, finalizar.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  VeredictoReinferencia,
} from '../types';

/** Un evento de detección tal como lo manda el cliente (de a uno o en lote). */
export interface EventoProctoringPayload {
  tipo: string;
  severidad: string;
  ts_cliente: string;
  payload?: Record<string, unknown>;
  screenshot_base64?: string | null;
  face_count_cliente?: number | null;
  /** SHA-256 de la imagen calculado en el cliente (cadena de custodia, c-78). */
  screenshot_sha256_cliente?: string;
}

export const sesionApi = {
  /**
   * Crea una sesión de proctoring en el backend activeexam (C-46).
   * Real: POST /proctoring/sessions
   */
  async crearSesionProctoring(
    modo: string,
    etiqueta?: string,
    examId?: string,
    examenContenidoId?: string | null,
  ): Promise<{ id: string; creada_en: string; examen_contenido_id?: string | null }> {
    // C-69: enviamos examen_contenido_id para que la sesión REGISTRE server-side
    // contra qué examen de contenido (Moodle XML) rinde el alumno. NULLABLE: una
    // sesión de prueba (sin contenido) sigue siendo válida.
    return await realFetch<{ id: string; creada_en: string; examen_contenido_id?: string | null }>(
      '/proctoring/sessions',
      {
        method: 'POST',
        body: JSON.stringify({
          modo,
          etiqueta,
          exam_id: examId,
          examen_contenido_id: examenContenidoId ?? null,
        }),
      },
      'demo',
    );
  },

  /**
   * Envía un evento con screenshot al backend activeexam (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/events
   *
   * PROPAGA el error si el envío falla. No es un detalle de estilo:
   *
   * Hasta c-78 esta función hacía `catch { return null }`, descrito como
   * "fire-and-forget seguro". Pero el llamador NO es fire-and-forget: es el
   * patrón buffer-first del examen (`append → POST → confirm(purgar)`). Como el
   * POST nunca rechazaba, el `confirm` corría SIEMPRE, incluso con la red caída:
   * **el buffer de IndexedDB se vaciaba solo en cada evento y el replay no
   * encontraba nunca nada que reenviar.** La resiliencia ante cortes era
   * decorativa. Quien decide qué hacer con un fallo es el llamador, que tiene el
   * buffer; esta capa solo informa la verdad.
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 — se transmite solo al backend;
   * nunca se loguea ni se persiste en almacenamiento local.
   */
  async enviarEventoProctoring(
    sessionId: string,
    payload: {
      tipo: string;
      severidad: string;
      ts_cliente: string;
      payload?: Record<string, unknown>;
      screenshot_base64?: string | null;
      face_count_cliente?: number | null;
      /** SHA-256 de la imagen calculado en el cliente (cadena de custodia, c-78). */
      screenshot_sha256_cliente?: string;
    },
  ): Promise<{
    evento_id: string;
    veredicto_reinferencia: VeredictoReinferencia;
    face_count_servidor: number;
    screenshot_sha256: string;
  }> {
    // El backend usa severidad en masculino (bajo|medio|alto|critico); el frontend
    // la maneja en femenino (baja|media|alta|critica) + baseline. Sin este mapeo el
    // POST da 422 y el evento se pierde en silencio (parece "sin red"/mock).
    const SEVERIDAD_BACKEND: Record<string, string> = {
      baseline: 'bajo', baja: 'bajo', media: 'medio', alta: 'alto', critica: 'critico',
    };
    const body = { ...payload, severidad: SEVERIDAD_BACKEND[payload.severidad] ?? payload.severidad };
    return await realFetch<{
      evento_id: string;
      veredicto_reinferencia: VeredictoReinferencia;
      face_count_servidor: number;
      screenshot_sha256: string;
    }>(
      `/proctoring/sessions/${sessionId}/events`,
      { method: 'POST', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Envía un LOTE de eventos en un solo request (c-78 §16.1f).
   * Real: POST /proctoring/sessions/{sessionId}/events/lote
   *
   * Es el camino del DRENAJE al reconectar. De a uno, drenar una caída de 30 s
   * tardaba 35,6 s de media contra Render (medido el 26/8/2026): el plan free
   * responde a 3 a 5 s por request y el drenaje los paga en serie.
   *
   * El orden del array es el orden de producción y se respeta; el ack vuelve en
   * la misma posición. PROPAGA el error, igual que el envío de a uno: dar por
   * enviado un lote que no llegó vaciaría el buffer sin haber mandado nada.
   */
  async enviarEventosProctoringEnLote(
    sessionId: string,
    eventos: EventoProctoringPayload[],
  ): Promise<{
    resultados: {
      evento_id: string;
      veredicto_reinferencia: VeredictoReinferencia;
      face_count_servidor: number | null;
      screenshot_sha256: string | null;
    }[];
  }> {
    // Mismo mapeo de severidad que el envío de a uno: en femenino del lado del
    // frontend, en masculino del lado del backend. Sin esto el lote entero da
    // 422 y el drenaje no avanza nunca.
    const SEVERIDAD_BACKEND: Record<string, string> = {
      baseline: 'bajo', baja: 'bajo', media: 'medio', alta: 'alto', critica: 'critico',
    };
    const body = {
      eventos: eventos.map((e) => ({
        ...e,
        severidad: SEVERIDAD_BACKEND[e.severidad] ?? e.severidad,
      })),
    };
    return await realFetch<{
      resultados: {
        evento_id: string;
        veredicto_reinferencia: VeredictoReinferencia;
        face_count_servidor: number | null;
        screenshot_sha256: string | null;
      }[];
    }>(
      `/proctoring/sessions/${sessionId}/events/lote`,
      { method: 'POST', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Envía el resultado de la verificación biométrica al backend activeexam (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/biometria
   *
   * PROPAGA el error. Era el peor de los tres casos de c-78: con la red caída
   * devolvía `{ ok: true }` — afirmaba éxito — y el llamador borraba el payload
   * de la verificación de identidad del alumno dándolo por entregado. Esa
   * verificación no volvía nunca más.
   */
  async enviarBiometriaProctoring(
    sessionId: string,
    bio: {
      liveness_ok: boolean;
      retos_resueltos: string[];
      embedding?: number[];
      resultado: string;
    },
  ): Promise<{ ok: boolean }> {
    // El backend espera `embedding` como STRING (columna Text, dato sensible).
    // El cliente lo arma como number[] → serializamos a JSON string. Sin esto el
    // backend devolvía 422 y la verificación biométrica NO se guardaba en la sesión.
    const payload = {
      liveness_ok: bio.liveness_ok,
      retos_resueltos: bio.retos_resueltos,
      resultado: bio.resultado,
      ...(bio.embedding !== undefined ? { embedding: JSON.stringify(bio.embedding) } : {}),
    };
    return await realFetch<{ ok: boolean }>(
      `/proctoring/sessions/${sessionId}/biometria`,
      { method: 'POST', body: JSON.stringify(payload) },
      'demo',
    );
  },

  /**
   * Finaliza una sesión de proctoring (C-64).
   * Real: PATCH /proctoring/sessions/{sessionId}/finalizar
   *
   * PROPAGA el error. Una finalización que falla en silencio deja la sesión
   * "en vivo" para siempre en el panel del proctor (el panel filtra por
   * `finalizada_en IS NULL`). El backstop es `auto_finalizacion` server-side,
   * pero el llamador tiene que poder enterarse y reintentar.
   *
   * Devuelve null SOLO cuando no hay `sessionId`: ahí no hay nada que finalizar
   * y no es un fallo.
   */
  async finalizarSesionProctoring(
    sessionId: string,
  ): Promise<{ id: string; finalizada_en: string } | null> {
    if (!sessionId) return null;
    return await realFetch<{ id: string; finalizada_en: string }>(
      `/proctoring/sessions/${sessionId}/finalizar`,
      { method: 'PATCH' },
      'demo',
    );
  },
};
