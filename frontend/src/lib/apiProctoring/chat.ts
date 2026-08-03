// Chat entre alumno y proctor.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  MensajeChat, AutorChat,
} from '../types';

export const chatApi = {
  /**
   * Envía un mensaje al canal de chat de una sesión (C-15).
   * Real: POST /proctoring/sessions/{id}/chat → 201 {id, autor, texto, creado_en}
   * Mock o fallo: agrega a la lista en memoria y devuelve el mensaje.
   */
  async enviarMensajeChat(
    sessionId: string,
    autor: AutorChat,
    texto: string,
  ): Promise<MensajeChat> {
    return await realFetch<MensajeChat>(
      `/proctoring/sessions/${sessionId}/chat`,
      { method: 'POST', body: JSON.stringify({ autor, texto }) },
      'demo',
    );
  },

  /**
   * Lista los mensajes de chat de una sesión, asc por creado_en (C-15).
   * `desde` (ISO) → polling incremental: solo mensajes con creado_en > desde.
   * Real: GET /proctoring/sessions/{id}/chat?desde=<iso>
   * Mock o fallo: filtra la lista en memoria.
   */
  async listarMensajesChat(sessionId: string, desde?: string): Promise<MensajeChat[]> {
    try {
      const qs = desde ? `?desde=${encodeURIComponent(desde)}` : '';
      return await realFetch<MensajeChat[]>(
        `/proctoring/sessions/${sessionId}/chat${qs}`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 — Pausa autorizada
  // ─────────────────────────────────────────────────────────────────────────,
};
