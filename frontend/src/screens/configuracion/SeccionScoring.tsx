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
import { SEVERITY_BADGE_COLORS, SEVERITY_CARD_COLORS } from '../harness/helpers';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';

// baseline NO es un evento: es el piso 0 del score, no se elige por evento.
import {
  rangoDeSeveridad,
  type SeveridadEditable,
} from '../../config/severityRanges';

const SEVERIDADES: SeveridadEditable[] = ['baja', 'media', 'alta', 'critica'];

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
  // Texto en progreso del input de peso (permite vaciar/tipear libre sin clampear
  // en cada tecla; el clamp al rango se aplica en onBlur). Sin esto, borrar un
  // digito o tipear un valor intermedio salta al min/max y no se puede llegar a 8.
  const [pesoText, setPesoText] = useState<Record<string, string>>({});

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
      setPesoText((prev) => {
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
    setPesoText((prev) => {
      const next = { ...prev };
      delete next[tipo];
      return next;
    });
  }

  if (cargando) {
    return (
      <div className="grid md:grid-cols-2 gap-md max-w-4xl">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-[120px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
        ))}
      </div>
    );
  }

  if (configs.length === 0) {
    return (
      <div className="rounded-2xl border border-outline-variant/60 bg-white py-12 text-center text-on-surface-variant space-y-base">
        <Icon name="rule_settings" className="text-[32px] text-outline" />
        <p className="text-[13px]">No hay configuración. ¿Aplicaste la migración 0011?</p>
      </div>
    );
  }

  return (
    <div className="space-y-lg max-w-4xl">
      {/* Título + chips de rangos por severidad (compactos, una sola línea) */}
      <div className="space-y-sm">
        <div>
          <h2 className="font-headline text-title-xl text-on-surface tracking-tight">Scoring</h2>
          <p className="text-[13px] text-on-surface-variant mt-1">
            Cuántos puntos suma cada tipo de evento al score de riesgo.
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap text-[12px]">
          <span className="text-on-surface-variant">Rangos:</span>
          <span className="inline-flex items-baseline gap-1.5 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-semibold"><span>Baja</span><span className="font-normal tabular-nums opacity-80">1–10</span></span>
          <span className="inline-flex items-baseline gap-1.5 px-2 py-0.5 rounded-full bg-warning-container text-warning font-semibold"><span>Media</span><span className="font-normal tabular-nums opacity-80">11–30</span></span>
          <span className="inline-flex items-baseline gap-1.5 px-2 py-0.5 rounded-full bg-error-container text-on-error-container font-semibold"><span>Alta</span><span className="font-normal tabular-nums opacity-80">31–60</span></span>
          <span className="inline-flex items-baseline gap-1.5 px-2 py-0.5 rounded-full bg-error text-on-error font-semibold"><span>Crítica</span><span className="font-normal tabular-nums opacity-80">61–100</span></span>
        </div>
      </div>

      {/* Aviso inline al inicio: los pesos solo afectan cálculos futuros. */}
      <div className="flex items-center gap-2.5 rounded-xl bg-surface-container border border-outline-variant/40 px-4 py-3 text-[13px] text-on-surface-variant">
        <Icon name="info" className="text-[20px] text-primary shrink-0" fill />
        <span>Cambiar los pesos no modifica eventos pasados; solo afecta el cálculo del score en futuros exámenes.</span>
      </div>

      <div className="grid md:grid-cols-2 gap-md min-w-0">
        {configs.map((cfg) => {
          const editado = tieneEdicion(cfg.tipo_evento);
          const sev = severidadEditable(valorActual(cfg, 'severidad') as Severidad);
          const peso = valorActual(cfg, 'peso') as number;
          const isGuardando = guardando === cfg.tipo_evento;
          return (
            <div
              key={cfg.tipo_evento}
              className={`rounded-2xl border shadow-card p-5 transition-colors min-w-0 flex flex-col gap-3 ${SEVERITY_CARD_COLORS[sev]} ${
                editado ? 'ring-2 ring-primary/40' : ''
              }`}
            >
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
                    className="text-[13px] px-2.5 py-1.5 rounded-xl border border-outline-variant bg-white hover:border-outline focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
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
                  <input
                    type="number"
                    min={rangoDeSeveridad(sev).min}
                    max={rangoDeSeveridad(sev).max}
                    value={pesoText[cfg.tipo_evento] ?? String(peso)}
                    onChange={(e) => {
                      const text = e.target.value;
                      setPesoText((p) => ({ ...p, [cfg.tipo_evento]: text }));
                      // Guardamos el valor tipeado SIN clampear (el clamp es en onBlur),
                      // para poder llegar a valores intermedios como 8.
                      const raw = parseInt(text, 10);
                      if (!isNaN(raw)) setDraft(cfg.tipo_evento, 'peso', raw);
                    }}
                    onBlur={() => {
                      // Al salir del campo: clampeamos al rango de la severidad y
                      // sincronizamos el texto al valor final (o al actual si quedó vacío).
                      const parsed = parseInt(pesoText[cfg.tipo_evento] ?? '', 10);
                      const ajustado = ajustarPesoARango(isNaN(parsed) ? peso : parsed, sev);
                      setDraft(cfg.tipo_evento, 'peso', ajustado);
                      setPesoText((p) => {
                        const next = { ...p };
                        delete next[cfg.tipo_evento];
                        return next;
                      });
                    }}
                    className="w-full px-2.5 py-1.5 text-[13px] rounded-xl border border-outline-variant bg-white font-mono hover:border-outline focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                    disabled={isGuardando}
                    aria-label={`Impacto en el score de ${cfg.tipo_evento} (rango ${rangoDeSeveridad(sev).min} a ${rangoDeSeveridad(sev).max} puntos)`}
                  />
                </label>
              </div>

              {/* Acciones de la card (solo si hay edición). Descartar = outline;
                  Guardar = primary (color institucional #004BA8). */}
              {editado && (
                <div className="flex items-center justify-end gap-1.5 pt-1">
                  <Button size="sm" variant="outline" onClick={() => descartar(cfg.tipo_evento)} disabled={isGuardando}>
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
  );
}
