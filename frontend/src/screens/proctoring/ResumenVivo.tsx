/**
 * ResumenVivo — Fila de stat-cards de la vista de supervisión EN VIVO.
 *
 * Métricas agregadas del lote actual de sesiones: activas, eventos totales,
 * discrepancias totales y sesiones que superan el umbral de riesgo alto. El tono
 * de cada tarjeta vira a error/success según el dato, como señal visual sobria.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { StatCard } from './StatCard';
import { statProps } from './statCatalog';
import { nivelRiesgo } from './helpers';

export function ResumenVivo({ sesiones }: { sesiones: SesionProctoringResumen[] }) {
  const activas = sesiones.length;
  const totalEventos = sesiones.reduce((acc, s) => acc + (s.total_eventos ?? 0), 0);
  const totalDiscrepancias = sesiones.reduce((acc, s) => acc + (s.total_discrepancias ?? 0), 0);
  const riesgoAlto = sesiones.filter((s) => nivelRiesgo(s.score ?? 0, s.umbral_cola_revision_efectivo) === 'alto').length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-md">
      {/* Cada card con un color BASE FIJO y distinto: nunca dos del mismo color,
          incluso cuando discrepancias y riesgo están ambos en 0. */}
      <StatCard {...statProps('sesionesActivas', activas)} />
      <StatCard {...statProps('eventos', totalEventos, 'en el lote actual')} />
      <StatCard {...statProps('discrepancias', totalDiscrepancias)} />
      <StatCard {...statProps('riesgoAlto', riesgoAlto)} />
    </div>
  );
}

export default ResumenVivo;
