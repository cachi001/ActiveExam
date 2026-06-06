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
      {/* Ícono en contenedor de tamaño fijo (shrink-0): nunca se comprime ni rompe la fila. */}
      <div className="w-8 h-8 rounded-lg bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name={derecho.icon} className="text-[18px]" />
      </div>
      <div className="min-w-0">
        <p className="text-label-md font-semibold text-on-surface">{derecho.titulo}</p>
        <p className="text-label-sm text-on-surface-variant">{derecho.desc}</p>
      </div>
    </div>
  );
}
