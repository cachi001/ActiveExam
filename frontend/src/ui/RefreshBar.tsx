// RefreshBar — barra de "última actualización + Actualizar" reutilizable.
//
// Se muestra arriba de páginas con tablas o dashboards que cargan datos del
// backend: indica el rango/estado de los datos y la hora de la última carga, y
// ofrece un botón para refrescar a demanda. El auto-refresh (cada 5 min) lo
// maneja `useAutoRefresh` en cada página; esta barra es solo presentacional.
import { Icon } from './components';

export interface RefreshBarProps {
  /** Texto principal (ej. "Todos los datos disponibles" o un rango de fechas). */
  texto?: string;
  /** Epoch ms de la última carga exitosa. Si viene, muestra "Actualizado: HH:MM". */
  lastUpdatedAt?: number;
  /** True mientras se está recargando (spinner + deshabilita el botón). */
  cargando: boolean;
  /** Callback del botón Actualizar. */
  onActualizar: () => void;
}

function formatHora(ts?: number): string {
  if (!ts) return '';
  return new Date(ts).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: true });
}

export function RefreshBar({ texto = 'Datos del sistema', lastUpdatedAt, cargando, onActualizar }: RefreshBarProps) {
  const hora = formatHora(lastUpdatedAt);
  return (
    <div className="mb-md flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-[13px] text-primary bg-primary/5 rounded-xl px-4 py-3 border border-primary/15">
      <div className="flex items-center gap-2">
        <Icon name="calendar_today" className="text-[16px] shrink-0" />
        <span>
          {texto}
          {hora && <span className="text-primary/60"> • Actualizado: {hora}</span>}
        </span>
      </div>
      <button
        type="button"
        onClick={onActualizar}
        disabled={cargando}
        className="inline-flex items-center gap-1.5 self-start sm:self-auto rounded-lg bg-white border border-primary/20 px-3 py-1.5 text-[13px] font-medium text-primary hover:bg-primary/5 disabled:opacity-50 transition-colors"
      >
        <Icon name="refresh" className={`text-[16px] ${cargando ? 'ae-spin' : ''}`} />
        {cargando ? 'Actualizando…' : 'Actualizar'}
      </button>
    </div>
  );
}
