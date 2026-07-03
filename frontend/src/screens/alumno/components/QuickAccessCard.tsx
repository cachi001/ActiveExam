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
      className="w-full flex items-center gap-4 px-4 py-4 bg-white border border-surface-200 rounded-lg hover:border-primary/40 hover:bg-surface-50 transition-colors text-left"
    >
      <div className="w-8 h-8 rounded-md bg-primary text-on-primary flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[16px]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold text-on-surface leading-tight">{title}</p>
        <p className="text-[12px] text-on-surface-variant leading-tight mt-0.5">{description}</p>
      </div>
      <Icon name="arrow_forward" className="text-on-surface-variant ml-auto shrink-0 text-[16px]" />
    </button>
  );
}
