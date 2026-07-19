// Métodos de proctoring del objeto `api` (refactor c-76): sesión, eventos, chat,
// pausa, observaciones, cierre forzado, revisión. Se componen en ./api.
import { realFetch, API_BASE } from './apiCore';
import { authProvider } from './authProvider';
import type {
  SesionProctoringResumen, SesionProctoringDetalle, VeredictoReinferencia,
  MensajeChat, AutorChat, Pausa, AccionPausa, PausaPendiente, ObservacionProctor, CierreForzado,
  DecisionRevision, DecisionResolucion,
} from './types';

export const proctoringApi = {
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
    respuestas: { pregunta_id: string; opcion_elegida_id: string }[],
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
  ): Promise<{ pregunta_id: string; opcion_elegida_id: string }[]> {
    if (!sessionId) return [];
    try {
      const data = await realFetch<{
        session_id: string;
        respuestas: { pregunta_id: string; opcion_elegida_id: string }[];
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
  async listarSesionesProctoring(): Promise<SesionProctoringResumen[]> {
    try {
      return await realFetch<SesionProctoringResumen[]>(
        '/proctoring/sessions',
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 — Chat bidireccional proctor↔alumno
  // ─────────────────────────────────────────────────────────────────────────

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
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * El alumno solicita una pausa (C-15).
   * Real: POST /proctoring/sessions/{id}/pausas → 201 pausa 'solicitada'
   * Mock o fallo: crea la pausa en memoria.
   */
  async solicitarPausa(sessionId: string, motivo: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/sessions/${sessionId}/pausas`,
      { method: 'POST', body: JSON.stringify({ motivo }) },
      'demo',
    );
  },

  /**
   * Lista las pausas de una sesión, desc por solicitada_en (C-15).
   * La más reciente queda primera (lo que el poll del alumno necesita).
   * Real: GET /proctoring/sessions/{id}/pausas
   * Mock o fallo: lista en memoria ordenada desc.
   */
  async listarPausas(sessionId: string): Promise<Pausa[]> {
    try {
      return await realFetch<Pausa[]>(
        `/proctoring/sessions/${sessionId}/pausas`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Lista las pausas pendientes de TODAS las sesiones (C-15) — poll del proctor.
   * Solo estado 'solicitada', asc por solicitada_en.
   * Real: GET /proctoring/pausas/pendientes
   * Mock o fallo: arma la cola desde el estado en memoria.
   */
  async listarPausasPendientes(): Promise<PausaPendiente[]> {
    try {
      return await realFetch<PausaPendiente[]>(
        '/proctoring/pausas/pendientes',
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * El proctor resuelve una pausa solicitada: aprobar o rechazar (C-15).
   * Real: PATCH /proctoring/pausas/{id} → 200 pausa actualizada; 409 si ya no
   *       está 'solicitada' (otra resolución ganó la carrera).
   * Mock o fallo: muta la pausa en memoria; lanza Error con .status=409 si ya
   *       no estaba 'solicitada' para que la UI maneje el caso igual que en real.
   */
  async resolverPausa(
    pausaId: string,
    accion: AccionPausa,
    proctorActor?: string | null,
    motivoRechazo?: string | null,
  ): Promise<Pausa> {
    // El motivo solo viaja al rechazar (al aprobar el backend lo ignora/None).
    const body: Record<string, unknown> = {
      accion,
      proctor_actor: proctorActor ?? null,
    };
    if (accion === 'rechazar') body.motivo_rechazo = motivoRechazo ?? null;
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Finaliza una pausa aprobada (el alumno reanuda el examen) (C-15).
   * Real: PATCH /proctoring/pausas/{id}/finalizar → 200 pausa 'finalizada';
   *       409 si no estaba 'aprobada'.
   * Mock o fallo: muta la pausa en memoria.
   */
  async finalizarPausa(pausaId: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}/finalizar`,
      { method: 'PATCH' },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 (3.2 / 3.3) — Acciones del proctor: observaciones + cierre forzado
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * El proctor registra una observación sobre la sesión (C-15 3.2) — insumo de C-16.
   * Real: POST /proctoring/sessions/{id}/observaciones → 201
   * Mock o fallo: agrega la observación en memoria.
   */
  async crearObservacionProctor(
    sessionId: string,
    texto: string,
    proctorActor?: string | null,
  ): Promise<ObservacionProctor> {
    return await realFetch<ObservacionProctor>(
      `/proctoring/sessions/${sessionId}/observaciones`,
      { method: 'POST', body: JSON.stringify({ texto, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  /**
   * Lista las observaciones del proctor de una sesión, asc por creada_en (C-15 3.2).
   * Real: GET /proctoring/sessions/{id}/observaciones
   * Mock o fallo: lista en memoria.
   */
  async listarObservacionesProctor(sessionId: string): Promise<ObservacionProctor[]> {
    try {
      return await realFetch<ObservacionProctor[]>(
        `/proctoring/sessions/${sessionId}/observaciones`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Cierre FORZADO de una sesión por el proctor (C-15 3.3). Operativo, NO
   * disciplinario (L2.5). Idempotente: preserva el audit del primer cierre.
   * Real: PATCH /proctoring/sessions/{id}/cerrar-forzado → 200
   * Mock o fallo: simula el cierre.
   */
  async cerrarSesionForzado(
    sessionId: string,
    motivo: string,
    proctorActor?: string | null,
  ): Promise<CierreForzado> {
    return await realFetch<CierreForzado>(
      `/proctoring/sessions/${sessionId}/cerrar-forzado`,
      { method: 'PATCH', body: JSON.stringify({ motivo, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-71 slice 2 — Decisión del revisor (dos fases). El sistema NUNCA sanciona
  // automáticamente (L2.5, regla #5): estos endpoints registran el juicio humano
  // de forma INMUTABLE (RN-RV-07). Un segundo intento devuelve 409.
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Registra la decisión de REVISIÓN (fase 1) sobre una sesión (capacidad `revisar_sesion`).
   * Real: POST /review/session/{id}/decide → 200; 409 si ya había decisión (inmutable).
   * El `motivo` viaja como `observaciones`: el fundamento queda en el audit inmutable.
   * `caso_abierto` deriva a la fase 2 (no valida ni anula la nota).
   */
  async decidirRevision(
    sessionId: string,
    decision: DecisionRevision,
    motivo: string,
  ): Promise<{ session_id: string; previous: string; new: string; actor: string; decision_at: string }> {
    return await realFetch(
      `/review/session/${sessionId}/decide`,
      { method: 'POST', body: JSON.stringify({ decision, observaciones: motivo }) },
    );
  },

  /**
   * Registra el VEREDICTO de resolución (fase 2) de un caso abierto (capacidad `resolver_caso`).
   * Real: POST /review/session/{id}/resolve → 200; 409 si ya resuelto o el caso no está abierto.
   * `motivo` obligatorio; `evidenciaRef` obligatorio si `anulado_por_fraude` (D11).
   */
  async resolverCaso(
    sessionId: string,
    resolucion: DecisionResolucion,
    motivo: string,
    evidenciaRef?: string,
  ): Promise<{ session_id: string; resolucion: string; actor: string; resolucion_at: string; nota_anulada: boolean }> {
    return await realFetch(
      `/review/session/${sessionId}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolucion, motivo, evidencia_ref: evidenciaRef ?? null }),
      },
    );
  },

  /**
   * Obtiene el detalle completo de una sesión de proctoring (C-46).
   * Real: GET /proctoring/sessions/{id}
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 en los eventos — no loguear.
   */
  async getSesionProctoring(id: string): Promise<SesionProctoringDetalle> {
    return await realFetch<SesionProctoringDetalle>(
      `/proctoring/sessions/${id}`,
      { method: 'GET' },
      'demo',
    );
  },

  /**
   * Elimina una sesión de proctoring (C-46). Real: DELETE /proctoring/sessions/{id} (204).
   * Fallo de red: retorna { ok:false } sin romper.
   */
  async eliminarSesionProctoring(id: string): Promise<{ ok: boolean }> {
    try {
      const token = authProvider.getToken();
      const res = await fetch(`${API_BASE}/proctoring/sessions/${id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      return { ok: res.ok };
    } catch {
      return { ok: false };
    }
  },
};
