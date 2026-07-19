// Métodos de administración (admin_sistema) extraídos de api.ts
// (refactor c-76: partir god-file). Gestión de usuarios, scoring config, detalle de
// usuario, registro público, versiones del texto de consentimiento y config del
// sistema. Se spreadean en `api` (./api); ningún método usa `this`.
import { API_BASE, realFetch, normalizarConsentText } from './apiCore';
import { authProvider } from './authProvider';
import type {
  UsuarioAdmin, ListarUsuariosResponse, EventoScoreConfig, BloqueConsentimiento,
} from './types';

export const adminApi = {
  // -------------------------------------------------------------------------
  // Gestión de usuarios (admin) — C-61 (task 6.4)
  // -------------------------------------------------------------------------

  /**
   * Lista usuarios paginados con filtros server-side (admin_sistema) — C-61 / C-68.
   * Real: GET /users/?rol=&estado=&q=&limit=&offset=
   * Mock: lista demo de 4 usuarios (activos e inactivos) con filtrado local.
   */
  async listarUsuarios(
    limit = 20,
    offset = 0,
    filtros?: { rol?: string; estado?: string; q?: string },
  ): Promise<ListarUsuariosResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filtros?.rol) params.set('rol', filtros.rol);
    if (filtros?.estado) params.set('estado', filtros.estado);
    if (filtros?.q) params.set('q', filtros.q);
    return await realFetch<ListarUsuariosResponse>(
      `/users/?${params.toString()}`,
      { method: 'GET' },
    );
  },

  /**
   * Reactiva un usuario dado de baja (admin_sistema) — C-68.
   * Real: POST /users/{id}/reactivar → usuario reactivado.
   * Mock: no-op (demo sin persistencia real de baja).
   */
  async reactivarUsuario(usuarioId: string): Promise<void> {
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/users/${usuarioId}/reactivar`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  /**
   * Crea un usuario con credencial local (admin_sistema) — C-61.
   * Real: POST /users/
   */
  async crearUsuario(body: {
    id_institucional: string;
    email: string;
    password: string;
    roles: string[];
    nombre?: string;
    apellido?: string;
  }): Promise<UsuarioAdmin> {
    return await realFetch<UsuarioAdmin>(
      '/users/',
      { method: 'POST', body: JSON.stringify(body) },
    );
  },

  /**
   * Edita email, nombre, apellido o roles de un usuario (admin_sistema) — C-61.
   * Real: PUT /users/{usuarioId}
   */
  async editarUsuario(
    usuarioId: string,
    body: { email?: string; nombre?: string; apellido?: string; roles?: string[] },
  ): Promise<UsuarioAdmin> {
    return await realFetch<UsuarioAdmin>(
      `/users/${usuarioId}`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
  },

  /**
   * Da de baja lógica (soft-delete) a un usuario (admin_sistema) — C-61.
   * Real: DELETE /users/{usuarioId} → 204 sin cuerpo.
   */
  async eliminarUsuario(usuarioId: string): Promise<void> {
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/users/${usuarioId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  // -------------------------------------------------------------------------
  // Configuracion de scoring (admin_sistema) — #9 / #10
  // -------------------------------------------------------------------------

  /**
   * Lista los pesos configurados por tipo de evento (admin_sistema).
   * Real: GET /scoring/config
   * Mock: defaults del catalogo.
   */
  /**
   * Devuelve el mapa { tipo_evento: peso } de tipos activos (cualquier usuario
   * autenticado). Lo usa scoringWeights.ts para el calculo de score en vivo.
   * Real: GET /scoring/weights
   * Mock: defaults del catalogo.
   */
  async obtenerScoringWeights(): Promise<{ weights: Record<string, number> }> {
    return await realFetch<{ weights: Record<string, number> }>('/scoring/weights', { method: 'GET' });
  },

  async listarScoringConfig(): Promise<{ items: EventoScoreConfig[] }> {
    return await realFetch<{ items: EventoScoreConfig[] }>('/scoring/config', { method: 'GET' });
  },

  /**
   * Actualiza peso / severidad / descripcion / activo de un tipo (admin_sistema).
   * Real: PATCH /scoring/config/{tipo}
   * Mock: echo con campos sobrescritos.
   */
  async editarScoringConfig(
    tipoEvento: string,
    body: { severidad?: string; peso?: number; descripcion?: string | null; activo?: boolean },
  ): Promise<EventoScoreConfig> {
    return await realFetch<EventoScoreConfig>(
      `/scoring/config/${encodeURIComponent(tipoEvento)}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    );
  },

  // -------------------------------------------------------------------------
  // Detalle de usuario (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Detalle completo de un usuario (admin_sistema) — C-68.
   * Real: GET /users/{id}
   * Mock: busca en el listado demo.
   */
  async obtenerDetalleUsuario(id: string): Promise<UsuarioAdmin & { eliminado_en?: string | null }> {
    return await realFetch<UsuarioAdmin & { eliminado_en?: string | null }>(
      `/users/${id}`,
      { method: 'GET' },
    );
  },

  /**
   * Consentimiento de perfil de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/consent-profile
   * Mock: estado simulado con datos plausibles.
   */
  async obtenerConsentimientoDeUsuario(id: string): Promise<{
    estado: 'otorgado' | 'revocado' | null;
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch<{
      estado: 'otorgado' | 'revocado' | null;
      version_texto: string | null;
      hash_texto: string | null;
      timestamp: string | null;
    }>(`/users/${id}/consent-profile`, { method: 'GET' });
  },

  /**
   * Estado de la referencia biométrica de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/biometria/referencia/estado
   * Mock: estado simulado.
   */
  async obtenerEstadoBiometriaDeUsuario(id: string): Promise<{
    tiene_referencia_vigente: boolean;
    algoritmo: string | null;
    fecha_expiracion: string | null;
    created_at: string | null;
    tiene_foto: boolean;
    foto_hash: string | null;
    foto_created_at: string | null;
  }> {
    return await realFetch<{
      tiene_referencia_vigente: boolean;
      algoritmo: string | null;
      fecha_expiracion: string | null;
      created_at: string | null;
      tiene_foto: boolean;
      foto_hash: string | null;
      foto_created_at: string | null;
    }>(`/users/${id}/biometria/referencia/estado`, { method: 'GET' });
  },

  // -------------------------------------------------------------------------
  // Registro público de estudiantes — C-61 (task 7.3)
  // -------------------------------------------------------------------------

  /**
   * Registro público de un nuevo estudiante (C-61).
   * Real: POST /auth/register → 201 sin token.
   * Mock: 201 simulado.
   */
  async registrarUsuario(body: {
    id_institucional: string;
    nombre: string;
    apellido: string;
    email: string;
    password: string;
    password_confirmacion: string;
  }): Promise<{ id: string; id_institucional: string; email: string }> {
    return await realFetch<{ id: string; id_institucional: string; email: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(body) },
    );
  },

  // -------------------------------------------------------------------------
  // Versiones del texto de consentimiento (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Lista las versiones publicadas del texto de consentimiento (admin_sistema).
   * Real: GET /api/v1/consent/text/versions
   * Mock: devuelve la versión demo como única entrada.
   */
  async listarVersionesConsentimiento(): Promise<{ version: string; hash_texto: string }[]> {
    return await realFetch<{ version: string; hash_texto: string }[]>(
      '/consent/text/versions',
      { method: 'GET' },
    );
  },

  /**
   * Publica una nueva versión del texto de consentimiento (admin_sistema).
   * Real: POST /api/v1/consent/text/versions
   *   body: { version, bloques: [{titulo, cuerpo}] }
   *   → 200 { version, bloques, hash_texto }
   *   → 409 si la versión ya existe
   * Mock: guarda en memoria (actualiza CONSENT_TEXT para la sesión).
   *
   * La versión publicada no se activa hasta hacer PATCH /config { consent_version_vigente }.
   */
  async crearVersionConsentimiento(params: {
    version: string;
    bloques: Array<{ titulo: string; cuerpo: string }>;
  }): Promise<{ version: string; bloques: BloqueConsentimiento[]; hash_texto: string }> {
    const raw = await realFetch<unknown>(
      '/consent/text/versions',
      { method: 'POST', body: JSON.stringify(params) },
    );
    return normalizarConsentText(raw);
  },

  // -------------------------------------------------------------------------
  // Config efectiva del sistema — configuracion-sistema-funcional (ola 2)
  // -------------------------------------------------------------------------

  /**
   * Config efectiva autoritativa (pesos + umbrales + version/ETag).
   * Accesible a cualquier usuario autenticado.
   * Real: GET /api/v1/config/effective
   * Mock: DEFAULT_CONFIG + pesos hardcodeados demo.
   */
  async obtenerConfigEfectiva(): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    scoring_severidades: Record<string, string>;
    // C-69 admin-sync: el backend puede no enviarlos aún (en construcción). Opcionales
    // acá; el cache normaliza a `true` (degradación segura) si vienen ausentes.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
  }> {
    return await realFetch('/config/effective', { method: 'GET' });
  },

  /**
   * Edita los defaults globales de la config del sistema.
   * SOLO admin_sistema con MFA. Invalida el cache del backend.
   * Real: PATCH /api/v1/config
   * Mock: devuelve la config demo sin cambios reales.
   */
  async editarConfigSistema(body: {
    face_absent_ms?: number;
    multiple_faces_frames?: number;
    gaze_deviation_threshold?: number;
    gaze_sustained_ms?: number;
    gaze_fixation_tolerance?: number;
    umbral_cola_revision?: number;
    detectores_activos?: string[];
    retencion_dias_default?: number;
    consent_version_vigente?: string;
    // C-69 admin-sync: habilitar/deshabilitar el chat proctor↔alumno y las pausas
    // solicitadas por el alumno desde la Configuración del sistema.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
  }): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
  }> {
    return await realFetch('/config', { method: 'PATCH', body: JSON.stringify(body) });
  },
};
