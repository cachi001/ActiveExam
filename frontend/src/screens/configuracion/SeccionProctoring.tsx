/**
 * SeccionProctoring — parámetros generales del examen (default del sistema).
 *
 * Cableada al endpoint real PATCH /api/v1/config (admin_sistema + MFA).
 * Carga la config efectiva al montar para pre-popular los campos.
 * Invalida el cache local de config efectiva tras guardar.
 *
 * Nota (c-68): la retención de evidencia se quitó de esta UI por pedido del
 * dueño. El backend conserva su default (inofensivo); acá no se envía.
 *
 * C-68 UX: dirty-aware footer (Guardar/Cancelar solo cuando hay cambios).
 */
import { useState, useEffect, useCallback } from 'react';
import { Card, SectionTitle, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import DetectoresSelector from '../admin/components/DetectoresSelector';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import type { TipoEvento } from '../../lib/types';

const DETECTORES_DEFAULT: TipoEvento[] = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida', 'perdida_de_foco', 'monitor_adicional',
];

const UMBRAL_MIN = 30;
const UMBRAL_MAX = 90;

interface Estado {
  umbral: number;
  detectores: TipoEvento[];
}

function estadosIguales(a: Estado, b: Estado): boolean {
  return a.umbral === b.umbral &&
    a.detectores.length === b.detectores.length &&
    a.detectores.every((d) => b.detectores.includes(d));
}

export default function SeccionProctoring() {
  const toast = useToast();
  const [estado, setEstado] = useState<Estado>({ umbral: 70, detectores: DETECTORES_DEFAULT });
  const [inicial, setInicial] = useState<Estado>({ umbral: 70, detectores: DETECTORES_DEFAULT });
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  // Cargar config efectiva al montar para pre-popular los valores actuales.
  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => {
        const cargado: Estado = {
          umbral: cfg.umbral_cola_revision,
          detectores: cfg.detectores_activos as TipoEvento[],
        };
        setEstado(cargado);
        setInicial(cargado);
      })
      .catch((e) => toast.error(`No se pudo cargar la configuración: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dirty = !estadosIguales(estado, inicial);

  const cancelar = useCallback(() => setEstado(inicial), [inicial]);

  async function guardar() {
    setGuardando(true);
    try {
      await api.editarConfigSistema({
        umbral_cola_revision: estado.umbral,
        detectores_activos: estado.detectores,
      });
      // Invalida el cache de config efectiva para que el examen y el harness
      // carguen la nueva config en la próxima sesión (task 4.5).
      resetEffectiveConfigCache();
      setInicial(estado);
      toast.success('Parámetros generales guardados');
    } catch (e) {
      toast.error(`Error al guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="space-y-lg max-w-4xl">
        <div className="h-[200px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
      </div>
    );
  }

  const umbralPct = ((estado.umbral - UMBRAL_MIN) / (UMBRAL_MAX - UMBRAL_MIN)) * 100;

  return (
    <div className="space-y-lg max-w-4xl">
      {/* B: Título propio de la sección */}
      <div>
        <h2 className="font-headline text-title-xl text-on-surface tracking-tight">Parámetros generales</h2>
        <p className="text-[13px] text-on-surface-variant mt-1">
          Umbral de riesgo para revisión humana y detectores que vigila el sistema por defecto.
          Los cambios aplican a partir del próximo examen que arranque.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-lg items-stretch">
        <Card className="space-y-md min-w-0 flex flex-col">
          <SectionTitle sub="A partir de qué puntaje de riesgo una sesión entra a revisión humana">
            Umbral de revisión
          </SectionTitle>

          {/* Slider moderno: valor grande + track/thumb estilados con tokens */}
          <div className="flex items-baseline gap-2">
            <span className="text-[40px] leading-none font-headline font-bold text-on-surface tabular-nums">
              {estado.umbral}
            </span>
            <span className="text-title-md font-semibold text-on-surface-variant">%</span>
          </div>

          <div className="relative pt-1">
            <input
              type="range"
              min={UMBRAL_MIN}
              max={UMBRAL_MAX}
              value={estado.umbral}
              onChange={(e) => setEstado((p) => ({ ...p, umbral: Number(e.target.value) }))}
              aria-label="Umbral de cola de revisión"
              aria-valuetext={`${estado.umbral} por ciento`}
              className="ae-slider w-full appearance-none bg-transparent cursor-pointer"
              style={{
                background: `linear-gradient(to right, #4f46e5 0%, #4f46e5 ${umbralPct}%, #c7c4d6 ${umbralPct}%, #c7c4d6 100%)`,
              }}
            />
            <div className="flex justify-between text-[11px] text-on-surface-variant mt-2 tabular-nums">
              <span>{UMBRAL_MIN}% · más sesiones a revisión</span>
              <span>{UMBRAL_MAX}% · solo las más riesgosas</span>
            </div>
          </div>

          <p className="text-[12px] text-on-surface-variant leading-relaxed border-t border-outline-variant/40 pt-sm">
            Cuando una sesión termina con un puntaje de riesgo igual o mayor a este valor, queda marcada
            para que una persona la revise. Bajarlo manda más sesiones a revisión; subirlo deja solo las
            más sospechosas. El sistema nunca sanciona solo.
          </p>
        </Card>

        <Card className="space-y-md min-w-0 flex flex-col">
          <SectionTitle sub="Qué situaciones vigila el sistema por defecto durante el examen">
            Detectores activos
          </SectionTitle>
          <DetectoresSelector
            value={estado.detectores}
            onChange={(detectores) => setEstado((p) => ({ ...p, detectores }))}
          />
        </Card>
      </div>

      {/* C: Footer dirty-aware */}
      {dirty && (
        <div className="flex items-center justify-between gap-sm pt-sm border-t border-outline-variant/40">
          <div className="flex items-center gap-xs text-[12px] text-on-surface-variant">
            <Icon name="edit" className="text-[14px]" />
            Hay cambios sin guardar
          </div>
          <div className="flex gap-sm">
            <Button variant="outline" icon="undo" onClick={cancelar} disabled={guardando}>
              Cancelar
            </Button>
            <Button variant="success" icon="save" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar parámetros'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
