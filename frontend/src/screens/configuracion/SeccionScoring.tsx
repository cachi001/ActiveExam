/**
 * SeccionScoring — pesos de scoring por tipo de evento (#10 / migracion 0011).
 *
 * Sección de la página Configuración del sistema. Lista los tipos del catalogo
 * persistidos en `evento_score_config` como tarjetas en grilla de 2 columnas,
 * con severidad y peso (0-100) por tipo.
 *
 * El on/off del evento NO vive acá: el único interruptor de activación es el
 * detector (Parámetros generales → Detectores). Si un detector está apagado, el
 * evento no se detecta y su peso no aplica. Acá solo se configura cuánto pesa.
 *
 * C-68 UX:
 *  - Fila inferior con controles en grilla alineada.
 *  - Más separación entre cards (gap-md).
 *  - Nota inferior con padding correcto.
 *  - Título de sección propio.
 */
import { useEffect, useState } from 'react';
import { Icon, Button } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api, SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from '../../lib/api';
import type { EventoScoreConfig, Severidad, TipoEvento } from '../../lib/types';
import { SEVERITY_BADGE_COLORS } from '../harness/helpers';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';

// baseline NO es un evento: es el piso 0 del score, no se elige por evento.
import {
  rangoDeSeveridad,
  type SeveridadEditable,
} from '../../config/severityRanges';

const SEVERIDADES: SeveridadEditable[] = ['baja', 'media', 'alta', 'critica'];
const SEV_ORDER: Record<string, number> = { critica: 0, alta: 1, media: 2, baja: 3 };

/** Color por severidad, usado por la barrita-acento corta de la card y el punto
 * de la leyenda de rangos (mismo lenguaje visual). */
const SEVERITY_DOT: Record<SeveridadEditable, string> = {
  baja: 'bg-blue-400',
  media: 'bg-amber-400',
  alta: 'bg-red-500',
  critica: 'bg-red-700',
};

/** Devuelve el peso ajustado al rango de la severidad dada. */
function ajustarPesoARango(peso: number, severidad: SeveridadEditable): number {
  const { min, max } = rangoDeSeveridad(severidad);
  if (peso < min) return min;
  if (peso > max) return max;
  return peso;
}

/** Severidad segura para indexar rangos (defaultea a 'media' si viene una
 * severidad no editable como 'baseline' — el catálogo no debería tener
 * baseline, pero el guardrail evita un undefined en la UI). */
function severidadEditable(s: Severidad): SeveridadEditable {
  return s === 'baseline' ? 'media' : s;
}

export default function SeccionScoring() {
  const toast = useToast();
  const [configs, setConfigs] = useState<EventoScoreConfig[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<EventoScoreConfig>>>({});

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setCargando(true);
    try {
      const res = await api.listarScoringConfig();
      setConfigs(res.items);
      setDrafts({});
    } catch (e) {
      toast.error(`No se pudo cargar la configuracion: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setCargando(false);
    }
  }

  function setDraft<K extends keyof EventoScoreConfig>(tipo: string, field: K, value: EventoScoreConfig[K]) {
    setDrafts((prev) => ({ ...prev, [tipo]: { ...prev[tipo], [field]: value } }));
  }

  /**
   * Setter para `severidad` que también ajusta el peso si queda fuera del rango
   * de la nueva severidad. Evita el bug "baja con peso 100" o "crítica con peso 5".
   */
  function setSeveridad(cfg: EventoScoreConfig, nuevaSev: SeveridadEditable) {
    const pesoActual = valorActual(cfg, 'peso') as number;
    const pesoAjustado = ajustarPesoARango(pesoActual, nuevaSev);
    setDrafts((prev) => ({
      ...prev,
      [cfg.tipo_evento]: { ...prev[cfg.tipo_evento], severidad: nuevaSev, peso: pesoAjustado },
    }));
  }

  function valorActual<K extends keyof EventoScoreConfig>(cfg: EventoScoreConfig, field: K): EventoScoreConfig[K] {
    const draft = drafts[cfg.tipo_evento];
    return (draft?.[field] as EventoScoreConfig[K] | undefined) ?? cfg[field];
  }

  function tieneEdicion(tipo: string): boolean {
    return !!drafts[tipo] && Object.keys(drafts[tipo]).length > 0;
  }

  async function guardar(cfg: EventoScoreConfig) {
    const draft = drafts[cfg.tipo_evento];
    if (!draft) return;
    setGuardando(cfg.tipo_evento);
    try {
      const updated = await api.editarScoringConfig(cfg.tipo_evento, draft);
      setConfigs((prev) => prev.map((c) => (c.tipo_evento === cfg.tipo_evento ? updated : c)));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[cfg.tipo_evento];
        return next;
      });
      // Invalida ambos caches: scoring weights + config efectiva completa (task 4.5).
      resetEffectiveConfigCache();
      toast.success(`Guardado: ${TIPO_EVENTO_LABEL[cfg.tipo_evento as TipoEvento] ?? cfg.tipo_evento}`);
    } catch (e) {
      toast.error(`No se pudo guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(null);
    }
  }

  function descartar(tipo: string) {
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[tipo];
      return next;
    });
  }

  if (cargando) {
    return (
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-md">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-[120px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
        ))}
      </div>
    );
  }

  if (configs.length === 0) {
    return (
      <div className="rounded-2xl border border-outline-variant/60 bg-white py-12 text-center text-on-surface-variant space-y-base">
        <Icon name="rule_settings" className="text-[32px] text-outline" />
        <p className="text-[13px]">No hay configuración de scoring cargada. Contactá al administrador del sistema.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-outline-variant/40">
      {/* Encabezado editorial + leyenda de rangos. El separador con el
          contenido de abajo lo da divide-y del contenedor. */}
      <div className="space-y-4 pb-lg">
        <div>
          <h2 className="font-headline text-[24px] font-bold text-on-surface tracking-tight leading-tight">Scoring</h2>
          <p className="text-[13.5px] text-on-surface-variant leading-relaxed max-w-2xl mt-2">
            Definí cuántos puntos suma cada tipo de evento al <strong>score de riesgo</strong> y su
            severidad. El on/off de cada evento se maneja en <strong>Parámetros generales →
            Detectores</strong>; acá solo ajustás el peso.
          </p>
        </div>
        {/* Leyenda de rangos: punto de color + nombre + rango. Limpia y alineada. */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-3 border-t border-outline-variant/40">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">Escala de severidad</span>
          {SEVERIDADES.map((s) => {
            const { min, max } = rangoDeSeveridad(s);
            return (
              <span key={s} className="inline-flex items-center gap-2 text-[12.5px]">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${SEVERITY_DOT[s]}`} aria-hidden />
                <span className="font-semibold text-on-surface">{SEVERIDAD_LABEL[s]}</span>
                <span className="text-on-surface-variant tabular-nums">{min}–{max}</span>
              </span>
            );
          })}
        </div>
      </div>

      <div className="py-lg space-y-lg">
        {/* Aviso inline al inicio: los pesos solo afectan cálculos futuros. */}
        <div className="flex items-center gap-2.5 rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-[13px] text-blue-900">
          <Icon name="info" className="text-[20px] text-blue-600 shrink-0" fill />
          <span>Cambiar los pesos no modifica eventos pasados; solo afecta el cálculo del score en futuros exámenes.</span>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-lg min-w-0">
          {[...configs]
            .sort((a, b) => (SEV_ORDER[severidadEditable(a.severidad as Severidad)] ?? 4) - (SEV_ORDER[severidadEditable(b.severidad as Severidad)] ?? 4))
            .map((cfg) => {
            const editado = tieneEdicion(cfg.tipo_evento);
            const sev = severidadEditable(valorActual(cfg, 'severidad') as Severidad);
            const peso = valorActual(cfg, 'peso') as number;
            const isGuardando = guardando === cfg.tipo_evento;
            return (
              <div
                key={cfg.tipo_evento}
                className="relative overflow-hidden rounded-xl border border-outline-variant/50 bg-white hover:border-outline p-6 transition-colors min-w-0 flex flex-col gap-4"
              >
              {/* Línea fina de color arriba, recortada por las esquinas redondeadas. */}
              <div className={`absolute top-0 left-0 right-0 h-1 ${SEVERITY_DOT[sev]}`} aria-hidden />
              {/* Cabecera: badge de severidad + nombre. El on/off del evento vive en
                  Parámetros generales → Detectores (un solo interruptor). Acá solo se
                  configura cuánto pesa y su severidad. */}
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 inline-flex items-center justify-center w-16 py-0.5 rounded-full text-[11px] font-semibold shrink-0 ${SEVERITY_BADGE_COLORS[sev]}`}>
                  {SEVERIDAD_LABEL[sev]}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-on-surface">
                    {TIPO_EVENTO_LABEL[cfg.tipo_evento as TipoEvento] ?? cfg.tipo_evento}
                  </p>
                  {cfg.descripcion && (
                    <p className="text-[12px] text-on-surface-variant mt-0.5">{cfg.descripcion}</p>
                  )}
                </div>
              </div>

              {/* Fila de controles: Severidad + Impacto en grilla alineada (E: alineación prolija) */}
              <div className="border-t border-outline-variant/40 pt-3 grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">Severidad</span>
                  <select
                    value={sev}
                    onChange={(e) => setSeveridad(cfg, e.target.value as SeveridadEditable)}
                    className="text-[13px] px-2.5 py-1.5 rounded-xl border border-outline-variant bg-white hover:border-outline focus:outline-none focus:border-surface-500 transition-colors"
                    disabled={isGuardando}
                    aria-label={`Severidad de ${cfg.tipo_evento}`}
                  >
                    {SEVERIDADES.map((s) => (
                      <option key={s} value={s}>{SEVERIDAD_LABEL[s]} ({rangoDeSeveridad(s).min}–{rangoDeSeveridad(s).max} pts)</option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant" title={`Puntos que suma este evento al score (rango permitido para severidad ${SEVERIDAD_LABEL[sev]}: ${rangoDeSeveridad(sev).min}–${rangoDeSeveridad(sev).max})`}>
                    Impacto ({rangoDeSeveridad(sev).min}–{rangoDeSeveridad(sev).max} pts)
                  </span>
                  <select
                    value={String(peso)}
                    onChange={(e) => setDraft(cfg.tipo_evento, 'peso', parseInt(e.target.value, 10))}
                    className="w-full px-2.5 py-1.5 text-[13px] rounded-xl border border-outline-variant bg-white font-mono hover:border-outline focus:outline-none focus:border-surface-500 transition-colors"
                    disabled={isGuardando}
                    aria-label={`Impacto en el score de ${cfg.tipo_evento} (rango ${rangoDeSeveridad(sev).min} a ${rangoDeSeveridad(sev).max} puntos)`}
                  >
                    {Array.from(
                      { length: rangoDeSeveridad(sev).max - rangoDeSeveridad(sev).min + 1 },
                      (_, k) => rangoDeSeveridad(sev).min + k,
                    ).map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>
              </div>

              {/* Acciones de la card (solo si hay edición). Descartar = outline;
                  Guardar = primary (color institucional #004BA8). */}
              {editado && (
                <div className="flex items-center justify-end gap-1.5 pt-1">
                  <Button size="sm" variant="ghost" onClick={() => descartar(cfg.tipo_evento)} disabled={isGuardando}>
                    Descartar
                  </Button>
                  <Button size="sm" variant="primary" icon="save" onClick={() => guardar(cfg)} disabled={isGuardando}>
                    {isGuardando ? '…' : 'Guardar'}
                  </Button>
                </div>
              )}
            </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
