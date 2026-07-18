/**
 * ResumenSesiones — Fila de tarjetas con métricas agregadas de la lista.
 *
 * Muestra total de sesiones, eventos y discrepancias. El tono de la tarjeta de
 * discrepancias pasa a error cuando hay alguna, como señal visual sobria.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { StatCard } from './StatCard';
import { statProps } from './statCatalog';

export function ResumenSesiones({ sesiones }: { sesiones: SesionProctoringResumen[] }) {
  const totalSesiones = sesiones.length;
  const totalEventos = sesiones.reduce((acc, s) => acc + (s.total_eventos ?? 0), 0);
  const totalDiscrepancias = sesiones.reduce((acc, s) => acc + (s.total_discrepancias ?? 0), 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
      <StatCard {...statProps('sesiones', totalSesiones, 'registradas en total')} />
      <StatCard {...statProps('eventos', totalEventos)} />
      <StatCard {...statProps('discrepancias', totalDiscrepancias)} />
    </div>
  );
}

export default ResumenSesiones;
