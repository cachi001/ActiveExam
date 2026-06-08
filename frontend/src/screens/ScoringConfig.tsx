/**
 * ScoringConfig — pantalla admin para editar pesos por tipo de evento (#10).
 *
 * Lista los 8 tipos del catalogo persistidos en `evento_score_config` (migracion 0011).
 * Permite editar peso (0-100), severidad y activar/desactivar cada tipo.
 *
 * Solo admin_sistema. El backend valida CHECK constraints (severidad valida, peso 0..100).
 */
import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { HelpButton } from '../ui/HelpButton';
import { api, SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from '../lib/api';
import type { EventoScoreConfig, Severidad, TipoEvento } from '../lib/types';
import { SEVERITY_BADGE_COLORS } from './harness/helpers';
import { resetScoringWeightsCache } from '../proctoring/scoringWeights';

const SEVERIDADES: Severidad[] = ['baseline', 'baja', 'media', 'alta', 'critica'];

export default function ScoringConfig() {
  const toast = useToast();
  const [configs, setConfigs] = useState<EventoScoreConfig[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState<string | null>(null);
  // Edits locales por tipo_evento — se persisten al "Guardar" de cada fila.
  const [drafts, setDrafts] = useState<Record<string, Partial<EventoScoreConfig>>>({});

  useEffect(() => {
    cargar();
  }, []);

  async function cargar() {
    setCargando(true);
    try {
      const res = await api.listarScoringConfig();
      setConfigs(res.items);
      setDrafts({});
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`No se pudo cargar la configuracion: ${msg}`);
    } finally {
      setCargando(false);
    }
  }

  function setDraft<K extends keyof EventoScoreConfig>(
    tipo: string,
    field: K,
    value: EventoScoreConfig[K],
  ) {
    setDrafts((prev) => ({ ...prev, [tipo]: { ...prev[tipo], [field]: value } }));
  }

  function valorActual<K extends keyof EventoScoreConfig>(
    cfg: EventoScoreConfig,
    field: K,
  ): EventoScoreConfig[K] {
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
      // Invalidar el cache de pesos: si admin abre /admin/detection-test o un examen
      // a continuacion, va a refetchear los pesos actualizados de la BD.
      resetScoringWeightsCache();
      toast.success(`Guardado: ${TIPO_EVENTO_LABEL[cfg.tipo_evento as TipoEvento] ?? cfg.tipo_evento}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`No se pudo guardar: ${msg}`);
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

  return (
    <StaffShell nav={STAFF_NAV} title="Configuracion de scoring">
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* Subtitulo + ayuda */}
        <div className="flex items-start gap-2">
          <p className="text-[13px] text-on-surface-variant">
            Ajustá cuánto suma cada tipo de evento al score acumulado (0-100). Los cambios se aplican al próximo examen.
          </p>
          <HelpButton title="Configuración de scoring">
            <p>
              Cada tipo de evento tiene una <strong>severidad</strong> (baseline/baja/media/alta/critica) y un
              <strong> peso</strong> (0-100) que aporta al score acumulado del examen cuando se dispara.
            </p>
            <p>
              Los pesos default por severidad son: baja=5, media=20, alta=50, critica=100. Subí el peso
              para priorizar un tipo en la cola de revisión; bajalo para tolerar más antes de flaggear.
              Los cambios se aplican al próximo examen que arranque (el cliente refetchea al iniciar).
            </p>
            <p>
              <strong>Desactivar</strong> un tipo dejará de sumar score por ese evento (sin perder el registro
              histórico). El sistema <strong>nunca sanciona automáticamente</strong>: el score solo prioriza
              revisión humana (L2.5).
            </p>
          </HelpButton>
        </div>

        {/* Tabla / lista de configuraciones */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
          <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
            <Icon name="tune" className="text-[16px] text-primary shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">
              Pesos por tipo de evento
              <span className="text-on-surface-variant font-normal ml-1">({configs.length})</span>
            </h2>
          </div>

          {cargando ? (
            <div className="py-12 text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
            </div>
          ) : configs.length === 0 ? (
            <div className="py-12 text-center text-on-surface-variant space-y-base">
              <Icon name="rule_settings" className="text-[32px] text-outline" />
              <p className="text-[13px]">No hay configuración. ¿Aplicaste la migración 0011?</p>
            </div>
          ) : (
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-surface-container-low">
                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Tipo de evento</th>
                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5">Severidad</th>
                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5 w-24">Peso</th>
                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5 w-24">Activo</th>
                    <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2.5 w-44">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/30">
                  {configs.map((cfg) => {
                    const editado = tieneEdicion(cfg.tipo_evento);
                    const sev = valorActual(cfg, 'severidad') as Severidad;
                    const peso = valorActual(cfg, 'peso') as number;
                    const activo = valorActual(cfg, 'activo') as boolean;
                    const isGuardando = guardando === cfg.tipo_evento;
                    return (
                      <tr key={cfg.tipo_evento} className={`hover:bg-surface-container-low transition-colors ${editado ? 'bg-warning-container/20' : ''}`}>
                        <td className="px-4 py-3">
                          <div className="flex flex-col">
                            <span className="text-[13px] font-medium text-on-surface">
                              {TIPO_EVENTO_LABEL[cfg.tipo_evento as TipoEvento] ?? cfg.tipo_evento}
                            </span>
                            {cfg.descripcion && (
                              <span className="text-[11px] text-on-surface-variant mt-0.5 max-w-md">
                                {cfg.descripcion}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${SEVERITY_BADGE_COLORS[sev]}`}>
                              {SEVERIDAD_LABEL[sev]}
                            </span>
                            <select
                              value={sev}
                              onChange={(e) => setDraft(cfg.tipo_evento, 'severidad', e.target.value)}
                              className="text-[12px] px-2 py-1 rounded border border-outline-variant bg-surface-container-lowest"
                              disabled={isGuardando}
                              aria-label={`Severidad de ${cfg.tipo_evento}`}
                            >
                              {SEVERIDADES.map((s) => (
                                <option key={s} value={s}>
                                  {SEVERIDAD_LABEL[s]}
                                </option>
                              ))}
                            </select>
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={peso}
                            onChange={(e) => {
                              const raw = parseInt(e.target.value, 10);
                              if (isNaN(raw)) return;
                              const clamped = Math.max(0, Math.min(100, raw));
                              setDraft(cfg.tipo_evento, 'peso', clamped);
                            }}
                            className="w-20 px-2 py-1 text-[13px] rounded border border-outline-variant bg-surface-container-lowest font-mono"
                            disabled={isGuardando}
                            aria-label={`Peso de ${cfg.tipo_evento}`}
                          />
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <label className="inline-flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={activo}
                              onChange={(e) => setDraft(cfg.tipo_evento, 'activo', e.target.checked)}
                              className="w-4 h-4 accent-primary"
                              disabled={isGuardando}
                            />
                            <span className="text-[12px] text-on-surface-variant">{activo ? 'Sí' : 'No'}</span>
                          </label>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-right">
                          {editado ? (
                            <div className="inline-flex gap-1.5">
                              <Button size="sm" variant="ghost" onClick={() => descartar(cfg.tipo_evento)} disabled={isGuardando}>
                                Descartar
                              </Button>
                              <Button size="sm" variant="primary" icon="save" onClick={() => guardar(cfg)} disabled={isGuardando}>
                                {isGuardando ? 'Guardando…' : 'Guardar'}
                              </Button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-on-surface-variant italic">sin cambios</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Aviso legal L2.5 */}
        <div className="bg-primary-fixed/40 rounded-xl p-sm text-[12px] text-on-primary-fixed-variant flex items-start gap-base">
          <Icon name="shield" className="text-[16px] shrink-0" fill />
          <span>
            El score solo prioriza la cola de revisión humana — el sistema nunca sanciona automáticamente.
            Cambiar los pesos NO modifica eventos pasados; solo afecta el cálculo del score en futuros exámenes.
          </span>
        </div>
      </div>
    </StaffShell>
  );
}
