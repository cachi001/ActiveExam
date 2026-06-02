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
    <Card className={`space-y-md ${className}`}>
      {/* Encabezado: ícono + título + badge */}
      <div className="flex items-center justify-between gap-md">
        <div className="flex items-center gap-sm">
          <Icon name={icon} className="text-[22px] text-on-surface-variant" />
          <h2 className="font-headline text-title-md text-on-surface">{title}</h2>
        </div>
        <Badge tone={badge.tone} dot>
          {badge.label}
        </Badge>
      </div>

      {/* Cuerpo: children (detalle del requisito) */}
      {children}

      {/* Acción: CTA opcional debajo del cuerpo */}
      {action}
    </Card>
  );
}
