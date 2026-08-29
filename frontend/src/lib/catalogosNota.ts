/**
 * Los catálogos de la tabla de notas: resultados y motivos de retención.
 *
 * Los define el BACKEND. Estuvieron escritos a mano acá y el resultado se
 * decidía además con `if` propios, duplicados en el export de Python: las dos
 * copias divergieron y una nota anulada por fraude salía "Aprobado" en el Excel
 * mientras la pantalla decía "Anulada".
 *
 * El respaldo existe sólo para que la pantalla no quede en blanco si la llamada
 * falla, y no se cachea para poder reintentar. Si difiere del backend, gana el
 * backend.
 */
import { fetchAutenticado } from './fetchAutenticado';
import { authProvider } from './authProvider';
import { API_BASE } from './api';
import type { TonoEstado } from './estadosMoodle';

export interface ItemCatalogo {
  valor: string;
  etiqueta: string;
  tono: TonoEstado;
  /** Explicación larga, para el tooltip. Sólo la traen las retenciones. */
  detalle?: string;
  /** Color hex para los gráficos. Sólo lo traen las decisiones. */
  color?: string;
}

const FALLBACK_RESULTADOS: ItemCatalogo[] = [
  { valor: 'aprobado', etiqueta: 'Aprobado', tono: 'success' },
  { valor: 'desaprobado', etiqueta: 'Desaprobado', tono: 'error' },
  { valor: 'anulada', etiqueta: 'Anulada', tono: 'critico' },
  { valor: 'sin_nota', etiqueta: 'Sin nota', tono: 'neutral' },
  { valor: 'sin_criterio', etiqueta: 'Sin criterio de aprobación', tono: 'neutral' },
];

const FALLBACK_RETENCIONES: ItemCatalogo[] = [
  { valor: 'en_riesgo', etiqueta: 'En revisión', tono: 'warning' },
  { valor: 'anulada', etiqueta: 'Anulada', tono: 'critico' },
  { valor: 'sin_destino', etiqueta: 'Falta el destino', tono: 'error' },
  { valor: 'sin_credencial_docente', etiqueta: 'Falta conectar el campus', tono: 'error' },
];

const FALLBACK_DECISIONES: ItemCatalogo[] = [
  { valor: 'sin_revisar', etiqueta: 'Sin revisar', tono: 'neutral', color: '#94a3b8' },
  { valor: 'aprobado', etiqueta: 'Aprobado', tono: 'success', color: '#10b981' },
  { valor: 'anulado', etiqueta: 'Anulado por fraude', tono: 'error', color: '#ef4444' },
];

const cache = new Map<string, ItemCatalogo[]>();
const enVuelo = new Map<string, Promise<ItemCatalogo[]>>();

async function traer(ruta: string, respaldo: ItemCatalogo[]): Promise<ItemCatalogo[]> {
  const cacheado = cache.get(ruta);
  if (cacheado) return cacheado;
  const pendiente = enVuelo.get(ruta);
  if (pendiente) return pendiente;
  const promesa = (async () => {
    try {
      // El header va en el PRIMER intento. `fetchAutenticado` NO lo arma: lo
      // espera en el `init` y solo lo agrega al reintentar tras un 401. Sin
      // esto, cada catálogo hacía 401 → refresh → reintento, tres viajes en vez
      // de uno, y llenaba la consola del alumno de 401 que parecían una fuga.
      const token = authProvider.getToken();
      const resp = await fetchAutenticado(`${API_BASE}/catalogos/${ruta}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as ItemCatalogo[];
      if (!Array.isArray(data) || data.length === 0) throw new Error('respuesta vacía');
      cache.set(ruta, data);
      return data;
    } catch {
      return respaldo;
    } finally {
      enVuelo.delete(ruta);
    }
  })();
  enVuelo.set(ruta, promesa);
  return promesa;
}

export const cargarResultados = () => traer('resultados-nota', FALLBACK_RESULTADOS);
export const cargarRetenciones = () => traer('retenciones', FALLBACK_RETENCIONES);

/** Veredictos de revisión, con su color para los gráficos. */
export const cargarDecisiones = () => traer('decisiones', FALLBACK_DECISIONES);

/** Solo para tests: descarta lo cacheado. */
export function _resetCacheCatalogos(): void {
  cache.clear();
  enVuelo.clear();
}
