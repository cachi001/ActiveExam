import { Card, Icon } from '../../../ui/components';
import type { Examen } from '../../../lib/types';

const DETECTORES_TOTAL = 8; // rostro_ausente, multiples_rostros, mirada_desviada_sostenida, perdida_de_foco, monitor_adicional, cambio_pestana, salida_pantalla_completa, copiar_pegar

function formatearInicio(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('es-AR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface ExamenResumenCardProps {
  examen: Examen;
}

export default function ExamenResumenCard({ examen }: ExamenResumenCardProps) {
  const nombre = examen.nombre.trim() || '—';
  const catedra = examen.catedra.trim() || '—';
  const inicio = formatearInicio(examen.inicio);

  return (
    <Card className="space-y-md">
      <div className="grid sm:grid-cols-2 gap-md">
        <Row icon="assignment" label="Examen" value={nombre} />
        <Row icon="school" label="Cátedra" value={catedra} />
        <Row icon="schedule" label="Inicio" value={inicio} />
        <Row icon="timer" label="Duración" value={`${examen.duracion_min} minutos`} />
        <Row icon="shield" label="Umbral de revisión" value={`${examen.umbral_score}%`} />
        <Row
          icon="inventory_2"
          label="Retención de evidencia"
          value={`${examen.retencion_dias} días (Ley 25.326)`}
        />
      </div>
      <div className="pt-sm border-t border-outline-variant/40">
        <div className="flex items-start gap-sm">
          <Icon name="visibility" className="text-[18px] text-on-surface-variant shrink-0 mt-[1px]" />
          <div>
            <p className="text-label-sm text-on-surface-variant">
              <span className="font-semibold text-on-surface">
                {examen.detectores.length} de {DETECTORES_TOTAL}
              </span>{' '}
              detectores activos
            </p>
            <p className="text-label-sm text-on-surface-variant mt-base">
              Priorizan sesiones para revisión humana, no sancionan.
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}

function Row({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-start gap-sm">
      <Icon name={icon} className="text-[18px] text-on-surface-variant shrink-0 mt-[1px]" />
      <div className="min-w-0">
        <p className="text-label-sm text-on-surface-variant">{label}</p>
        <p className="text-label-md font-semibold text-on-surface truncate">{value}</p>
      </div>
    </div>
  );
}
