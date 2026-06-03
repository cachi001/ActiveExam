/**
 * StatCard — Tarjeta compacta de métrica (ícono + número grande + etiqueta).
 *
 * Estilo sobrio Material 3: superficie neutra, acento de color SOLO en el ícono
 * cuando se pide (para resaltar estado, p. ej. score de riesgo). Sin gradientes.
 * Reutilizada en el resumen de la lista y en el header del detalle.
 */
import type { ReactNode } from 'react';
import { Icon } from '../../ui/components';

export type StatTono = 'neutral' | 'success' | 'warning' | 'error' | 'primary';

const TONO_ICONO: Record<StatTono, string> = {
  neutral: 'bg-surface-container-high text-on-surface-variant',
  primary: 'bg-primary-fixed text-primary',
  success: 'bg-success-container text-success',
  warning: 'bg-warning-container text-warning',
  error: 'bg-error-container text-on-error-container',
};

const TONO_VALOR: Record<StatTono, string> = {
  neutral: 'text-on-surface',
  primary: 'text-on-surface',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-error',
};

export function StatCard({
  icon,
  label,
  value,
  sub,
  tono = 'neutral',
}: {
  icon: string;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tono?: StatTono;
}) {
  return (
    <div className="flex items-center gap-md p-md rounded-xl bg-surface-container-lowest
      border border-outline-variant/40 shadow-card">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${TONO_ICONO[tono]}`}>
        <Icon name={icon} className="text-[22px]" fill />
      </div>
      <div className="min-w-0">
        <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">{label}</p>
        <p className={`font-headline text-headline-md leading-tight truncate ${TONO_VALOR[tono]}`}>{value}</p>
        {sub && <p className="text-label-sm text-on-surface-variant mt-px">{sub}</p>}
      </div>
    </div>
  );
}

export default StatCard;
