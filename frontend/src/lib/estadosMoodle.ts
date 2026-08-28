/**
 * Estados de la nota en el campus: los trae el BACKEND, no los define esta capa.
 *
 * Antes esta lista estaba escrita a mano en dos lugares del frontend (el badge de
 * la tabla y el desplegable del filtro) y ya se habían desfasado entre sí: cuando
 * apareció 'manual' ("cargada a mano"), el badge lo mostraba pero el filtro no lo
 * ofrecía, así que una nota marcada a mano se veía en pantalla y no se podía
 * buscar. La etiqueta y el color son decisiones de dominio (verde = "el campus lo
 * confirmó" es distinto de "alguien dice que la cargó"), así que viven del lado
 * del backend y acá solo se consumen.
 *
 * `FALLBACK_ESTADOS` existe solo para que la pantalla no quede sin filtro si la
 * llamada falla, y para los tests. No es la fuente de verdad: si difiere del
 * backend, gana el backend.
 */
import { fetchAutenticado } from './fetchAutenticado';
import { API_BASE } from './api';

// `critico` es un rojo lleno: una anulación por fraude no puede verse igual
// que un desaprobado, que es un resultado académico normal.
export type TonoEstado = 'warning' | 'success' | 'error' | 'neutral' | 'primary' | 'critico';

export interface EstadoMoodleInfo {
  valor: string;
  etiqueta: string;
  tono: TonoEstado;
}

/** Respaldo si la API no responde. Espeja el enum `EstadoNota` del backend. */
export const FALLBACK_ESTADOS: EstadoMoodleInfo[] = [
  { valor: 'pendiente', etiqueta: 'Pendiente', tono: 'warning' },
  { valor: 'enviado', etiqueta: 'Enviado', tono: 'success' },
  { valor: 'fallido', etiqueta: 'Fallido', tono: 'error' },
  { valor: 'sin_token', etiqueta: 'Falta conectar el campus', tono: 'error' },
  { valor: 'manual', etiqueta: 'Cargada a mano', tono: 'primary' },
];

// Es una constante de dominio: se pide una vez por sesión, no en cada pantalla.
let cache: EstadoMoodleInfo[] | null = null;
let enVuelo: Promise<EstadoMoodleInfo[]> | null = null;

export async function cargarEstadosMoodle(): Promise<EstadoMoodleInfo[]> {
  if (cache) return cache;
  if (enVuelo) return enVuelo;
  enVuelo = (async () => {
    try {
      const resp = await fetchAutenticado(`${API_BASE}/catalogos/estados-entrega`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as EstadoMoodleInfo[];
      if (!Array.isArray(data) || data.length === 0) throw new Error('respuesta vacía');
      cache = data;
      return data;
    } catch {
      // Sin estados no se puede ni filtrar ni pintar el badge: se cae al respaldo
      // en vez de dejar la pantalla rota. No se cachea, para reintentar después.
      return FALLBACK_ESTADOS;
    } finally {
      enVuelo = null;
    }
  })();
  return enVuelo;
}

/** Solo para tests: descarta lo cacheado. */
export function _resetCacheEstadosMoodle(): void {
  cache = null;
  enVuelo = null;
}
