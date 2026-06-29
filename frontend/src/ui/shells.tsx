import { useState, useEffect, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';
import { Icon, BackButton } from './components';
import { Link, useRouter, useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { nombreCompleto } from '../lib/types';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';
import { WizardStepper, type WizardPaso } from '../screens/enrollment/EnrollmentStepLayout';
import type { StaffNavItem } from './nav';

// ---------------------------------------------------------------------------
// Constantes de layout (compartidas entre Header / Sidebar / Main)
// ---------------------------------------------------------------------------

const TOPBAR_H = 56;            // Altura del topbar (h-14)
const SIDEBAR_EXPANDED = 240;   // Sidebar expandida en desktop
const SIDEBAR_COLLAPSED = 60;   // Sidebar colapsada (solo iconos)
const SIDEBAR_DRAWER_W = 280;   // Sidebar en mobile (drawer)
const LS_SIDEBAR_COLLAPSED = 'ae_sidebar_collapsed';

/** Hook simple para saber si estamos en desktop (>= lg / 1024px). */
function useIsDesktop() {
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

/** Hook para persistir el estado colapsado/expandido de la sidebar. */
function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(LS_SIDEBAR_COLLAPSED) === '1'; } catch { return false; }
  });
  const toggle = () => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem(LS_SIDEBAR_COLLAPSED, next ? '1' : '0'); } catch { /* noop */ }
      return next;
    });
  };
  return [collapsed, toggle];
}

// ---------------------------------------------------------------------------
// Logo (compartido)
// ---------------------------------------------------------------------------

function LogoMark() {
  return (
    <div className="w-8 h-8 rounded-lg bg-primary-fixed text-primary flex items-center justify-center shadow-sm shrink-0">
      <Icon name="verified_user" className="text-[18px]" fill />
    </div>
  );
}

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

// ---------------------------------------------------------------------------
// User menu (staff)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Sidebar item + section (staff)
// ---------------------------------------------------------------------------

function SidebarItem({
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

function SidebarSection({
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

// ---------------------------------------------------------------------------
// StaffShell
// ---------------------------------------------------------------------------

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

  // Cierra el drawer mobile al navegar.
  useEffect(() => { if (!isDesktop) setMobileOpen(false); }, [path, isDesktop]);

  // Bloquea scroll del body cuando el drawer mobile está abierto.
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

  // Filtramos el nav por los roles del usuario logueado ANTES de partirlo en
  // grupos: el proctor solo ve los items de SUPERVISION (vivo / cola / grabadas);
  // el admin ve todo. Coherente con los guards de ruta de App.tsx — un item cuya
  // ruta el rol no puede abrir no se muestra (si no, clickea y ve "Sin permisos").
  const roles = useAuth((s) => s.principal?.roles);
  const visibleNav = useMemo(
    () => nav.filter((i) => i.roles.some((r) => roles?.includes(r))),
    [nav, roles],
  );
  const mainItems = useMemo(() => visibleNav.filter((i) => i.group === 'main'), [visibleNav]);
  const configItems = useMemo(() => visibleNav.filter((i) => i.group === 'config'), [visibleNav]);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* ── Topbar full-width ────────────────────────────────────────────── */}
      <header
        className="fixed top-0 left-0 right-0 z-50 border-b border-surface-200/80 bg-white/95 backdrop-blur-sm"
        style={{ height: TOPBAR_H }}
      >
        <div className="h-full px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile: hamburger */}
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="lg:hidden inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-50 hover:text-on-surface transition-colors"
              aria-label="Abrir menú"
            >
              <Icon name="menu" className="text-[20px]" />
            </button>

            {/* Desktop: collapse toggle */}
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

      {/* ── Overlay mobile ────────────────────────────────────────────────── */}
      {mobileOpen && !isDesktop && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden transition-opacity duration-300"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Sidebar fija (debajo del topbar) ─────────────────────────────── */}
      <aside
        className={`fixed left-0 bottom-0 z-40 flex flex-col bg-white border-r border-surface-200 ${
          isDesktop ? 'transition-[width] duration-300 ease-in-out' : 'transition-transform duration-300 ease-in-out lg:translate-x-0'
        } ${!isDesktop && !mobileOpen ? '-translate-x-full' : 'translate-x-0'}`}
        style={{ top: TOPBAR_H, width: sidebarWidth }}
      >
        {/* Mobile header del drawer */}
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

      {/* ── Main content ─────────────────────────────────────────────────── */}
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

// ---------------------------------------------------------------------------
// StudentShell — sidebar persistente desktop + bottom-nav mobile
// ---------------------------------------------------------------------------

interface StudentNavItem { to: string; icon: string; label: string; short?: string; }

const STUDENT_NAV: StudentNavItem[] = [
  { to: '/alumno',              icon: 'home',            label: 'Inicio',       short: 'Inicio' },
  { to: '/alumno/materias',     icon: 'menu_book',       label: 'Mis materias', short: 'Materias' },
  { to: '/alumno/mis-examenes', icon: 'assignment',      label: 'Mis exámenes', short: 'Exámenes' },
  { to: '/alumno/perfil',       icon: 'manage_accounts', label: 'Mi perfil',    short: 'Perfil' },
];

function StudentUserMenu({ onLogoutClick }: { onLogoutClick: () => void }) {
  const principal = useApp((s) => s.principal);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  // Ver nota en UserMenu: el overlay fixed no sirve por el backdrop-blur del topbar.
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

  if (!principal) return null;

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
        {principal.foto_perfil ? (
          <img src={principal.foto_perfil} alt={principal.nombre} className="w-8 h-8 rounded-full object-cover shrink-0" />
        ) : (
          <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px] shrink-0">
            {principal.nombre.charAt(0)}
          </div>
        )}
        <div className="hidden lg:block text-left max-w-[180px] leading-tight">
          <div className="text-[12px] font-medium text-on-surface truncate">{nombreCompleto(principal)}</div>
          <div className="text-[11px] text-on-surface-variant truncate">{principal.id_institucional}</div>
        </div>
        <Icon name="expand_more" className={`text-[16px] text-on-surface-variant transition-transform hidden lg:block ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-2 z-50 w-56 rounded-lg border border-surface-200 bg-white shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
          <div className="px-4 py-3 border-b border-surface-200 lg:hidden">
            <div className="text-sm font-medium text-on-surface truncate">{nombreCompleto(principal)}</div>
            <div className="text-xs text-on-surface-variant truncate">{principal.id_institucional}</div>
          </div>
          <button
            onClick={() => { setOpen(false); navigate('/alumno/perfil'); }}
            role="menuitem"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-on-surface hover:bg-surface-50 transition-colors"
          >
            <Icon name="manage_accounts" className="text-[18px] text-on-surface-variant" />
            Mi perfil
          </button>
          <button
            onClick={() => { setOpen(false); onLogoutClick(); }}
            role="menuitem"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-error hover:bg-error-container/40 transition-colors"
          >
            <Icon name="logout" className="text-[18px]" />
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}

export function StudentShell({ children, step, backTo = '/alumno' }: { children: ReactNode; step?: number; backTo?: string }) {
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const { path } = useRouter();
  const principal = useApp((s) => s.principal);
  const setFotoPerfil = useApp((s) => s.setFotoPerfil);
  const isDesktop = useIsDesktop();
  const [collapsed, toggleCollapsed] = useSidebarCollapsed();
  const [confirmandoLogout, setConfirmandoLogout] = useState(false);

  const PASOS_EXAMEN = ['Requisitos', 'Consentimiento', 'Verificación', 'Sala'];
  const pasosWizard: WizardPaso[] = PASOS_EXAMEN.map((label, i) => ({
    label,
    estado:
      step === undefined
        ? 'pendiente'
        : i + 1 < step
          ? 'completado'
          : i + 1 === step
            ? 'actual'
            : 'pendiente',
  }));

  useEffect(() => {
    if (principal && !principal.foto_perfil) {
      api.obtenerFotoPerfil().then((foto) => { if (foto) setFotoPerfil(foto); }).catch(() => {});
    }
  }, [principal, setFotoPerfil]);

  const showAsCollapsed = isDesktop && collapsed;

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Topbar — en mobile NO hay hamburger ni drawer: la navegación va por el
          bottom-nav, que ya cubre las 4 secciones del alumno. */}
      <header
        className="fixed top-0 left-0 right-0 z-50 border-b border-surface-200/80 bg-white/95 backdrop-blur-sm"
        style={{ height: TOPBAR_H }}
      >
        <div className="h-full px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {isDesktop && (
              <>
                <button
                  onClick={toggleCollapsed}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-on-surface-variant hover:bg-surface-50 hover:text-on-surface transition-colors"
                  aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
                >
                  <Icon name={collapsed ? 'chevron_right' : 'chevron_left'} className="text-[20px]" />
                </button>
                <div className="hidden sm:block w-px h-6 bg-surface-200" />
              </>
            )}
            <Link to="/alumno" className="flex items-center gap-2.5 min-w-0">
              <LogoMark />
              <span className="text-sm font-semibold text-on-surface leading-tight">Active Exam</span>
            </Link>
          </div>
          <StudentUserMenu onLogoutClick={() => setConfirmandoLogout(true)} />
        </div>
      </header>

      {/* Sidebar persistente — sólo desktop. En mobile no se monta. */}
      {isDesktop && (
        <aside
          className="fixed left-0 bottom-0 z-40 flex flex-col bg-white border-r border-surface-200 transition-[width] duration-300 ease-in-out"
          style={{ top: TOPBAR_H, width: showAsCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED }}
        >
          <div className="flex-1 py-3 overflow-y-auto overflow-x-hidden">
            <SidebarSection
              items={STUDENT_NAV}
              collapsed={showAsCollapsed}
              currentPath={path}
            />
          </div>
        </aside>
      )}

      {/* Main */}
      <div
        className="min-h-screen transition-[margin] duration-300 ease-in-out"
        style={{
          paddingTop: TOPBAR_H,
          marginLeft: isDesktop ? (showAsCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED) : 0,
        }}
      >
        <main className="p-4 sm:p-6 pb-24 md:pb-6">
          {typeof step === 'number' && (
            <div className="mb-6 space-y-4">
              <BackButton onClick={() => navigate(backTo)} />
              <WizardStepper pasos={pasosWizard} />
            </div>
          )}
          {children}
        </main>
      </div>

      {/* Bottom-nav (mobile only) — atajo rápido cuando el drawer está cerrado */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-white/95 backdrop-blur-sm border-t border-surface-200 flex items-stretch justify-around pb-[env(safe-area-inset-bottom)]">
        {STUDENT_NAV.map((item) => {
          const active = path === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex-1 min-w-[4.5rem] flex flex-col items-center justify-center gap-0.5 py-2 transition-colors ${
                active ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <Icon name={item.icon} className="text-[22px]" fill={active} />
              <span className="text-[11px] font-medium whitespace-nowrap">{item.short ?? item.label}</span>
            </Link>
          );
        })}
      </nav>

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
