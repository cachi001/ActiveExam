/**
 * ConfigSnapshotCard — foto de la config de scoring vigente al CREAR la sesión
 * (migration 0083: `config_snapshot`). Un cambio posterior del umbral/pesos NO
 * afecta retroactivamente a una sesión ya rendida — esta card lo hace visible.
 *
 * Sin snapshot (sesión pre-migración o config no disponible al crearla) no
 * renderiza nada: no hay foto que mostrar, y decir "se usó la config viva" no
 * aporta al revisor.
 */
import { Icon, Card } from '../../ui/components';
import type { SesionProctoringDetalle } from '../../lib/types';
import { humanizarLabel } from './helpers';

export function ConfigSnapshotCard({ detalle }: { detalle: SesionProctoringDetalle }) {
  const snapshot = detalle.config_snapshot;
  if (!snapshot) return null;

  const pesos = Object.entries(snapshot.scoring_weights ?? {}).sort((a, b) => b[1] - a[1]);
  const desactivados = snapshot.scoring_desactivados ?? [];

  return (
    <Card className="space-y-sm">
      <div className="flex items-center gap-sm">
        <Icon name="photo_camera" className="text-[18px] text-on-surface-variant" />
        <p className="text-label-md font-semibold text-on-surface">
          Config de scoring vigente al rendir esta sesión
        </p>
      </div>
      <p className="text-label-sm text-on-surface-variant">
        Foto tomada al crear la sesión. Si la configuración del sistema cambió después, esta
        sesión sigue evaluada con estos valores.
      </p>

      <div className="flex flex-wrap gap-sm">
        <div className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-md py-sm">
          <p className="text-[11px] font-semibold text-on-surface-variant">Umbral de cola de revisión</p>
          <p className="text-body-md font-semibold text-on-surface tabular-nums">
            {snapshot.umbral_cola_revision} pts
          </p>
        </div>
      </div>

      {pesos.length > 0 && (
        <div className="space-y-xs">
          <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
            Pesos por tipo de evento
          </p>
          <div className="flex flex-wrap gap-xs">
            {pesos.map(([tipo, peso]) => (
              <span
                key={tipo}
                className="inline-flex items-center gap-base rounded-full border border-outline-variant/40 bg-surface-container-lowest px-sm py-[2px] text-label-sm text-on-surface-variant"
              >
                {humanizarLabel(tipo)}
                <span className="font-semibold text-on-surface tabular-nums">{peso}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {desactivados.length > 0 && (
        <div className="space-y-xs">
          <p className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wide">
            Detectores desactivados
          </p>
          <div className="flex flex-wrap gap-xs">
            {desactivados.map((tipo) => (
              <span
                key={tipo}
                className="inline-flex items-center rounded-full border border-outline-variant/40 bg-surface-container-lowest px-sm py-[2px] text-label-sm text-on-surface-variant"
              >
                {humanizarLabel(tipo)}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default ConfigSnapshotCard;
