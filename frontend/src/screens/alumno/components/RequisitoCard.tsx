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
      {/* Encabezado: ícono + título + badge. flex-wrap + min-w-0 para que en
          mobile el badge baje de línea en vez de desbordar a lo ancho. */}
      <div className="flex items-center justify-between gap-sm flex-wrap">
        <div className="flex items-center gap-sm min-w-0">
          <Icon name={icon} className="text-[22px] text-on-surface-variant shrink-0" />
          <h2 className="font-headline text-title-lg text-on-surface">{title}</h2>
        </div>
        <Badge tone={badge.tone} dot className="shrink-0">
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
