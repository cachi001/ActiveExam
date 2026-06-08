/**
 * ResumenSesiones — Fila de tarjetas con métricas agregadas de la lista.
 *
 * Muestra total de sesiones, eventos y discrepancias. El tono de la tarjeta de
 * discrepancias pasa a error cuando hay alguna, como señal visual sobria.
 */
import type { SesionProctoringResumen } from '../../lib/types';
import { StatCard } from './StatCard';

export function ResumenSesiones({ sesiones }: { sesiones: SesionProctoringResumen[] }) {
  const totalSesiones = sesiones.length;
  const totalEventos = sesiones.reduce((acc, s) => acc + (s.total_eventos ?? 0), 0);
  const totalDiscrepancias = sesiones.reduce((acc, s) => acc + (s.total_discrepancias ?? 0), 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
      <StatCard icon="video_library" label="Sesiones" value={totalSesiones} tono="primary" />
      <StatCard icon="notifications" label="Eventos" value={totalEventos} tono="neutral" />
      <StatCard
        icon="rule"
        label="Discrepancias"
        value={totalDiscrepancias}
        tono={totalDiscrepancias > 0 ? 'error' : 'success'}
      />
    </div>
  );
}

export default ResumenSesiones;
