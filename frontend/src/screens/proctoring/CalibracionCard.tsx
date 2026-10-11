/**
 * CalibracionCard — con qué cero se evaluó la mirada de esta sesión (migración
 * 0108: `calibracion`). Descriptiva, NUNCA evidencia (reglas duras #5/#6): no
 * participa del score, solo documenta el dato para quien revise la sesión.
 *
 * Sin calibración (sesión pre-migración, o sin cámara) no renderiza nada: no
 * hay nada que mostrar, y no calibrar ya se ve en el propio score/eventos.
 */
import { Icon, Card } from '../../ui/components';
import type { SesionProctoringDetalle } from '../../lib/types';

export function CalibracionCard({ detalle }: { detalle: SesionProctoringDetalle }) {
  const calibracion = detalle.calibracion;
  if (!calibracion) return null;

  const { centro, rango_x, rango_y, origen, muestras_por_punto } = calibracion;
  const tieneRango = rango_x !== null && rango_y !== null;

  return (
    <Card className="space-y-sm">
      <div className="flex items-center gap-sm">
        <Icon name="center_focus_strong" className="text-[18px] text-on-surface-variant" />
        <p className="text-label-md font-semibold text-on-surface">Calibración de mirada</p>
      </div>
      <p className="text-label-sm text-on-surface-variant">
        {origen === 'paso_previo'
          ? 'Calibró las 4 esquinas de la pantalla, en pantalla completa, antes de empezar.'
          : 'No calibró antes de empezar: el examen midió un solo punto de respaldo al arrancar.'}{' '}
        Con esto se evalúa su mirada — no contra un cero absoluto.
      </p>

      <div className="flex flex-wrap gap-sm">
        <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-md py-sm">
          <p className="text-[11px] font-semibold text-on-surface-variant">Centro (cero)</p>
          <p className="text-body-md font-semibold text-on-surface tabular-nums font-mono">
            x {centro.x.toFixed(3)} · y {centro.y.toFixed(3)}
          </p>
        </div>
        {tieneRango && (
          <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-md py-sm">
            <p className="text-[11px] font-semibold text-on-surface-variant">Rango medido (4 esquinas)</p>
            <p className="text-body-md font-semibold text-on-surface tabular-nums font-mono">
              x [{rango_x![0].toFixed(2)}, {rango_x![1].toFixed(2)}] · y [{rango_y![0].toFixed(2)},{' '}
              {rango_y![1].toFixed(2)}]
            </p>
          </div>
        )}
        <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-md py-sm">
          <p className="text-[11px] font-semibold text-on-surface-variant">Muestras por punto</p>
          <p className="text-body-md font-semibold text-on-surface tabular-nums">{muestras_por_punto}</p>
        </div>
      </div>
    </Card>
  );
}

export default CalibracionCard;
