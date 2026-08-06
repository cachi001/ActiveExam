/**
 * RequisitoCard — tarjeta genérica de presentación pura para un requisito de enrollment.
 *
 * Encapsula el patrón visual: ícono + título + badge de estado (encabezado) +
 * slot `children` (detalle) + slot `action` (CTA opcional).
 *
 * Spec: profile-requisito-cards (C-42)
 */
import type { ReactNode } from 'react';
import { Card, Badge, Icon } from '../../../ui/components';

type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'error';

interface RequisitoCardProps {
  icon: string;
  /** Título del requisito. Acepta ReactNode para títulos con elementos inline (p.ej. badge "Opcional"). */
  title: ReactNode;
  badge: { tone: BadgeTone; label: string };
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function RequisitoCard({ icon, title, badge, action, children, className = '' }: RequisitoCardProps) {
  return (
    <Card className={className}>
      {/* Encabezado: ícono + título + badge */}
      <div className="flex items-center justify-between gap-3 flex-wrap mb-7">
        <div className="flex items-center gap-3 min-w-0">
          <Icon name={icon} className="text-2xl text-on-surface-variant shrink-0" />
          <h2 className="text-xl font-semibold text-on-surface whitespace-nowrap">{title}</h2>
        </div>
        <Badge tone={badge.tone} dot className="shrink-0">
          {badge.label}
        </Badge>
      </div>

      {/* Cuerpo */}
      <div className="space-y-4">
        {children}
      </div>

      {/* Acción */}
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}
