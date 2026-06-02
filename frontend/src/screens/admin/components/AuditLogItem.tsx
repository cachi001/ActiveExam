import { Icon, Badge } from '../../../ui/components';

interface AuditLogItemProps {
  entrada: {
    ts: string;
    actor: string;
    accion: string;
    detalle: string;
    tono: 'error' | 'neutral' | 'warning' | 'success' | 'primary';
  };
}

export function AuditLogItem({ entrada }: AuditLogItemProps) {
  return (
    <div className="flex items-start gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/30">
      <div className="w-9 h-9 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant shrink-0">
        <Icon name="history" className="text-[18px]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-base">
          <span className="text-label-md font-semibold text-on-surface">{entrada.accion}</span>
          <Badge tone={entrada.tono}>{entrada.actor}</Badge>
        </div>
        <p className="text-label-sm text-on-surface-variant mt-base">{entrada.detalle}</p>
        <p className="text-label-sm text-on-surface-variant font-mono mt-base">{entrada.ts}</p>
      </div>
    </div>
  );
}
