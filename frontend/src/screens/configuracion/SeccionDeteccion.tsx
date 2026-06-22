/**
 * SeccionDeteccion — umbrales del motor de detección (default del sistema).
 *
 * Cableada al endpoint real PATCH /api/v1/config (admin_sistema + MFA).
 * Muestra la escala amigable (segundos, sensibilidad baja/media/alta) y convierte
 * a unidades internas antes de enviar (D6 — la UI nunca manda la escala cruda).
 * Invalida el cache local de config efectiva tras guardar.
 *
 * C-68 UX:
 *  - Título de sección propio + descripción.
 *  - Agrupado en sub-secciones con sub-títulos (Rostro en cámara / Mirada).
 *  - Footer dirty-aware: Guardar/Cancelar solo visibles si hay cambios.
 *  - "Restaurar defaults" como botón outline (no texto pelado).
 */
import { useState, useEffect, useCallback } from 'react';
import { Card, SectionTitle, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import {
  toFriendly, toInternal,
  SENSIBILIDAD_OPTIONS,
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

function configsIguales(a: ConfigFriendly, b: ConfigFriendly): boolean {
  return (
    a.face_absent_seg === b.face_absent_seg &&
    a.multiple_faces_display === b.multiple_faces_display &&
    a.gaze_deviation_label === b.gaze_deviation_label &&
    a.gaze_sustained_seg === b.gaze_sustained_seg &&
    a.gaze_fixation_label === b.gaze_fixation_label
  );
}

export default function SeccionDeteccion() {
  const toast = useToast();
  const [friendly, setFriendly] = useState<ConfigFriendly>(DEFAULTS_FRIENDLY);
  const [inicial, setInicial] = useState<ConfigFriendly>(DEFAULTS_FRIENDLY);
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => {
        const cargado = toFriendly(cfg);
        setFriendly(cargado);
        setInicial(cargado);
      })
      .catch((e) => toast.error(`No se pudo cargar la configuración: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dirty = !configsIguales(friendly, inicial);

  const cancelar = useCallback(() => setFriendly(inicial), [inicial]);

  function restaurarDefaults() {
    setFriendly(DEFAULTS_FRIENDLY);
  }

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
      setInicial(friendly);
      toast.success('Umbrales de detección guardados');
    } catch (e) {
      toast.error(`Error al guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="h-[300px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse max-w-4xl" />
    );
  }

  return (
    <div className="space-y-lg max-w-4xl">
      {/* B: Título propio de la sección */}
      <div>
        <h2 className="font-headline text-title-xl text-on-surface tracking-tight">Detección</h2>
        <p className="text-[13px] text-on-surface-variant mt-1">
          Cuándo y con qué tolerancia el motor marca cada situación. Más tiempo equivale a menos falsas alarmas;
          mayor sensibilidad avisa con menos margen. Por defecto, valores conservadores para evitar molestias innecesarias.
        </p>
      </div>

      {/* F: Sub-sección "Rostro en cámara" */}
      <Card className="space-y-md">
        <SectionTitle sub="Cuándo el sistema alerta por ausencia o exceso de personas en cámara">
          Rostro en cámara
        </SectionTitle>

        <div className="grid sm:grid-cols-2 gap-md">
          {/* face_absent_ms → segundos */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Tiempo sin rostro para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuánto tiempo puede no verse un rostro antes de marcar el evento. Ej.: 3 segundos.
            </p>
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
          </div>

          {/* multiple_faces_frames → "N detecciones seguidas" */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Detecciones seguidas con varios rostros
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuántas veces seguidas se ve más de un rostro antes de marcar el evento. Ej.: 5 veces.
            </p>
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
        </div>
      </Card>

      {/* F: Sub-sección "Mirada" */}
      <Card className="space-y-md">
        <SectionTitle sub="Tolerancia y tiempo antes de alertar por mirada fuera de pantalla">
          Mirada
        </SectionTitle>

        <div className="grid sm:grid-cols-2 gap-md">
          {/* gaze_deviation_threshold → sensibilidad baja/media/alta */}
          <div className="space-y-base min-w-0">
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
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Tiempo de mirada desviada para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuánto tiempo seguido puede mirar hacia un lado antes de marcar el evento. Ej.: 2,5 segundos.
            </p>
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
          </div>

          {/* gaze_fixation_tolerance → sensibilidad baja/media/alta */}
          <div className="space-y-base min-w-0 sm:col-span-2">
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
      </Card>

      {/* C: Footer dirty-aware con Restaurar defaults como botón outline (C+F) */}
      <div className="flex items-center justify-between gap-sm pt-sm border-t border-outline-variant/40">
        {/* Restaurar defaults: siempre visible, estilo outline (C: no texto pelado) */}
        <Button variant="outline" icon="restart_alt" onClick={restaurarDefaults} disabled={guardando}>
          Restaurar defaults
        </Button>

        {dirty ? (
          <div className="flex items-center gap-sm">
            <div className="flex items-center gap-xs text-[12px] text-on-surface-variant mr-1">
              <Icon name="edit" className="text-[14px]" />
              Cambios sin guardar
            </div>
            <Button variant="outline" icon="undo" onClick={cancelar} disabled={guardando}>
              Cancelar
            </Button>
            <Button variant="success" icon="save" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar umbrales'}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
