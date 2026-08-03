// Capa de API del MVP — objeto `api`. Los internos (realFetch, estado demo,
// data mock, helpers) viven en ./apiCore (refactor c-76: partir god-file).
import type {
  ConsentTextResponse, ConsentResponse, Examen,
  EventoSesion,
  Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  MensajeChat, AutorChat, Pausa, AccionPausa, PausaPendiente,
  UsuarioAdmin, ListarUsuariosResponse,
  EventoScoreConfig,
  ExamenContenidoResumen,
} from './types';
import { authProvider } from './authProvider';
import {
  API_BASE,
  delay, realFetch, commitEnrollment,
  _estadosViaAlternativa, normalizarConsentText,
  consentVersionVigente, setConsentVersionVigente,
  enrollmentAlumno,
} from './apiCore';
import { proctoringApi } from './apiProctoring';
import { adminApi } from './apiAdmin';
import { enrollmentApi } from './apiEnrollment';
import { alumnoApi } from './apiAlumno';

// Re-export para compat: consumidores importaban estos desde './api'.
export {
  API_BASE, DESAFIOS,
  BIOMETRIC_VALIDITY_MONTHS, ENABLE_DNI_SCAN, resetEnrollmentCache,
} from './apiCore';

export const api = {
  async getConsentText(token = 'demo'): Promise<ConsentTextResponse> {
    // El backend devuelve `bloques` como dict[str, str]; normalizamos a array.
    const texto = normalizarConsentText(await realFetch<unknown>('/consent/text', { method: 'GET' }, token));
    // Sincronizar la versión vigente para el gate de perfil (evita falso "renovación").
    setConsentVersionVigente(texto.version || consentVersionVigente());
    return texto;
  },

  async recordConsent(examId: string, token = 'demo'): Promise<ConsentResponse> {
    return await realFetch<ConsentResponse>('/consent', {
      method: 'POST',
      body: JSON.stringify({ exam_id: examId, version_texto: consentVersionVigente(), affirmative_action: true }),
    }, token);
  },

  /**
   * Consulta el estado de la referencia biométrica del usuario autenticado (C-59).
   *
   * Real (USE_REAL_BACKEND=1): GET /proctoring/biometria/referencia/estado
   *   El backend identifica al usuario por JWT y devuelve si tiene referencia vigente.
   *   La respuesta SOLO contiene el booleano; NUNCA el embedding ni el referencia_id
   *   (Ley 25.326, regla dura #7).
   *
   * Demo (USE_REAL_BACKEND=0): deriva de enrollmentAlumno.biometria?.captura_completada.
   *
   * Usar este endpoint para el gate de enrollment en el frontend ANTES de intentar
   * la verificación (evita capturar el embedding vivo solo para descubrir que no hay ref).
   */
  async estadoReferenciaBiometrica(): Promise<{ tiene_referencia_vigente: boolean }> {
    try {
      return await realFetch<{ tiene_referencia_vigente: boolean }>(
        '/proctoring/biometria/referencia/estado',
        { method: 'GET' },
      );
    } catch {
      // Si el endpoint falla (ej. red), asumir sin referencia para no bloquear.
      return { tiene_referencia_vigente: false };
    }
  },

  /**
   * Verificación biométrica 1:1 server-side (C-59, rama REAL).
   *
   * Real (USE_REAL_BACKEND=1): POST /proctoring/biometria/verificar-referencia
   *   body: { embedding_vivo, umbral? }
   *   El backend identifica al usuario por JWT, busca la referencia vigente en DB,
   *   la descifra server-side y compara. El embedding de referencia NUNCA viaja al
   *   cliente (Ley 25.326, regla dura #7).
   *   resp: { distancia, es_match, umbral }
   *   - 404: sin referencia vigente -> señal de no_enrolado (distinto de error de red).
   *   - 422: embedding_vivo de dimensión inválida.
   *   - 500: error interno de descifrado.
   *
   * DATO SENSIBLE (Ley 25.326): el embedding_vivo NO se loguea.
   */
  async verificarBiometriaReferencia(
    embeddingVivo: number[],
    umbral?: number,
  ): Promise<{ distancia: number; es_match: boolean; umbral: number }> {
    // No hace try/catch: propaga el error para que el caller distinga:
    //   - Error('HTTP 404') -> sin referencia vigente -> fase no_enrolado
    //   - Error('HTTP 422') -> embedding invalido
    //   - Error('HTTP 500') -> error interno de descifrado
    //   - Otros -> error de red
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/proctoring/biometria/verificar-referencia`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        embedding_vivo: embeddingVivo,
        umbral: umbral ?? null,
      }),
    });
    if (!res.ok) {
      // Lanza un error con el status HTTP para que Biometria.tsx pueda distinguir 404.
      const err = new Error(`HTTP ${res.status}`) as Error & { status: number };
      err.status = res.status;
      throw err;
    }
    return res.json() as Promise<{ distancia: number; es_match: boolean; umbral: number }>;
  },

  /**
   * Verificación biométrica 1:1 — dos ramas (real vs demo).
   *
   * RAMA REAL (USE_REAL_BACKEND=1):
   *   Llama a verificarBiometriaReferencia (POST /proctoring/biometria/verificar-referencia).
   *   Solo se envía el embedding_vivo; el backend identifica al usuario por JWT.
   *   embeddingReferencia se IGNORA en modo real (es null por diseño en C-56).
   *
   * RAMA DEMO (USE_REAL_BACKEND=0):
   *   Calcula la distancia coseno LOCALMENTE entre los dos descriptores 128-d.
   *   embeddingReferencia debe estar presente en el cliente (capturado en enrollment demo).
   *
   * DATO SENSIBLE (Ley 25.326): los embeddings NO se loguean.
   *
   * @deprecated Para modo real preferir verificarBiometriaReferencia directamente.
   *   Este método conserva retrocompat con el flujo demo existente.
   */
  async verificarBiometria(
    embeddingVivo: number[],
    _embeddingReferencia: number[],
    umbral?: number,
  ): Promise<{ distancia: number; es_match: boolean; umbral: number } | null> {
    // Rama real (C-59): solo envía el embedding vivo; el backend hace el resto.
    // embeddingReferencia se ignora intencionalmente (es null en modo real, C-56).
    try {
      return await this.verificarBiometriaReferencia(embeddingVivo, umbral);
    } catch {
      return null;
    }
  },

  /** No hay catálogo de exámenes "rendibles" server-side; los callers toleran undefined. */
  async getExam(_id: string): Promise<Examen | undefined> { return undefined; },

  ...alumnoApi,
  ...enrollmentApi,

  // -------------------------------------------------------------------------
  // Backend slim de proctoring — C-46
  // Todos los métodos llaman al backend slim C-45.
  // -------------------------------------------------------------------------

  // Proctoring / chat / pausa / revisión → ./apiProctoring (refactor c-76)
  ...proctoringApi,

  // -------------------------------------------------------------------------
  // Foto de perfil — C-61 (task 5.1)
  // -------------------------------------------------------------------------

  /**
   * Obtiene la foto de perfil del usuario autenticado (C-61).
   * Real: GET /enrollment/foto-perfil → { imagen_base64: string }
   * Mock: retorna null (sin foto demo).
   */
  async obtenerFotoPerfil(): Promise<string | null> {
    try {
      const data = await realFetch<{ imagen_base64: string }>(
        '/enrollment/foto-perfil',
        { method: 'GET' },
      );
      return data.imagen_base64;
    } catch {
      return null;
    }
  },

  /**
   * Obtiene la foto de perfil de un usuario específico (admin/proctor) — C-61.
   * Real: GET /enrollment/foto-perfil/{usuario_id} → { imagen_base64: string }
   * Mock: retorna null.
   */
  async obtenerFotoPerfilDeUsuario(usuarioId: string): Promise<string | null> {
    try {
      const data = await realFetch<{ imagen_base64: string }>(
        `/enrollment/foto-perfil/${usuarioId}`,
        { method: 'GET' },
      );
      return data.imagen_base64;
    } catch {
      return null;
    }
  },

  ...adminApi,

  // -------------------------------------------------------------------------
  // Consentimiento de perfil persistido server-side — configuracion-sistema-funcional (ola 2)
  // -------------------------------------------------------------------------

  /**
   * Otorga el consentimiento de perfil (acción afirmativa explícita, RN-CO-02).
   * Real: POST /api/v1/consent/profile
   * Demo: registra localmente (no persiste server-side).
   *
   * REEMPLAZA la implementación anterior que solo guardaba en localStorage.
   */
  async registrarConsentimientoPerfil(versionTexto: string, viaAlternativa = false): Promise<AcuseConsentimiento> {
    if (!viaAlternativa) {
      // Consentimiento directo: POST al backend server-side (Ley 25.326, append-only).
      const data = await realFetch<{
        estado: string;
        version_texto: string | null;
        hash_texto: string | null;
        timestamp: string | null;
      }>('/consent/profile', {
        method: 'POST',
        body: JSON.stringify({ version_texto: versionTexto, affirmative_action: true }),
      });
      const acuse: AcuseConsentimiento = {
        version: data.version_texto ?? versionTexto,
        timestamp: data.timestamp ?? new Date().toISOString(),
        hash: data.hash_texto ? `sha256:${data.hash_texto}` : '',
        via_alternativa: false,
      };
      commitEnrollment({ ...enrollmentAlumno, consentimiento: acuse });
      return acuse;
    }
    // Demo / vía alternativa: comportamiento original (hash simulado local)
    await delay(400);
    const acuse: AcuseConsentimiento = {
      version: versionTexto,
      timestamp: new Date().toISOString(),
      hash: 'sha256:' + Math.random().toString(16).slice(2, 18),
      via_alternativa: viaAlternativa,
    };
    commitEnrollment({ ...enrollmentAlumno, consentimiento: acuse });
    return acuse;
  },

  /**
   * Estado vigente del consentimiento de perfil del usuario autenticado.
   * Real: GET /api/v1/consent/profile
   * Demo: lee el enrollment local.
   */
  async estadoConsentimientoPerfil(): Promise<{
    estado: 'otorgado' | 'revocado' | 'inexistente';
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch('/consent/profile', { method: 'GET' });
  },

  // -------------------------------------------------------------------------
  // Catálogo de exámenes de contenido importados (C-69)
  // -------------------------------------------------------------------------

  /**
   * Lista los exámenes de contenido importados desde Moodle XML (C-69).
   *
   * GET /api/v1/exam-content → [{id, titulo, cantidad_preguntas}] en orden alfabético.
   *   Cualquier principal autenticado puede consultar el catálogo.
   *   D3: es_correcta NUNCA en la respuesta.
   *
   * Degradación silenciosa: un error de red retorna [] sin propagar (lo maneja
   * listarExamenesContenidoFn).
   */
  async listarExamenesContenido(strict = false): Promise<ExamenContenidoResumen[]> {
    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const token = authProvider.getToken();
    return listarExamenesContenidoFn(API_BASE, token, strict);
  },

  /**
   * Revoca el consentimiento de perfil (inserta estado revocado, preserva histórico).
   * Real: POST /api/v1/consent/profile/revoke
   * Demo: simula estado revocado.
   */
  async revocarConsentimientoPerfil(): Promise<{
    estado: string;
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch('/consent/profile/revoke', { method: 'POST' });
  },
};

// Helpers de presentación (definidos en ./apiLabels; re-export para compat).
export { DESC_EVENTO, descripcionEvento, SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from './apiLabels';

export type {
  EventoSesion, Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  // C-46: tipos de proctoring (re-export desde types.ts)
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  // C-15: chat + pausa autorizada (re-export desde types.ts)
  MensajeChat, AutorChat, Pausa, AccionPausa, PausaPendiente,
  // C-61: gestión de usuarios
  UsuarioAdmin, ListarUsuariosResponse,
  // #10: scoring config
  EventoScoreConfig,
};
