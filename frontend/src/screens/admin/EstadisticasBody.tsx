// Cuerpo presentacional de la página de estadísticas institucionales (C-20).
//
// Prop-driven (sin red ni router): la página que lo envuelve hace el fetch a
// GET /stats/resumen y le pasa el estado. Implementa el contrato de carga
// resiliente (C-73): cargando / error / vacío-real / cargado. Un fetch fallido
// se muestra como ERROR con reintentar, NUNCA como datos en cero.
//
// L2.5 (RN-SC-01, DD-01): "en riesgo" es un CONTEO que prioriza la revisión
// humana, nunca un veredicto ni una sanción automática.
import { Card, Icon, LoadingSpinner } from '../../ui/components';
import { StatCard } from '../proctoring/StatCard';
import type { ResumenStats } from '../../lib/types';
import {
  alturasRelativas,
  distribucionBuckets,
  donutSegmentos,
  pctSobreTotal,
  segmentosDonut,
} from './estadisticas.helpers';

export interface EstadisticasBodyProps {
  cargando: boolean;
  error: string | null;
  data: ResumenStats | null;
  onReintentar: () => void;
}

export function EstadisticasBody({ cargando, error, data, onReintentar }: EstadisticasBodyProps) {
  // Prioridad: un error de fetch manda — jamás degradar a "0" (contrato C-73).
  if (error) {
    return (
      <div className="flex flex-col items-center text-center gap-md py-2xl text-on-surface-variant">
        <Icon name="error" className="text-[40px] text-error" fill />
        <p className="text-[15px] max-w-sm">{error}</p>
        <button
          type="button"
          onClick={onReintentar}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-surface-200 bg-white text-on-surface text-[14px] font-medium hover:bg-primary/5 hover:border-primary/50 transition-colors"
        >
          <Icon name="refresh" className="text-[16px]" />
          Reintentar
        </button>
      </div>
    );
  }

  if (cargando || !data) {
    return (
      <div className="py-2xl flex items-center justify-center">
        <LoadingSpinner size="md" label="Cargando estadísticas…" />
      </div>
    );
  }

  return (
    <div className="space-y-lg animate-in fade-in duration-500">
      {/* Stat cards con datos reales del endpoint. Cero acá es honesto (el fetch
          fue OK); un fallo se ramifica arriba como error, no como estas cards.
          Sin descripciones: solo el número, para lectura limpia de un vistazo. */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-md">
        <StatCard icon="assignment" label="Exámenes" value={data.total_examenes} tono="primary" />
        <StatCard icon="school" label="Materias" value={data.total_materias} tono="violet" />
        <StatCard icon="groups" label="Comisiones" value={data.total_comisiones} tono="cyan" />
        <StatCard icon="videocam" label="Sesiones" value={data.total_sesiones} tono="success" />
        <StatCard icon="flag" label="En riesgo" value={data.sesiones_en_riesgo} tono="error" />
      </div>

      <GraficosScores data={data} />
    </div>
  );
}

/** Color vivo por banda de score, COMPARTIDO por la rosca y las barras para que
 * ambos gráficos "lean" igual: verde (bajo) → azul → ámbar → rojo (riesgo). */
const COLOR_BANDA: Record<string, string> = {
  '0-24': '#10b981',   // emerald — actividad baja
  '25-49': '#3b82f6',  // blue
  '50-69': '#f59e0b',  // amber
  '70-100': '#ef4444', // red — banda que prioriza revisión
};
const ETIQUETA_BANDA: Record<string, string> = {
  '0-24': 'Bajo',
  '25-49': 'Moderado',
  '50-69': 'Alto',
  '70-100': 'Prioriza revisión',
};

/** Zona de gráficos: el dashboard COMPLETO siempre visible. Cada tarjeta resuelve
 * su propio "sin datos" adentro (no se colapsa todo a una sola card). Con 0
 * sesiones se muestra un aviso arriba, pero la estructura del dashboard queda a la
 * vista — el usuario ve TODAS las dimensiones, aunque estén en cero (vacío-real). */
function GraficosScores({ data }: { data: ResumenStats }) {
  const sinDatos = data.total_sesiones === 0;

  return (
    <div className="space-y-lg">
      {sinDatos && (
        <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 px-lg py-4 text-[13.5px] text-blue-900">
          <Icon name="info" className="text-[22px] text-blue-600 shrink-0 mt-0.5" fill />
          <p className="leading-relaxed">
            <span className="font-semibold">Todavía no hay sesiones rendidas.</span>{' '}
            El catálogo y las métricas de sesiones se poblarán a medida que se
            supervisen exámenes; los paneles de abajo muestran la estructura completa
            del tablero.
          </p>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <RoscaComposicion data={data} />
        <BarrasDistribucion data={data} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <TopEventos data={data} />
        <DonutDecisiones data={data} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <SesionesPorMateria data={data} />
        <ActividadPorDia data={data} />
      </div>
    </div>
  );
}

/** Cabecera común de cada tarjeta de gráfico (título + bajada). */
function ChartHead({ titulo, bajada }: { titulo: string; bajada: string }) {
  return (
    <div className="px-lg py-md border-b border-surface-200">
      <h2 className="text-[16px] font-semibold text-on-surface leading-tight">{titulo}</h2>
      <p className="text-[12.5px] text-on-surface-variant mt-0.5">{bajada}</p>
    </div>
  );
}

/** Estado vacío chico dentro de una tarjeta de gráfico. */
function ChartVacio({ icono, texto }: { icono: string; texto: string }) {
  return (
    <div className="px-lg py-xl flex flex-col items-center text-center gap-sm text-on-surface-variant">
      <Icon name={icono} className="text-[32px]" />
      <p className="text-[13px]">{texto}</p>
    </div>
  );
}

/** Etiquetas legibles de los tipos de evento (detectores). Fallback: prettify. */
const ETIQUETA_EVENTO: Record<string, string> = {
  rostro_ausente: 'Rostro ausente',
  multiples_rostros: 'Múltiples rostros',
  mirada_desviada_sostenida: 'Mirada desviada',
  perdida_de_foco: 'Pérdida de foco',
  cambio_pestana: 'Cambio de pestaña',
  salida_pantalla_completa: 'Salió de pantalla completa',
  copiar_pegar: 'Copiar / pegar',
  monitor_adicional: 'Monitor adicional',
  corte_conectividad_prolongado: 'Corte de conexión',
  reanudacion_tardia: 'Reanudación tardía',
  recarga_pagina: 'Recarga de página',
};
function etiquetaEvento(tipo: string): string {
  return ETIQUETA_EVENTO[tipo] ?? tipo.replace(/_/g, ' ');
}

/**
 * Top de detectores que más dispararon (barras horizontales). Muestra qué
 * situaciones llaman la atención con más frecuencia — no es un veredicto.
 */
function TopEventos({ data }: { data: ResumenStats }) {
  const items = data.top_eventos ?? [];
  const alturas = alturasRelativas(items.map((e) => e.cantidad));
  return (
    <Card padded={false}>
      <ChartHead titulo="Detectores más frecuentes" bajada="Cuántas veces disparó cada situación observada." />
      {items.length === 0 ? (
        <ChartVacio icono="sensors" texto="Todavía no hay eventos registrados." />
      ) : (
        <div className="px-lg py-lg space-y-2.5">
          {items.map((e, i) => (
            <div key={e.tipo} className="flex items-center gap-3 text-[12.5px]">
              <span className="w-40 shrink-0 truncate text-on-surface" title={etiquetaEvento(e.tipo)}>
                {etiquetaEvento(e.tipo)}
              </span>
              <div className="flex-1 h-4 bg-surface-100 rounded-sm overflow-hidden">
                <div
                  className="h-full rounded-sm"
                  style={{ width: `${Math.max(alturas[i], 3)}%`, backgroundColor: '#0d9488' }}
                />
              </div>
              <span className="w-7 text-right font-semibold text-on-surface tabular-nums">{e.cantidad}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/** Etiqueta + color de cada decisión de revisión. */
const DECISION_META: Record<string, { label: string; color: string }> = {
  sin_revisar: { label: 'Sin revisar', color: '#94a3b8' },
  pendiente: { label: 'Pendiente', color: '#3b82f6' },
  sin_hallazgos: { label: 'Sin hallazgos', color: '#10b981' },
  aprobado: { label: 'Aprobado', color: '#10b981' },
  caso_abierto: { label: 'Caso abierto', color: '#ef4444' },
};
function decisionMeta(clave: string): { label: string; color: string } {
  return DECISION_META[clave] ?? { label: clave.replace(/_/g, ' '), color: '#8b5cf6' };
}

/**
 * Estado de revisión de las sesiones (rosca). La revisión es SIEMPRE humana; esto
 * solo muestra en qué punto del circuito está cada sesión.
 */
function DonutDecisiones({ data }: { data: ResumenStats }) {
  const conteos = data.decisiones ?? {};
  const items = Object.entries(conteos)
    .map(([clave, valor]) => ({ clave, valor }))
    .sort((a, b) => b.valor - a.valor);
  const segs = segmentosDonut(items);
  const total = items.reduce((acc, it) => acc + it.valor, 0);

  const size = 176;
  const stroke = 26;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;

  return (
    <Card padded={false}>
      <ChartHead titulo="Estado de revisión" bajada="En qué punto del circuito humano está cada sesión." />
      {total === 0 ? (
        <ChartVacio icono="fact_check" texto="Todavía no hay sesiones para revisar." />
      ) : (
        <div className="px-lg py-lg flex flex-col sm:flex-row items-center gap-lg">
          <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
              <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef1f5" strokeWidth={stroke} />
              {segs.map((s) =>
                s.fraccion > 0 ? (
                  <circle
                    key={s.clave}
                    cx={size / 2}
                    cy={size / 2}
                    r={r}
                    fill="none"
                    stroke={decisionMeta(s.clave).color}
                    strokeWidth={stroke}
                    strokeDasharray={`${s.fraccion * c} ${c}`}
                    strokeDashoffset={-s.inicio * c}
                  >
                    <title>{`${decisionMeta(s.clave).label}: ${s.valor} · ${s.pct}%`}</title>
                  </circle>
                ) : null,
              )}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-[28px] font-bold text-on-surface leading-none tabular-nums">{total}</span>
              <span className="text-[11px] text-on-surface-variant mt-1">sesiones</span>
            </div>
          </div>
          <ul className="flex-1 min-w-0 space-y-2 w-full">
            {segs.map((s) => (
              <li key={s.clave} className="flex items-center gap-2.5 text-[12.5px]">
                <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: decisionMeta(s.clave).color }} aria-hidden />
                <span className="text-on-surface font-medium">{decisionMeta(s.clave).label}</span>
                <span className="ml-auto text-on-surface font-semibold tabular-nums">{s.valor}</span>
                <span className="text-on-surface-variant tabular-nums w-10 text-right">{s.pct}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/**
 * Sesiones por materia (barras horizontales apiladas): el total en gris-azulado y
 * la porción "en riesgo" en rojo, que PRIORIZA la revisión humana.
 */
function SesionesPorMateria({ data }: { data: ResumenStats }) {
  const items = data.por_materia ?? [];
  const alturas = alturasRelativas(items.map((m) => m.sesiones));
  return (
    <Card padded={false}>
      <ChartHead titulo="Sesiones por materia" bajada="Volumen supervisado y cuántas priorizan revisión (en rojo)." />
      {items.length === 0 ? (
        <ChartVacio icono="school" texto="Todavía no hay sesiones asociadas a materias." />
      ) : (
        <div className="px-lg py-lg space-y-3">
          {items.map((m, i) => {
            const pctRiesgo = m.sesiones > 0 ? (m.en_riesgo / m.sesiones) * 100 : 0;
            return (
              <div key={m.materia_id} className="text-[12.5px]">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-on-surface font-medium truncate" title={m.nombre}>{m.nombre}</span>
                  <span className="text-on-surface-variant tabular-nums">
                    {m.sesiones} · <span style={{ color: '#ef4444' }}>{m.en_riesgo} en riesgo</span>
                  </span>
                </div>
                <div className="h-5 bg-surface-100 rounded-sm overflow-hidden" style={{ width: `${Math.max(alturas[i], 4)}%` }}>
                  <div className="h-full flex">
                    <div className="h-full" style={{ width: `${100 - pctRiesgo}%`, backgroundColor: '#3b82f6' }} />
                    <div className="h-full" style={{ width: `${pctRiesgo}%`, backgroundColor: '#ef4444' }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/**
 * Actividad por día (área SVG): sesiones creadas por jornada. Da la evolución en
 * el tiempo del volumen supervisado.
 */
function ActividadPorDia({ data }: { data: ResumenStats }) {
  const items = data.por_dia ?? [];
  const alturas = alturasRelativas(items.map((d) => d.sesiones));
  const maxV = Math.max(0, ...items.map((d) => d.sesiones));
  return (
    <Card padded={false}>
      <ChartHead titulo="Actividad por día" bajada="Sesiones supervisadas por jornada." />
      {items.length === 0 ? (
        <ChartVacio icono="calendar_month" texto="Todavía no hay actividad registrada." />
      ) : (
        <div className="px-lg py-lg">
          <div className="flex items-end justify-between gap-1.5 h-40">
            {items.map((d, i) => (
              <div key={d.fecha} className="flex flex-col items-center gap-1 flex-1 min-w-0 h-full justify-end">
                <span className="text-[11px] font-semibold text-on-surface tabular-nums">{d.sesiones}</span>
                <div className="w-full flex items-end justify-center" style={{ height: '100%' }}>
                  <div
                    className="w-full max-w-[28px] rounded-t-sm"
                    style={{ height: `${Math.max(alturas[i], d.sesiones > 0 ? 4 : 0)}%`, backgroundColor: '#6366f1' }}
                    aria-label={`${d.sesiones} sesiones el ${d.fecha}`}
                  />
                </div>
                <span className="text-[10px] text-on-surface-variant tabular-nums truncate w-full text-center">
                  {d.fecha.slice(5)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-on-surface-variant mt-2 text-right">Pico: {maxV} sesiones/día</p>
        </div>
      )}
    </Card>
  );
}

/**
 * Rosca (donut) SVG de la composición por banda de score. El centro resume el
 * total de sesiones y el % en la banda de riesgo. El % en riesgo PRIORIZA la
 * revisión humana; no es un veredicto (L2.5, RN-SC-01).
 */
function RoscaComposicion({ data }: { data: ResumenStats }) {
  const segs = donutSegmentos(data.distribucion_scores, data.umbral_riesgo);
  const pctRiesgo = pctSobreTotal(data.sesiones_en_riesgo, data.total_sesiones);

  const size = 176;
  const stroke = 26;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;

  return (
    <Card padded={false}>
      <div className="px-lg py-md border-b border-surface-200">
        <h2 className="text-[16px] font-semibold text-on-surface leading-tight">Sesiones por nivel de score</h2>
        <p className="text-[12.5px] text-on-surface-variant mt-0.5">
          Cómo se reparten las sesiones entre los niveles de score.
        </p>
      </div>
      <div className="px-lg py-lg flex flex-col sm:flex-row items-center gap-lg">
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef1f5" strokeWidth={stroke} />
            {segs.map((s) =>
              s.fraccion > 0 ? (
                <circle
                  key={s.rango}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={COLOR_BANDA[s.rango]}
                  strokeWidth={stroke}
                  strokeDasharray={`${s.fraccion * c} ${c}`}
                  strokeDashoffset={-s.inicio * c}
                >
                  <title>{`${ETIQUETA_BANDA[s.rango]} (${s.rango}): ${s.valor} · ${s.pct}%`}</title>
                </circle>
              ) : null,
            )}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-[30px] font-bold text-on-surface leading-none tabular-nums">{data.total_sesiones}</span>
            <span className="text-[11px] text-on-surface-variant mt-1">sesiones</span>
          </div>
        </div>

        <ul className="flex-1 min-w-0 space-y-2 w-full">
          {segs.map((s) => (
            <li key={s.rango} className="flex items-center gap-2.5 text-[12.5px]">
              <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: COLOR_BANDA[s.rango] }} aria-hidden />
              <span className="text-on-surface font-medium">{ETIQUETA_BANDA[s.rango]}</span>
              <span className="text-on-surface-variant tabular-nums">{s.rango}</span>
              <span className="ml-auto text-on-surface font-semibold tabular-nums">{s.valor}</span>
              <span className="text-on-surface-variant tabular-nums w-10 text-right">{s.pct}%</span>
            </li>
          ))}
        </ul>
      </div>
      {/* Pie con el % que prioriza revisión — fuera de la rosca para que no choque. */}
      <div className="px-lg py-3 border-t border-surface-200 flex items-center gap-2 text-[12.5px]">
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLOR_BANDA['70-100'] }} aria-hidden />
        <span className="text-on-surface-variant">
          <span className="font-semibold text-on-surface tabular-nums">{pctRiesgo}%</span> de las
          sesiones priorizan la revisión humana
        </span>
      </div>
    </Card>
  );
}

/**
 * Barras verticales de distribución por bucket. La barra más poblada llega al
 * 100% de la altura; cada banda usa su color vivo. Con la banda de riesgo (>=
 * umbral) el color rojo PRIORIZA la lectura, sin emitir juicio.
 */
function BarrasDistribucion({ data }: { data: ResumenStats }) {
  const bars = distribucionBuckets(data.distribucion_scores, data.umbral_riesgo);

  return (
    <Card padded={false}>
      <div className="px-lg py-md border-b border-surface-200">
        <h2 className="text-[16px] font-semibold text-on-surface leading-tight">Distribución de scores</h2>
        <p className="text-[12.5px] text-on-surface-variant mt-0.5">
          Sesiones por rango de score. Desde {data.umbral_riesgo} priorizan la revisión humana.
        </p>
      </div>
      <div className="px-lg py-lg">
        <div className="flex items-end justify-around gap-md h-48">
          {bars.map((b) => (
            <div key={b.rango} className="flex flex-col items-center gap-2 flex-1 min-w-0 h-full justify-end">
              <span className="text-[13px] font-semibold text-on-surface tabular-nums">{b.valor}</span>
              <div className="w-full flex items-end justify-center" style={{ height: '100%' }}>
                <div
                  className="w-full max-w-[64px] rounded-t-md transition-all"
                  style={{
                    height: `${b.pct}%`,
                    minHeight: b.valor > 0 ? 4 : 0,
                    backgroundColor: COLOR_BANDA[b.rango],
                  }}
                  aria-label={`${b.valor} sesiones con score ${b.rango}`}
                />
              </div>
              <span className="text-[12px] text-on-surface-variant tabular-nums">{b.rango}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

export default EstadisticasBody;
