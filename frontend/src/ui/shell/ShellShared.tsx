import { useState, useEffect } from 'react';
import { Icon } from '../components';
import { Link } from '../../lib/router';
import { useUiPrefs } from '../../lib/useUiPrefs';
import type { StaffNavItem } from '../nav';

export const TOPBAR_H = 56;
export const SIDEBAR_EXPANDED = 240;
export const SIDEBAR_COLLAPSED = 60;
export const SIDEBAR_DRAWER_W = 280;
export const LS_SIDEBAR_COLLAPSED = 'ae_sidebar_collapsed';

export interface StudentNavItem { to: string; icon: string; label: string; short?: string; }

export function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window === 'undefined' ? true : window.innerWidth >= 1024,
  );
  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return isDesktop;
}

// Delegado al store persistido `useUiPrefs` (C-73): la preferencia sobrevive la
// recarga vía `persist` (allowlist), en vez del localStorage crudo de antes.
export function useSidebarCollapsed(): [boolean, () => void] {
  const collapsed = useUiPrefs((s) => s.sidebarColapsado);
  const toggle = useUiPrefs((s) => s.toggleSidebar);
  return [collapsed, toggle];
}

export function LogoMark() {
  return (
    <div className="w-8 h-8 rounded-lg bg-primary-fixed text-primary flex items-center justify-center shadow-sm shrink-0">
      <Icon name="verified_user" className="text-[18px]" fill />
    </div>
  );
}

export function SidebarItem({
  item,
  collapsed,
  active,
  onClick,
}: {
  item: StaffNavItem | StudentNavItem;
  collapsed: boolean;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      to={item.to}
      onClick={onClick}
      className={`relative group flex items-center py-2 text-[13px] font-medium rounded-md mx-2 transition-[color,background-color,padding-left] duration-300 ease-in-out ${
        collapsed ? 'pl-[13px] pr-2' : 'px-3'
      } ${
        active
          ? 'bg-primary text-on-primary shadow-sm'
          : 'text-on-surface-variant hover:bg-surface-50 hover:text-on-surface'
      }`}
    >
      <Icon name={item.icon} className="text-[18px] shrink-0" fill={active} />
      {collapsed && (
        <span className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 rounded-md text-[12px] font-medium bg-surface-900 text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50 shadow-md">
          {item.label}
        </span>
      )}
      <span
        className={`whitespace-nowrap overflow-hidden leading-none select-none py-1 transition-[max-width,opacity,margin-left] ease-in-out ${
          collapsed
            ? 'max-w-0 opacity-0 ml-0 duration-150'
            : 'max-w-[180px] opacity-100 ml-2.5 duration-200 delay-[80ms]'
        }`}
      >
        {item.label}
      </span>
    </Link>
  );
}

export function SidebarSection({
  items,
  collapsed,
  currentPath,
  onItemClick,
  showDivider = false,
}: {
  items: StaffNavItem[] | StudentNavItem[];
  collapsed: boolean;
  currentPath: string;
  onItemClick?: () => void;
  showDivider?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      {showDivider && (
        <div className={`mb-2 ${collapsed ? 'mx-auto w-8 h-px bg-surface-300' : 'mx-4 h-px bg-surface-200'}`} />
      )}
      <nav className="space-y-0.5">
        {items.map((it) => (
          <SidebarItem
            key={it.to}
            item={it}
            collapsed={collapsed}
            active={currentPath === it.to}
            onClick={onItemClick}
          />
        ))}
      </nav>
    </div>
  );
}
