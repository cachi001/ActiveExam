/**
 * SeccionProctoring — parámetros globales de proctoring (default por examen).
 *
 * Antes vivían dentro de "Configurar examen" (por examen). Ahora son el default
 * del sistema: umbral de cola de revisión, detectores activos y retención de
 * evidencia. En modo demo el guardado es local (toast); con backend real iría a
 * un endpoint de configuración global.
 */
import { useState } from 'react';
import { Card, SectionTitle, Button, RangeInput, FormField } from '../../ui/components';
import { useToast } from '../../ui/toast';
import DetectoresSelector from '../admin/components/DetectoresSelector';
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

  async function guardar() {
    setGuardando(true);
    await new Promise((r) => setTimeout(r, 300));
    setGuardando(false);
    toast.success('Parámetros de proctoring guardados');
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
            hint="Por defecto 30 días. Los datos se eliminan automáticamente al vencer el plazo."
          >
            <input
              type="number"
              min={7}
              max={90}
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
