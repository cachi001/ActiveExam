/**
 * SeccionScoring — pesos de scoring por tipo de evento (#10 / migracion 0011).
 *
 * Sección de la página Configuración del sistema. Lista los tipos del catalogo
 * persistidos en `evento_score_config` como tarjetas blancas en grilla de 2
 * columnas, con severidad, peso (0-100) y un toggle activo por tipo.
 *
 * C-68 UX:
 *  - Toggle movido a esquina superior derecha de la card (fuera de la fila Sev/Impacto).
 *  - Toggle rojo cuando DESACTIVADO, verde cuando ACTIVADO.
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
const SEVERIDADES: Severidad[] = ['baja', 'media', 'alta', 'critica'];

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
      {/* B: Título propio de la sección */}
      <div>
        <h2 className="font-headline text-title-xl text-on-surface tracking-tight">Scoring</h2>
        <p className="text-[13px] text-on-surface-variant mt-1">
          Cuánto suma cada tipo de evento al puntaje de riesgo (0–100) que prioriza la revisión humana.
          A mayor impacto, más peso tiene ese evento para que una persona revise la sesión.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-md min-w-0">
        {configs.map((cfg) => {
          const editado = tieneEdicion(cfg.tipo_evento);
          const sev = valorActual(cfg, 'severidad') as Severidad;
          const peso = valorActual(cfg, 'peso') as number;
          const activo = valorActual(cfg, 'activo') as boolean;
          const isGuardando = guardando === cfg.tipo_evento;
          return (
            <div
              key={cfg.tipo_evento}
              className={`rounded-2xl border shadow-card p-5 transition-colors min-w-0 flex flex-col gap-3 ${SEVERITY_CARD_COLORS[sev]} ${
                editado ? 'ring-2 ring-primary/40' : ''
              }`}
            >
              {/* Cabecera: badge + nombre + toggle activo (E: toggle en esquina superior derecha) */}
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
                {/* Toggle activo: verde=on, rojo=off (E: color semántico) */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={activo}
                  aria-label={`${activo ? 'Desactivar' : 'Activar'} ${cfg.tipo_evento}`}
                  onClick={() => setDraft(cfg.tipo_evento, 'activo', !activo)}
                  disabled={isGuardando}
                  title={activo ? 'Activo — clic para desactivar' : 'Inactivo — clic para activar'}
                  className={`relative shrink-0 inline-flex h-6 w-11 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50 ${
                    activo ? 'bg-success-600' : 'bg-error-600'
                  }`}
                >
                  <span className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${activo ? 'translate-x-5' : 'translate-x-0'}`} />
                </button>
              </div>

              {/* Fila de controles: Severidad + Impacto en grilla alineada (E: alineación prolija) */}
              <div className="border-t border-outline-variant/40 pt-3 grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">Severidad</span>
                  <select
                    value={sev}
                    onChange={(e) => setDraft(cfg.tipo_evento, 'severidad', e.target.value)}
                    className="text-[13px] px-2.5 py-1.5 rounded-xl border border-outline-variant bg-white hover:border-outline focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                    disabled={isGuardando}
                    aria-label={`Severidad de ${cfg.tipo_evento}`}
                  >
                    {SEVERIDADES.map((s) => (
                      <option key={s} value={s}>{SEVERIDAD_LABEL[s]}</option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant" title="Cuánto suma este evento al puntaje de riesgo (0–100) que prioriza la revisión humana">
                    Impacto en score
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={peso}
                    onChange={(e) => {
                      const raw = parseInt(e.target.value, 10);
                      if (isNaN(raw)) return;
                      setDraft(cfg.tipo_evento, 'peso', Math.max(0, Math.min(100, raw)));
                    }}
                    className="w-full px-2.5 py-1.5 text-[13px] rounded-xl border border-outline-variant bg-white font-mono hover:border-outline focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                    disabled={isGuardando}
                    aria-label={`Impacto en el score de ${cfg.tipo_evento}`}
                  />
                </label>
              </div>

              {/* Acciones de la card (solo si hay edición) */}
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

      {/* Nota inferior con padding correcto (E) */}
      <div className="bg-surface-container rounded-2xl p-lg text-[12px] text-on-surface-variant flex items-start gap-base border border-outline-variant/40">
        <Icon name="info" className="text-[16px] shrink-0" fill />
        <span>Cambiar los pesos no modifica eventos pasados; solo afecta el cálculo del score en futuros exámenes.</span>
      </div>
    </div>
  );
}
