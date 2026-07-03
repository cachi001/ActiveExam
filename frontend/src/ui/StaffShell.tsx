import { useState, useEffect, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';
import { Icon } from './components';
import { Link, useRouter } from '../lib/router';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { ConfirmModal } from './ConfirmModal';
import type { StaffNavItem } from './nav';
import {
  TOPBAR_H, SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED, SIDEBAR_DRAWER_W,
  useIsDesktop, useSidebarCollapsed, LogoMark, SidebarSection,
} from './shell/ShellShared';

function LogoFull({ showText = true }: { showText?: boolean }) {
  return (
    <Link to="/admin" className="flex items-center gap-2.5 min-w-0">
      <LogoMark />
      {showText && (
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-on-surface">Active Exam</span>
          <span className="hidden sm:block text-[10px] text-on-surface-variant">Plataforma de proctoring</span>
        </div>
      )}
    </Link>
  );
}

function UserMenu() {
  const principal = useApp((s) => s.principal);
  const logout = useAuth((s) => s.logout);
  const [open, setOpen] = useState(false);
  const [confirmandoLogout, setConfirmandoLogout] = useState(false);
  // El click-outside no se puede resolver con un overlay <div className="fixed
  // inset-0"> porque el topbar usa backdrop-blur y eso crea un stacking context
  // que confina al "fixed" al header en vez de cubrir la pantalla. Mousedown
  // global + ref del wrapper es robusto a cualquier contenedor padre.
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDown = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  const inicial = principal?.nombre?.charAt(0) ?? '?';
  const secundario = principal?.email ?? principal?.id_institucional ?? '';

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex items-center gap-2 px-2 py-1.5 rounded-md transition-colors hover:bg-surface-50 ${
          open ? 'bg-surface-50' : ''
        }`}
      >
        {principal?.foto_perfil ? (
          <img src={principal.foto_perfil} alt={principal.nombre} className="w-8 h-8 rounded-full object-cover" />
        ) : (
          <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px]">
            {inicial}
          </div>
        )}
        <div className="hidden lg:block text-left max-w-[180px] leading-tight">
          <div className="text-[12px] font-medium text-on-surface truncate">{principal?.nombre ?? 'Invitado'}</div>
          <div className="text-[11px] text-on-surface-variant truncate">{secundario}</div>
        </div>
        <Icon name="expand_more" className={`text-[16px] text-on-surface-variant transition-transform hidden lg:block ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-2 z-50 w-56 rounded-lg border border-surface-200 bg-white shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
          <div className="px-4 py-3 border-b border-surface-200">
            <div className="text-sm font-medium text-on-surface truncate">{principal?.nombre ?? 'Invitado'}</div>
            <div className="text-xs text-on-surface-variant truncate">{secundario}</div>
          </div>
          <button
            onClick={() => { setOpen(false); setConfirmandoLogout(true); }}
            role="menuitem"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-error hover:bg-error-container/40 transition-colors"
          >
            <Icon name="logout" className="text-[18px]" /> Cerrar sesión
          </button>
        </div>
      )}
      <ConfirmModal
        abierto={confirmandoLogout}
        titulo="Cerrar sesión"
        mensaje="¿Querés cerrar tu sesión? Vas a tener que volver a iniciar sesión para continuar."
        textoConfirmar="Cerrar sesión"
        textoCancelar="Cancelar"
        variante="logout"
        onConfirmar={() => { setConfirmandoLogout(false); logout(); }}
        onCancelar={() => setConfirmandoLogout(false)}
      />
    </div>
  );
}

export function StaffShell({
  children,
  nav,
  title,
  subtitle,
  help,
  actions,
}: {
  children: ReactNode;
  nav: StaffNavItem[];
  title: string;
  subtitle?: ReactNode;
  help?: ReactNode;
  actions?: ReactNode;
}) {
  const { path } = useRouter();
  const isDesktop = useIsDesktop();
  const [collapsed, toggleCollapsed] = useSidebarCollapsed();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => { if (!isDesktop) setMobileOpen(false); }, [path, isDesktop]);

  useEffect(() => {
    if (isDesktop || !mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isDesktop, mobileOpen]);

  const showAsCollapsed = isDesktop && collapsed;
  const sidebarWidth = isDesktop
    ? (showAsCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED)
    : SIDEBAR_DRAWER_W;

  const roles = useAuth((s) => s.principal?.roles);
  const visibleNav = useMemo(
    () => nav.filter((i) => i.roles.some((r) => roles?.includes(r))),
    [nav, roles],
  );
  const mainItems = useMemo(() => visibleNav.filter((i) => i.group === 'main'), [visibleNav]);
  const configItems = useMemo(() => visibleNav.filter((i) => i.group === 'config'), [visibleNav]);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <header
        className="fixed top-0 left-0 right-0 z-50 border-b border-surface-200/80 bg-white/95 backdrop-blur-sm"
        style={{ height: TOPBAR_H }}
      >
        <div className="h-full px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="lg:hidden inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-50 hover:text-on-surface transition-colors"
              aria-label="Abrir menú"
            >
              <Icon name="menu" className="text-[20px]" />
            </button>
            <button
              onClick={toggleCollapsed}
              className="hidden lg:inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-50 hover:text-on-surface transition-colors"
              aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
            >
              <Icon name={collapsed ? 'chevron_right' : 'chevron_left'} className="text-[20px]" />
            </button>
            <div className="hidden sm:block w-px h-6 bg-surface-200" />
            <LogoFull />
          </div>
          <div className="flex items-center gap-2">
            <UserMenu />
          </div>
        </div>
      </header>

      {mobileOpen && !isDesktop && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden transition-opacity duration-300"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed left-0 bottom-0 z-40 flex flex-col bg-white border-r border-surface-200 ${
          isDesktop ? 'transition-[width] duration-300 ease-in-out' : 'transition-transform duration-300 ease-in-out lg:translate-x-0'
        } ${!isDesktop && !mobileOpen ? '-translate-x-full' : 'translate-x-0'}`}
        style={{ top: TOPBAR_H, width: sidebarWidth }}
      >
        {!isDesktop && (
          <div className="px-4 py-3 border-b border-surface-200 flex items-center justify-between">
            <span className="text-sm font-semibold text-on-surface">Menú</span>
            <button
              onClick={() => setMobileOpen(false)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-50 hover:text-on-surface"
              aria-label="Cerrar menú"
            >
              <Icon name="close" className="text-[20px]" />
            </button>
          </div>
        )}
        <div className="flex-1 py-3 space-y-4 overflow-y-auto overflow-x-hidden">
          <SidebarSection
            items={mainItems}
            collapsed={showAsCollapsed}
            currentPath={path}
            onItemClick={() => { if (!isDesktop) setMobileOpen(false); }}
          />
          <SidebarSection
            items={configItems}
            collapsed={showAsCollapsed}
            currentPath={path}
            onItemClick={() => { if (!isDesktop) setMobileOpen(false); }}
            showDivider
          />
        </div>
      </aside>

      <div
        className="min-h-screen transition-[margin] duration-300 ease-in-out"
        style={{
          paddingTop: TOPBAR_H,
          marginLeft: isDesktop ? (showAsCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED) : 0,
        }}
      >
        <main className="p-4 sm:p-6">
          <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-on-surface truncate">{title}</h1>
                {help}
              </div>
              {subtitle && <p className="text-base text-on-surface-variant mt-1">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
