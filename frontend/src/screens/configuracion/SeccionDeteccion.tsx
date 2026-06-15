/**
 * SeccionDeteccion — umbrales del motor de detección (default del sistema).
 *
 * Cableada al endpoint real PATCH /api/v1/config (admin_sistema + MFA).
 * Muestra la escala amigable (segundos, sensibilidad baja/media/alta) y convierte
 * a unidades internas antes de enviar (D6 — la UI nunca manda la escala cruda).
 * Invalida el cache local de config efectiva tras guardar.
 */
import { useState, useEffect } from 'react';
import { Card, SectionTitle, Button } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import {
  toFriendly, toInternal,
  SENSIBILIDAD_OPTIONS,
  segToMs,
  framesToDisplay,
} from '../../config/configScale';
import type { ConfigFriendly, SensibilidadLabel } from '../../config/configScale';

// Defaults amigables (reflejan DEFAULT_CONFIG de stateTransitionRules.ts)
const DEFAULTS_FRIENDLY: ConfigFriendly = {
  face_absent_seg: 3,
  multiple_faces_display: 5,
  gaze_deviation_label: 'media',
  gaze_sustained_seg: 2.5,
  gaze_fixation_label: 'media',
  umbral_cola_revision: 70,
  retencion_dias_default: 30,
};

export default function SeccionDeteccion() {
  const toast = useToast();
  const [friendly, setFriendly] = useState<ConfigFriendly>(DEFAULTS_FRIENDLY);
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => {
        setFriendly(toFriendly(cfg));
      })
      .catch((e) => toast.error(`No se pudo cargar la configuración: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function guardar() {
    setGuardando(true);
    try {
      // Convierte a unidades internas ANTES del PATCH (D6).
      const internal = toInternal(friendly);
      await api.editarConfigSistema({
        face_absent_ms: internal.face_absent_ms,
        multiple_faces_frames: internal.multiple_faces_frames,
        gaze_deviation_threshold: internal.gaze_deviation_threshold,
        gaze_sustained_ms: internal.gaze_sustained_ms,
        gaze_fixation_tolerance: internal.gaze_fixation_tolerance,
      });
      resetEffectiveConfigCache();
      toast.success('Umbrales de detección guardados');
    } catch (e) {
      toast.error(`Error al guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  function restaurarDefaults() {
    setFriendly(DEFAULTS_FRIENDLY);
  }

  if (cargando) {
    return (
      <div className="h-[300px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse max-w-4xl" />
    );
  }

  return (
    <Card className="space-y-md max-w-4xl">
      <SectionTitle sub="Defaults conservadores — minimizan falsos positivos">Umbrales de detección</SectionTitle>
      <p className="text-label-sm text-on-surface-variant">
        Estos valores definen cuándo el sistema emite una alerta. Valores más altos en tiempo significan
        más paciencia antes de alertar; sensibilidad "alta" dispara más fácil.
      </p>

      <div className="grid sm:grid-cols-2 gap-md">
        {/* face_absent_ms → segundos */}
        <div className="space-y-base">
          <label className="block">
            <span className="text-label-sm font-semibold text-on-surface">
              Tiempo sin rostro para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
            </span>
          </label>
          <p className="text-[11px] text-on-surface-variant">Tiempo sin detectar un rostro antes de emitir una alerta.</p>
          <input
            type="number"
            step={0.1}
            min={0.5}
            max={30}
            inputMode="decimal"
            value={friendly.face_absent_seg}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) setFriendly((p) => ({ ...p, face_absent_seg: v }));
            }}
            className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
          <p className="text-[10px] text-on-surface-variant/70 font-mono">
            → {segToMs(friendly.face_absent_seg)} ms internos
          </p>
        </div>

        {/* multiple_faces_frames → "N detecciones seguidas" */}
        <div className="space-y-base">
          <label className="block">
            <span className="text-label-sm font-semibold text-on-surface">
              Detecciones seguidas con varios rostros
            </span>
          </label>
          <p className="text-[11px] text-on-surface-variant">Fotogramas consecutivos con más de un rostro para alertar.</p>
          <input
            type="number"
            step={1}
            min={1}
            max={100}
            value={framesToDisplay(friendly.multiple_faces_display)}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) setFriendly((p) => ({ ...p, multiple_faces_display: v }));
            }}
            className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>

        {/* gaze_deviation_threshold → sensibilidad baja/media/alta */}
        <div className="space-y-base">
          <label className="block">
            <span className="text-label-sm font-semibold text-on-surface">
              Sensibilidad de detección de mirada desviada
            </span>
          </label>
          <p className="text-[11px] text-on-surface-variant">
            Alta = más alertas (mayor precisión); Baja = menos alertas (más tolerancia).
          </p>
          <div className="flex gap-sm">
            {SENSIBILIDAD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFriendly((p) => ({ ...p, gaze_deviation_label: opt.value as SensibilidadLabel }))}
                className={`flex-1 py-sm px-base rounded-xl border text-label-sm font-medium transition-colors ${
                  friendly.gaze_deviation_label === opt.value
                    ? 'bg-primary text-on-primary border-primary'
                    : 'bg-white text-on-surface border-outline-variant hover:border-primary/50'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-on-surface-variant/70">
            {SENSIBILIDAD_OPTIONS.find((o) => o.value === friendly.gaze_deviation_label)?.desc}
          </p>
        </div>

        {/* gaze_sustained_ms → segundos */}
        <div className="space-y-base">
          <label className="block">
            <span className="text-label-sm font-semibold text-on-surface">
              Tiempo de mirada desviada para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
            </span>
          </label>
          <p className="text-[11px] text-on-surface-variant">Tiempo continuo mirando hacia un lado antes de alertar.</p>
          <input
            type="number"
            step={0.1}
            min={0.5}
            max={30}
            inputMode="decimal"
            value={friendly.gaze_sustained_seg}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) setFriendly((p) => ({ ...p, gaze_sustained_seg: v }));
            }}
            className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
          <p className="text-[10px] text-on-surface-variant/70 font-mono">
            → {segToMs(friendly.gaze_sustained_seg)} ms internos
          </p>
        </div>

        {/* gaze_fixation_tolerance → sensibilidad baja/media/alta */}
        <div className="space-y-base sm:col-span-2">
          <label className="block">
            <span className="text-label-sm font-semibold text-on-surface">
              Tolerancia de fijación de mirada
            </span>
          </label>
          <p className="text-[11px] text-on-surface-variant">
            Alta = más alertas (exige que la mirada no se mueva); Baja = permite más variación natural.
          </p>
          <div className="flex gap-sm max-w-sm">
            {SENSIBILIDAD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFriendly((p) => ({ ...p, gaze_fixation_label: opt.value as SensibilidadLabel }))}
                className={`flex-1 py-sm px-base rounded-xl border text-label-sm font-medium transition-colors ${
                  friendly.gaze_fixation_label === opt.value
                    ? 'bg-primary text-on-primary border-primary'
                    : 'bg-white text-on-surface border-outline-variant hover:border-primary/50'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-on-surface-variant/70">
            {SENSIBILIDAD_OPTIONS.find((o) => o.value === friendly.gaze_fixation_label)?.desc}
          </p>
        </div>
      </div>

      <div className="flex justify-end gap-sm pt-sm border-t border-outline-variant/40">
        <Button variant="ghost" icon="undo" onClick={restaurarDefaults}>Restaurar defaults</Button>
        <Button icon="save" onClick={guardar} disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar umbrales'}</Button>
      </div>
    </Card>
  );
}
