import { Icon } from '../../../ui/components';

interface QuickAccessCardProps {
  icon: string;
  title: string;
  description: string;
  onClick: () => void;
}

export function QuickAccessCard({ icon, title, description, onClick }: QuickAccessCardProps) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-md p-md bg-surface-container-lowest border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-left"
    >
      <div className="w-11 h-11 rounded-xl bg-secondary-container text-on-secondary flex items-center justify-center shrink-0">
        <Icon name={icon} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-label-md font-semibold text-on-surface">{title}</p>
        <p className="text-label-sm text-on-surface-variant">{description}</p>
      </div>
      <Icon name="arrow_forward" className="text-on-surface-variant ml-auto shrink-0" />
    </button>
  );
}
