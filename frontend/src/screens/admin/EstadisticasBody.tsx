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
import type { ResumenStats, ComisionStat } from '../../lib/types';
import {
  alturasRelativas,
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
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-surface-200 bg-white text-on-surface text-[14px] font-medium hover:bg-primary-50 hover:border-primary-200 transition-colors"
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

      <PadronElegibilidad data={data} />

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
/** Etiqueta base por banda; si el segmento tiene enRiesgo=true se reemplaza por "Prioriza revisión". */
const ETIQUETA_BANDA: Record<string, string> = {
  '0-24': 'Bajo',
  '25-49': 'Moderado',
  '50-69': 'Alto',
  '70-100': 'Alto',
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
            Los gráficos se poblarán a medida que los alumnos rindan exámenes y se registren sesiones;
            los paneles de abajo muestran la estructura completa del tablero.
          </p>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <RoscaComposicion data={data} />
        <DonutDecisiones data={data} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <SesionesPorMateria data={data} />
        <SesionesPorComision data={data} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <TopEventos data={data} />
        <ActividadPorDia data={data} />
      </div>
    </div>
  );
}

/**
 * Habilitación del padrón para PODER RENDIR. Rosca SVG (Pueden / No pueden)
 * + barras horizontales de motivos de bloqueo. Mismo estilo visual que
 * DonutDecisiones para coherencia del dashboard.
 */
function PadronElegibilidad({ data }: { data: ResumenStats }) {
  const e = data.elegibilidad ?? {
    total_inscriptos: 0,
    con_consentimiento: 0,
    sin_consentimiento: 0,
    con_biometria: 0,
    sin_biometria: 0,
    pueden_rendir: 0,
    no_pueden_rendir: 0,
  };
  const total = e.total_inscriptos;

  const size = 176;
  const stroke = 26;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;

  const fracPueden = total > 0 ? e.pueden_rendir / total : 0;
  const fracNo     = total > 0 ? e.no_pueden_rendir / total : 0;

  const segs = [
    { key: 'pueden',    label: 'Pueden rendir',     valor: e.pueden_rendir,    fraccion: fracPueden, inicio: 0,          color: '#10b981' },
    { key: 'no_pueden', label: 'No pueden rendir',  valor: e.no_pueden_rendir, fraccion: fracNo,     inicio: fracPueden, color: '#ef4444' },
  ];

  const bloqueos = [
    { key: 'consent',  label: 'Sin consentimiento', valor: e.sin_consentimiento, icon: 'fact_check', color: '#f59e0b' },
    { key: 'bio',      label: 'Sin biometría',      valor: e.sin_biometria,      icon: 'face',       color: '#f59e0b' },
  ];

  return (
    <Card padded={false}>
      <ChartHead
        titulo="Habilitación para rendir"
        bajada="Requisito previo para iniciar un examen: consentimiento vigente + biometría de referencia."
      />
      {total === 0 ? (
        <ChartVacio icono="how_to_reg" texto="No hay alumnos inscriptos para el filtro seleccionado." />
      ) : (
        <div className="px-lg py-lg flex flex-col sm:flex-row items-center gap-lg">
          {/* Rosca SVG */}
          <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
              <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef1f5" strokeWidth={stroke} />
              {segs.map((s) =>
                s.fraccion > 0 ? (
                  <circle
                    key={s.key}
                    cx={size / 2} cy={size / 2} r={r}
                    fill="none"
                    stroke={s.color}
                    strokeWidth={stroke}
                    strokeDasharray={`${s.fraccion * c} ${c}`}
                    strokeDashoffset={-s.inicio * c}
                  >
                    <title>{`${s.label}: ${s.valor} · ${Math.round(s.fraccion * 100)}%`}</title>
                  </circle>
                ) : null,
              )}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-[28px] font-bold text-on-surface leading-none tabular-nums">{total}</span>
              <span className="text-[11px] text-on-surface-variant mt-1">inscriptos</span>
            </div>
          </div>

          {/* Leyenda + desglose de motivos de bloqueo */}
          <div className="flex-1 min-w-0 space-y-4 w-full">
            {/* Leyenda principal */}
            <ul className="space-y-2">
              {segs.map((s) => (
                <li key={s.key} className="flex items-center gap-2.5 text-[12.5px]">
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: s.color }} aria-hidden />
                  <span className="text-on-surface font-medium">{s.label}</span>
                  <span className="ml-auto text-on-surface font-semibold tabular-nums">{s.valor}</span>
                  <span className="text-on-surface-variant tabular-nums w-10 text-right">{Math.round(s.fraccion * 100)}%</span>
                </li>
              ))}
            </ul>

            <div className="border-t border-surface-200" />

            {/* Motivos de bloqueo como barras horizontales */}
            <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">Motivos de bloqueo</p>
            <div className="space-y-3">
              {bloqueos.map((b) => {
                const pct = total > 0 ? (b.valor / total) * 100 : 0;
                return (
                  <div key={b.key} className="text-[12px]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="flex items-center gap-1.5 text-on-surface">
                        <Icon name={b.icon} className="text-[14px] text-amber-600 shrink-0" fill />
                        {b.label}
                      </span>
                      <span className="text-on-surface-variant tabular-nums">
                        {b.valor} · {Math.round(pct)}%
                      </span>
                    </div>
                    <div className="h-3 w-full bg-surface-100 rounded-sm overflow-hidden">
                      <div
                        className="h-full rounded-sm"
                        style={{ width: `${Math.max(pct, b.valor > 0 ? 2 : 0)}%`, backgroundColor: b.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </Card>
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
  caso_abierto: { label: 'Caso abierto', color: '#f59e0b' },
  anulado_por_fraude: { label: 'Anulado por fraude', color: '#ef4444' },
  caso_descartado: { label: 'Caso descartado', color: '#10b981' },
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
      <ChartHead titulo="Estado de revisión" bajada="Estado de la revisión humana de cada sesión. Pendiente: sin veredicto aún. Sin hallazgos / Aprobado: falso positivo — nota validada. Anulado por fraude: nota anulada, devuelve 0." />
      {total === 0 ? (
        <ChartVacio icono="fact_check" texto="Ninguna sesión ha pasado por revisión humana todavía." />
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
      <ChartHead titulo="Sesiones por materia" bajada="Cantidad de sesiones de examen registradas por materia. Las que superan el umbral de score se muestran en rojo y priorizan la revisión humana." />
      {items.length === 0 ? (
        <ChartVacio icono="school" texto="Aún no hay sesiones de examen registradas." />
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

function SesionesPorComision({ data }: { data: ResumenStats }) {
  const items = (data.por_comision ?? []) as ComisionStat[];
  const alturas = alturasRelativas(items.map((c) => c.sesiones));
  return (
    <Card padded={false}>
      <ChartHead titulo="Sesiones por comisión" bajada="Cantidad de sesiones de examen registradas por comisión. Las que superan el umbral se muestran en rojo." />
      {items.length === 0 ? (
        <ChartVacio icono="groups" texto="Aún no hay sesiones de examen registradas." />
      ) : (
        <div className="px-lg py-lg space-y-3">
          {items.map((c, i) => {
            const pctRiesgo = c.sesiones > 0 ? (c.en_riesgo / c.sesiones) * 100 : 0;
            return (
              <div key={c.comision_id} className="text-[12.5px]">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-on-surface font-medium truncate" title={c.nombre}>{c.nombre}</span>
                  <span className="text-on-surface-variant tabular-nums">
                    {c.sesiones} · <span style={{ color: '#ef4444' }}>{c.en_riesgo} en riesgo</span>
                  </span>
                </div>
                <div className="h-5 bg-surface-100 rounded-sm overflow-hidden" style={{ width: `${Math.max(alturas[i], 4)}%` }}>
                  <div className="h-full flex">
                    <div className="h-full" style={{ width: `${100 - pctRiesgo}%`, backgroundColor: '#0d9488' }} />
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
      <ChartHead titulo="Actividad por día" bajada="Cantidad de sesiones de examen registradas por día. Muestra el volumen de actividad a lo largo del tiempo." />
      {items.length === 0 ? (
        <ChartVacio icono="calendar_month" texto="Aún no hay sesiones registradas." />
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
                  <title>{`${s.enRiesgo ? 'Prioriza revisión' : ETIQUETA_BANDA[s.rango]} (${s.rango}): ${s.valor} · ${s.pct}%`}</title>
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
              <span className={`text-on-surface font-medium${s.enRiesgo ? ' font-semibold' : ''}`}>
                {s.enRiesgo ? 'Prioriza revisión' : ETIQUETA_BANDA[s.rango]}
              </span>
              <span className="text-on-surface-variant tabular-nums">{s.rango}</span>
              <span className="ml-auto text-on-surface font-semibold tabular-nums">{s.valor}</span>
              <span className="text-on-surface-variant tabular-nums w-10 text-right">{s.pct}%</span>
            </li>
          ))}
        </ul>
      </div>
      {/* Pie con el % que prioriza revisión — fuera de la rosca para que no choque. */}
      <div className="px-lg py-3 border-t border-surface-200 flex items-center gap-2 text-[12.5px]">
        <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-[#ef4444]" aria-hidden />
        <span className="text-on-surface-variant">
          <span className="font-semibold text-on-surface tabular-nums">{pctRiesgo}%</span>{' '}
          priorizan revisión humana (score ≥ {data.umbral_riesgo ?? 70})
        </span>
      </div>
    </Card>
  );
}

export default EstadisticasBody;
