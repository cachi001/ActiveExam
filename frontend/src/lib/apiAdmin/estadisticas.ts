// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { API_BASE, realFetch } from '../apiCore';
import { authProvider } from '../authProvider';
import type {
  ResumenStats, FiltrosStats, AuditLogResponse, AuditFiltros,
} from '../types';

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

export const estadisticasApi = {
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
};
