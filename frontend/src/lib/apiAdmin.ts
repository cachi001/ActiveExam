// Métodos de administración (admin_sistema) extraídos de api.ts
// (refactor c-76: partir god-file). Gestión de usuarios, scoring config, detalle de
// usuario, registro público, versiones del texto de consentimiento y config del
// sistema. Se spreadean en `api` (./api); ningún método usa `this`.
import { API_BASE, realFetch, normalizarConsentText } from './apiCore';
import { authProvider } from './authProvider';
import type {
  UsuarioAdmin, ListarUsuariosResponse, EventoScoreConfig, BloqueConsentimiento,
  ResumenStats, FiltrosStats, AuditLogResponse, AuditFiltros,
} from './types';

/** Query string de los filtros de stats (omite las claves vacías). */
function statsQuery(filtros?: FiltrosStats): string {
  if (!filtros) return '';
  const p = new URLSearchParams();
  if (filtros.materia_id) p.set('materia_id', filtros.materia_id);
  if (filtros.comision_id) p.set('comision_id', filtros.comision_id);
  if (filtros.examen_id) p.set('examen_id', filtros.examen_id);
  if (filtros.desde) p.set('desde', filtros.desde);
  if (filtros.hasta) p.set('hasta', filtros.hasta);
  const s = p.toString();
  return s ? `?${s}` : '';
}

/** Descarga autenticada de un export de stats (PDF/Excel) como Blob. Un fallo se
 * PROPAGA (no descarga un archivo vacío). */
async function descargarStats(path: string, filtros?: FiltrosStats): Promise<Blob> {
  const token = authProvider.getToken();
  const res = await fetch(`${API_BASE}${path}${statsQuery(filtros)}`, {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
  return await res.blob();
}

export const adminApi = {

  // -------------------------------------------------------------------------
  // Estadísticas institucionales — C-20
  // -------------------------------------------------------------------------

  /**
   * Sumario institucional agregado (admin_sistema / coordinador) — C-20.
   * Real: GET /api/v1/stats/resumen → conteos + riesgo + distribución de scores.
   * Un fallo (403/red) se PROPAGA como error; la página lo muestra como error,
   * nunca como datos en cero (contrato de carga resiliente C-73).
   */
  async obtenerResumenStats(filtros?: FiltrosStats): Promise<ResumenStats> {
    return await realFetch<ResumenStats>(`/stats/resumen${statsQuery(filtros)}`, { method: 'GET' });
  },

  /**
   * Descarga el sumario como Excel (.xlsx) con gráficos nativos — C-20.
   * Real: GET /api/v1/stats/export.xlsx (con Authorization). Un fallo se PROPAGA.
   */
  async descargarResumenExcel(filtros?: FiltrosStats): Promise<Blob> {
    return await descargarStats('/stats/export.xlsx', filtros);
  },

  /**
   * Registro de actividad / auditoría (admin_sistema) — C-20.
   * Real: GET /api/v1/admin/audit-log (paginado + filtrado). Un fallo se PROPAGA;
   * la página lo muestra como error, nunca como datos vacíos falsos.
   */
  async obtenerAuditLog(
    filtros?: AuditFiltros,
    limit = 50,
    offset = 0,
  ): Promise<AuditLogResponse> {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filtros?.actor) p.set('actor', filtros.actor);
    if (filtros?.modulo) p.set('modulo', filtros.modulo);
    if (filtros?.tipo_accion) p.set('tipo_accion', filtros.tipo_accion);
    if (filtros?.accion) p.set('accion', filtros.accion);
    if (filtros?.desde) p.set('desde', filtros.desde);
    if (filtros?.hasta) p.set('hasta', filtros.hasta);
    return await realFetch<AuditLogResponse>(`/admin/audit-log?${p.toString()}`, { method: 'GET' });
  },

  async obtenerAuditModulos(): Promise<string[]> {
    return await realFetch<string[]>('/admin/audit-modulos', { method: 'GET' });
  },

  /**
   * Descarga el registro de auditoría con LOS MISMOS filtros que la pantalla.
   * Lo que se ve es lo que sale en el archivo — un export que ignora los filtros
   * aplicados no sirve para responder "qué pasó entre estas dos fechas".
   * Real: GET /api/v1/admin/audit-log/export.{xlsx|pdf}
   */
  async exportarAuditoria(
    formato: 'xlsx' | 'pdf',
    filtros?: AuditFiltros,
  ): Promise<Blob> {
    const p = new URLSearchParams();
    if (filtros?.actor) p.set('actor', filtros.actor);
    // El módulo IBA sin enviarse: filtrabas por "Integración Moodle" y el archivo
    // salía con TODO el registro. Ahora el export respeta el filtro de módulo.
    if (filtros?.modulo) p.set('modulo', filtros.modulo);
    if (filtros?.accion) p.set('accion', filtros.accion);
    if (filtros?.desde) p.set('desde', filtros.desde);
    if (filtros?.hasta) p.set('hasta', filtros.hasta);
    const qs = p.toString();
    const token = authProvider.getToken();
    const res = await fetch(
      `${API_BASE}/admin/audit-log/export.${formato}${qs ? `?${qs}` : ''}`,
      { method: 'GET', headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
    return await res.blob();
  },

  /**
   * Descarga el sumario como PDF (admin_sistema / coordinador) — C-20.
   * Real: GET /api/v1/stats/export.pdf (con Authorization). Devuelve el Blob para
   * que la pantalla dispare la descarga; un fallo se PROPAGA.
   */
  async descargarResumenPdf(filtros?: FiltrosStats): Promise<Blob> {
    return await descargarStats('/stats/export.pdf', filtros);
  },
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
    password?: string;
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

  // -------------------------------------------------------------------------
  // Credencial de servicio de Moodle (token cifrado en la base)
  // -------------------------------------------------------------------------

  /**
   * Estado de la credencial de Moodle. El token NUNCA viaja: solo si está
   * configurado y sus últimos 4 caracteres, para reconocer cuál se cargó.
   * Real: GET /api/v1/config/moodle  (solo admin_sistema)
   */
  async obtenerCredencialMoodle(): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle', { method: 'GET' });
  },

  /**
   * Guarda la credencial. Omitir `token` deja el guardado intacto (permite
   * corregir el curso o la actividad sin volver a tipear el secreto).
   * Real: PUT /api/v1/config/moodle
   */
  async guardarCredencialMoodle(body: {
    base_url?: string;
    token?: string;
    component?: 'mod_assign' | 'mod_quiz';
  }): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle', { method: 'PUT', body: JSON.stringify(body) });
  },

  /** Borra el token guardado. Real: DELETE /api/v1/config/moodle/token */
  async borrarTokenMoodle(): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle/token', { method: 'DELETE' });
  },
};

/** Estado de la credencial de Moodle tal como lo expone la API (SIN el token). */
export interface CredencialMoodle {
  base_url: string;
  /** Tipo de actividad por defecto. El DESTINO (curso + actividad) es de cada examen. */
  component: 'mod_assign' | 'mod_quiz';
  /** True si hay un token utilizable (guardado en la base o heredado del entorno). */
  token_configurado: boolean;
  /** Últimos 4 caracteres del token guardado. null si viene del entorno. */
  token_pista: string | null;
  /** 'db' | 'env' | 'sin_configurar'. */
  origen: string;
  actualizado_en: string | null;
  actualizado_por: string | null;
}
