import { Icon } from '../../../ui/components';

interface DsrCardProps {
  derecho: {
    icon: string;
    titulo: string;
    desc: string;
  };
}

export function DsrCard({ derecho }: DsrCardProps) {
  return (
    <div className="flex items-start gap-sm p-base rounded-xl bg-surface-container-low border border-outline-variant/30">
      <Icon name={derecho.icon} className="text-primary text-[20px]" />
      <div>
        <p className="text-label-md font-semibold text-on-surface">{derecho.titulo}</p>
        <p className="text-label-sm text-on-surface-variant">{derecho.desc}</p>
      </div>
    </div>
  );
}
