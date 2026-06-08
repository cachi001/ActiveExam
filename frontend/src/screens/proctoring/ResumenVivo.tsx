/**
 * ResumenVivo — Fila de stat-cards de la vista de supervisión EN VIVO.
 *
 * Métricas agregadas del lote actual de sesiones: activas, eventos totales,
 * discrepancias totales y sesiones que superan el umbral de riesgo alto. El tono
 * de cada tarjeta vira a error/success según el dato, como señal visual sobria.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { StatCard } from './StatCard';
import { nivelRiesgo, SCORE_UMBRAL_ALTO } from './helpers';

export function ResumenVivo({ sesiones }: { sesiones: SesionProctoringResumen[] }) {
  const activas = sesiones.length;
  const totalEventos = sesiones.reduce((acc, s) => acc + (s.total_eventos ?? 0), 0);
  const totalDiscrepancias = sesiones.reduce((acc, s) => acc + (s.total_discrepancias ?? 0), 0);
  const riesgoAlto = sesiones.filter((s) => nivelRiesgo(s.score ?? 0) === 'alto').length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-md">
      {/* Cada card con un color BASE distinto para que nunca se confundan entre sí. */}
      <StatCard icon="sensors" label="Sesiones activas" value={activas} tono="primary" />
      <StatCard icon="notifications" label="Eventos totales" value={totalEventos} tono="info" />
      <StatCard
        icon="rule"
        label="Discrepancias"
        value={totalDiscrepancias}
        tono={totalDiscrepancias > 0 ? 'warning' : 'neutral'}
      />
      <StatCard
        icon="priority_high"
        label={`Riesgo alto (≥${SCORE_UMBRAL_ALTO})`}
        value={riesgoAlto}
        tono={riesgoAlto > 0 ? 'error' : 'success'}
      />
    </div>
  );
}

export default ResumenVivo;
