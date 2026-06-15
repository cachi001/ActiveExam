/**
 * SeccionProctoring — parámetros globales de proctoring (default por examen).
 *
 * Cableada al endpoint real PATCH /api/v1/config (admin_sistema + MFA).
 * Carga la config efectiva al montar para pre-popular los campos.
 * Invalida el cache local de config efectiva tras guardar.
 */
import { useState, useEffect } from 'react';
import { Card, SectionTitle, Button, RangeInput, FormField } from '../../ui/components';
import { useToast } from '../../ui/toast';
import DetectoresSelector from '../admin/components/DetectoresSelector';
import { api } from '../../lib/api';
import { resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import type { TipoEvento } from '../../lib/types';

const DETECTORES_DEFAULT: TipoEvento[] = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida', 'perdida_de_foco', 'monitor_adicional',
];

export default function SeccionProctoring() {
  const toast = useToast();
  const [umbral, setUmbral] = useState(70);
  const [detectores, setDetectores] = useState<TipoEvento[]>(DETECTORES_DEFAULT);
  const [retencion, setRetencion] = useState(30);
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  // Cargar config efectiva al montar para pre-popular los valores actuales.
  useEffect(() => {
    api.obtenerConfigEfectiva()
      .then((cfg) => {
        setUmbral(cfg.umbral_cola_revision);
        setRetencion(cfg.retencion_dias_default);
        setDetectores(cfg.detectores_activos as TipoEvento[]);
      })
      .catch((e) => toast.error(`No se pudo cargar la configuración: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setCargando(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function guardar() {
    setGuardando(true);
    try {
      await api.editarConfigSistema({
        umbral_cola_revision: umbral,
        detectores_activos: detectores,
        retencion_dias_default: retencion,
      });
      // Invalida el cache de config efectiva para que el examen y el harness
      // carguen la nueva config en la próxima sesión (task 4.5).
      resetEffectiveConfigCache();
      toast.success('Parámetros de proctoring guardados');
    } catch (e) {
      toast.error(`Error al guardar: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return (
      <div className="space-y-lg max-w-5xl">
        <div className="h-[200px] rounded-2xl border border-outline-variant/40 bg-white animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-lg max-w-5xl">
      <div className="grid lg:grid-cols-2 gap-lg items-start">
        <Card className="space-y-md">
          <SectionTitle sub="Política de priorización y privacidad">Umbral y retención</SectionTitle>
          <RangeInput
            label="Umbral de cola de revisión"
            unit="%"
            min={30}
            max={90}
            value={umbral}
            onChange={setUmbral}
            hint="Sesiones que superen este score al finalizar entran a revisión humana."
          />
          <FormField
            label="Retención de evidencia (días)"
            hint="Los datos se eliminan automáticamente al vencer el plazo (mínimo 7 días)."
          >
            <input
              type="number"
              min={7}
              max={365}
              value={retencion}
              onChange={(e) => setRetencion(Number(e.target.value))}
              className="w-32 px-sm py-base rounded-xl border border-outline-variant bg-white font-mono text-label-md focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </FormField>
        </Card>

        <Card className="space-y-md">
          <SectionTitle sub="Qué eventos se vigilan por defecto">Detectores activos</SectionTitle>
          <DetectoresSelector value={detectores} onChange={setDetectores} />
        </Card>
      </div>

      <div className="flex justify-end">
        <Button icon="save" onClick={guardar} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar parámetros'}
        </Button>
      </div>
    </div>
  );
}
