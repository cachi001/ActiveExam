// Ciclo de vida de la sesion: crear, eventos, biometria, finalizar.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  VeredictoReinferencia,
} from '../types';

export const sesionApi = {
  /**
   * Crea una sesión de proctoring en el backend slim (C-46).
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
   * Envía un evento con screenshot al backend slim (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/events
   * Mock o fallo: retorna null sin propagar (fire-and-forget seguro)
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
    },
  ): Promise<{
    evento_id: string;
    veredicto_reinferencia: VeredictoReinferencia;
    face_count_servidor: number;
    screenshot_sha256: string;
  } | null> {
    // El backend usa severidad en masculino (bajo|medio|alto|critico); el frontend
    // la maneja en femenino (baja|media|alta|critica) + baseline. Sin este mapeo el
    // POST da 422 y el evento se pierde en silencio (parece "sin red"/mock).
    const SEVERIDAD_BACKEND: Record<string, string> = {
      baseline: 'bajo', baja: 'bajo', media: 'medio', alta: 'alto', critica: 'critico',
    };
    const body = { ...payload, severidad: SEVERIDAD_BACKEND[payload.severidad] ?? payload.severidad };
    try {
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
    } catch {
      return null;
    }
  },

  /**
   * Envía el resultado de la verificación biométrica al backend slim (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/biometria
   * Mock o fallo: retorna { ok: true } con delay 150ms (fire-and-forget)
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
    try {
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
    } catch {
      return { ok: true };
    }
  },

  /**
   * Finaliza una sesión de proctoring (C-64).
   * Real: PATCH /proctoring/sessions/{sessionId}/finalizar
   * Mock o fallo: retorna null sin propagar (fire-and-forget seguro).
   */
  async finalizarSesionProctoring(
    sessionId: string,
  ): Promise<{ id: string; finalizada_en: string } | null> {
    if (!sessionId) return null;
    try {
      return await realFetch<{ id: string; finalizada_en: string }>(
        `/proctoring/sessions/${sessionId}/finalizar`,
        { method: 'PATCH' },
        'demo',
      );
    } catch {
      return null;
    }
  },
};
