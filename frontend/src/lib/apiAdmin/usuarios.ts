// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { API_BASE, realFetch } from '../apiCore';
import { authProvider } from '../authProvider';
import { fetchAutenticado } from '../fetchAutenticado';
import type {
  UsuarioAdmin, ListarUsuariosResponse,
} from '../types';

export const usuariosApi = {
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
    filtros?: { rol?: string; estado?: string; q?: string; materia_id?: string; comision_id?: string },
  ): Promise<ListarUsuariosResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filtros?.rol) params.set('rol', filtros.rol);
    if (filtros?.estado) params.set('estado', filtros.estado);
    if (filtros?.q) params.set('q', filtros.q);
    if (filtros?.materia_id) params.set('materia_id', filtros.materia_id);
    if (filtros?.comision_id) params.set('comision_id', filtros.comision_id);
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
    const res = await fetchAutenticado(`${API_BASE}/users/${usuarioId}/reactivar`, {
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
    username: string;
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
   * Le genera al usuario una contraseña temporal y la devuelve UNA sola vez.
   *
   * El endpoint existe desde c-78 pero ninguna pantalla lo llamaba: la única
   * forma de destrabar a alguien que olvidó su clave era pegarle a la API a mano.
   *
   * La temporal NO se guarda en claro en ningún lado — si se pierde antes de
   * dársela a la persona, hay que resetear de nuevo. El usuario queda obligado a
   * cambiarla al entrar, así que el admin destraba el acceso sin quedarse
   * sabiendo la clave de nadie.
   *
   * Real: POST /users/{usuarioId}/resetear-password
   */
  async resetearPasswordUsuario(usuarioId: string): Promise<{
    usuario_id: string;
    password_temporal: string;
    debe_cambiar_password: boolean;
  }> {
    return await realFetch(
      `/users/${encodeURIComponent(usuarioId)}/resetear-password`,
      { method: 'POST' },
    );
  },

  /**
   * Da de baja lógica (soft-delete) a un usuario (admin_sistema) — C-61.
   * Real: DELETE /users/{usuarioId} → 204 sin cuerpo.
   */
  async eliminarUsuario(usuarioId: string): Promise<void> {
    const token = authProvider.getToken();
    const res = await fetchAutenticado(`${API_BASE}/users/${usuarioId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },
};
