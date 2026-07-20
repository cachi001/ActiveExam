// Helpers puros de la página de estadísticas institucionales (C-20).
//
// Solo transforman el sumario agregado (/stats/resumen) para dibujarlo: ordenan
// los buckets, escalan la altura de las barras y derivan tasas. NO emiten
// veredictos ni acciones (L2.5, RN-SC-01, DD-01): la banda "en riesgo" es una
// señal de PRIORIZACIÓN para la revisión humana.

/** Orden canónico de los buckets de score (espeja el backend). */
export const ORDEN_BUCKETS = ['0-24', '25-49', '50-69', '70-100'] as const;

export interface BucketBar {
  /** Rango del bucket, p.ej. "70-100". */
  rango: string;
  /** Cantidad de sesiones en el bucket. */
  valor: number;
  /** Altura relativa 0-100 (respecto al bucket más poblado). */
  pct: number;
  /** El límite inferior del rango cae dentro de la banda de riesgo (>= umbral). */
  enRiesgo: boolean;
}

/** Límite inferior de un rango "X-Y" → X (NaN-safe: rango inválido → 0). */
function limiteInferior(rango: string): number {
  const n = Number.parseInt(rango.split('-')[0] ?? '', 10);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Convierte el mapa de distribución en barras ordenadas y escaladas.
 * La barra más poblada llega al 100%; el resto es proporcional. Con todos los
 * buckets en cero, `pct` es 0 (nunca NaN por dividir por cero).
 */
export function distribucionBuckets(
  dist: Record<string, number>,
  umbral: number,
): BucketBar[] {
  const max = Math.max(0, ...ORDEN_BUCKETS.map((r) => dist[r] ?? 0));
  return ORDEN_BUCKETS.map((rango) => {
    const valor = dist[rango] ?? 0;
    return {
      rango,
      valor,
      pct: max > 0 ? (valor / max) * 100 : 0,
      enRiesgo: limiteInferior(rango) >= umbral,
    };
  });
}

/** Porcentaje entero de `parte` sobre `total`. Total 0 → 0 (nunca NaN). */
export function pctSobreTotal(parte: number, total: number): number {
  return total > 0 ? Math.round((parte / total) * 100) : 0;
}

/** Altura relativa (0..100) de cada valor respecto al máximo de la serie. Para
 * barras: la más alta llega al 100%. Máximo 0 → todas en 0 (nunca NaN). */
export function alturasRelativas(valores: number[]): number[] {
  const max = Math.max(0, ...valores);
  return valores.map((v) => (max > 0 ? (v / max) * 100 : 0));
}

export interface DonutSlice {
  clave: string;
  valor: number;
  fraccion: number;
  pct: number;
  inicio: number;
}

/** Segmentos de rosca a partir de conteos arbitrarios (respeta el orden dado).
 * Genérico (a diferencia de `donutSegmentos`, atado a los buckets de score):
 * lo usa el donut de decisiones de revisión. Total 0 → todo en 0 (sin NaN). */
export function segmentosDonut(items: { clave: string; valor: number }[]): DonutSlice[] {
  const total = items.reduce((acc, it) => acc + it.valor, 0);
  let acumulado = 0;
  return items.map((it) => {
    const fraccion = total > 0 ? it.valor / total : 0;
    const slice: DonutSlice = {
      clave: it.clave,
      valor: it.valor,
      fraccion,
      pct: total > 0 ? Math.round((it.valor / total) * 100) : 0,
      inicio: acumulado,
    };
    acumulado += fraccion;
    return slice;
  });
}

export interface DonutSegment {
  /** Rango del bucket, p.ej. "70-100". */
  rango: string;
  /** Cantidad de sesiones en el bucket. */
  valor: number;
  /** Fracción del total (0..1). Total 0 → 0 (nunca NaN). */
  fraccion: number;
  /** Porcentaje entero del total (0..100). */
  pct: number;
  /** Fracción acumulada donde ARRANCA el arco en la circunferencia (0..1). */
  inicio: number;
  /** El rango cae dentro de la banda de riesgo (límite inferior >= umbral). */
  enRiesgo: boolean;
}

/**
 * Reparte la distribución en segmentos acumulados para dibujar una rosca (donut)
 * con arcos SVG. Cada segmento sabe qué fracción del total ocupa y desde dónde
 * arranca, de modo que el componente solo traduce fracción → stroke-dasharray.
 * Con total 0, todas las fracciones son 0 (nunca NaN por dividir por cero).
 */
export function donutSegmentos(
  dist: Record<string, number>,
  umbral: number,
): DonutSegment[] {
  const total = ORDEN_BUCKETS.reduce((acc, r) => acc + (dist[r] ?? 0), 0);
  let acumulado = 0;
  return ORDEN_BUCKETS.map((rango) => {
    const valor = dist[rango] ?? 0;
    const fraccion = total > 0 ? valor / total : 0;
    const seg: DonutSegment = {
      rango,
      valor,
      fraccion,
      pct: total > 0 ? Math.round((valor / total) * 100) : 0,
      inicio: acumulado,
      enRiesgo: limiteInferior(rango) >= umbral,
    };
    acumulado += fraccion;
    return seg;
  });
}
