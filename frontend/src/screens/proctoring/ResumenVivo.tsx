/**
 * ResumenVivo — Fila de stat-cards de la vista de supervisión EN VIVO.
 *
 * Métricas agregadas del lote actual de sesiones: activas, eventos totales,
 * discrepancias totales y sesiones que superan el umbral de riesgo alto. El tono
 * de cada tarjeta vira a error/success según el dato, como señal visual sobria.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { StatCard } from './StatCard';
import { nivelRiesgo } from './helpers';

export function ResumenVivo({ sesiones }: { sesiones: SesionProctoringResumen[] }) {
  const activas = sesiones.length;
  const totalEventos = sesiones.reduce((acc, s) => acc + (s.total_eventos ?? 0), 0);
  const totalDiscrepancias = sesiones.reduce((acc, s) => acc + (s.total_discrepancias ?? 0), 0);
  const riesgoAlto = sesiones.filter((s) => nivelRiesgo(s.score ?? 0) === 'alto').length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-md">
      {/* Cada card con un color BASE FIJO y distinto: nunca dos del mismo color,
          incluso cuando discrepancias y riesgo están ambos en 0. */}
      <StatCard icon="sensors" label="Sesiones activas" value={activas} sub="rindiendo ahora" tono="primary" />
      <StatCard icon="notifications" label="Eventos totales" value={totalEventos} sub="en el lote actual" tono="info" />
      <StatCard icon="rule" label="Discrepancias" value={totalDiscrepancias} sub="verificadas en server" tono="warning" />
      <StatCard icon="priority_high" label="Riesgo alto" value={riesgoAlto} sub="superan el umbral" tono="error" />
    </div>
  );
}

export default ResumenVivo;
