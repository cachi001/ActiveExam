import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { Icon } from './components';
import { Link, useRouter, useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { nombreCompleto } from '../lib/types';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';

const LOGO = (
  <div className="flex items-center gap-sm">
    <div className="w-9 h-9 rounded-lg bg-primary text-on-primary flex items-center justify-center shadow-sm">
      <Icon name="verified_user" className="text-[20px]" fill />
    </div>
    <div className="leading-tight">
      <div className="font-headline text-title-lg text-on-surface">Active Exam</div>
    </div>
  </div>
);

/** Menú de usuario del header (staff): nombre + correo + popup con cerrar sesión. */
function UserMenu() {
  const principal = useApp((s) => s.principal);
  const logout = useAuth((s) => s.logout);
  const [open, setOpen] = useState(false);
  const [confirmandoLogout, setConfirmandoLogout] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const inicial = principal?.nombre?.charAt(0) ?? '?';
  const secundario = principal?.email ?? principal?.id_institucional ?? '';

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2.5 rounded-full py-1 pl-3 pr-1.5 hover:bg-surface-container transition-colors"
      >
        <div className="text-right leading-tight hidden sm:block">
          <div className="text-[13px] font-semibold text-on-surface truncate max-w-[180px]">{principal?.nombre ?? 'Invitado'}</div>
          <div className="text-[11px] text-on-surface-variant truncate max-w-[180px]">{secundario}</div>
        </div>
        {principal?.foto_perfil ? (
          <img src={principal.foto_perfil} alt={principal.nombre} className="w-9 h-9 rounded-full object-cover" />
        ) : (
          <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[14px]">{inicial}</div>
        )}
        <Icon name="expand_more" className={`text-[18px] text-on-surface-variant transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div role="menu" className="absolute right-0 top-full mt-2 z-50 w-64 rounded-2xl border border-outline-variant/60 bg-white shadow-card-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
            <div className="px-4 py-3 border-b border-outline-variant/40">
              <div className="text-[13px] font-semibold text-on-surface truncate">{principal?.nombre ?? 'Invitado'}</div>
              <div className="text-[12px] text-on-surface-variant truncate">{secundario}</div>
              {principal?.roles && principal.roles.length > 0 && (
                <div className="text-[11px] text-on-surface-variant truncate mt-0.5">{principal.roles.join(', ')}</div>
              )}
            </div>
            <button
              onClick={() => { setOpen(false); setConfirmandoLogout(true); }}
              role="menuitem"
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-error hover:bg-error-container/40 transition-colors"
            >
              <Icon name="logout" className="text-[18px]" /> Cerrar sesión
            </button>
          </div>
        </>
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

const STUDENT_NAV: NavItem[] = [
  { to: '/alumno', icon: 'home', label: 'Inicio', short: 'Inicio' },
  { to: '/alumno/materias', icon: 'menu_book', label: 'Mis materias', short: 'Materias' },
  { to: '/alumno/mis-examenes', icon: 'assignment', label: 'Mis exámenes', short: 'Exámenes' },
  { to: '/alumno/perfil', icon: 'manage_accounts', label: 'Mi perfil', short: 'Perfil' },
];

/** Dropdown del header: nombre + ID clickeables que abren menú con "Mi perfil" + "Cerrar sesión". */
function StudentUserMenu({ onLogoutClick }: { onLogoutClick: () => void }) {
  const principal = useApp((s) => s.principal);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (!principal) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-sm rounded-full pl-md pr-base py-base hover:bg-surface-container transition-colors"
      >
        <div className="text-right leading-tight hidden sm:block">
          <div className="text-label-md text-on-surface font-semibold truncate max-w-[200px]">{nombreCompleto(principal)}</div>
          <div className="text-label-sm text-on-surface-variant truncate max-w-[200px]">{principal.id_institucional}</div>
        </div>
        {principal.foto_perfil ? (
          <img src={principal.foto_perfil} alt={principal.nombre} className="w-9 h-9 rounded-full object-cover shrink-0" />
        ) : (
          <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[14px] shrink-0">
            {principal.nombre.charAt(0)}
          </div>
        )}
        <Icon name="expand_more" className={`text-[18px] text-on-surface-variant transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div role="menu" className="absolute right-0 top-full mt-base z-50 w-64 rounded-2xl border border-outline-variant/60 bg-white shadow-card-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
            <div className="px-md py-sm border-b border-outline-variant/40 sm:hidden">
              <div className="text-label-md font-semibold text-on-surface truncate">{nombreCompleto(principal)}</div>
              <div className="text-label-sm text-on-surface-variant truncate">{principal.id_institucional}</div>
            </div>
            <button
              onClick={() => { setOpen(false); navigate('/alumno/perfil'); }}
              role="menuitem"
              className="w-full flex items-center gap-sm px-md py-sm text-label-md text-on-surface hover:bg-surface-container transition-colors"
            >
              <Icon name="manage_accounts" className="text-[20px] text-on-surface-variant" />
              Mi perfil
            </button>
            <button
              onClick={() => { setOpen(false); onLogoutClick(); }}
              role="menuitem"
              className="w-full flex items-center gap-sm px-md py-sm text-label-md text-error hover:bg-error-container/40 transition-colors"
            >
              <Icon name="logout" className="text-[20px]" />
              Cerrar sesión
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/** Shell para el flujo del estudiante: header + drawer lateral (flecha pegada al borde). */
export function StudentShell({ children, step }: { children: ReactNode; step?: number }) {
  const logout = useAuth((s) => s.logout);
  const { path } = useRouter();
  const principal = useApp((s) => s.principal);
  const setFotoPerfil = useApp((s) => s.setFotoPerfil);
  const [confirmandoLogout, setConfirmandoLogout] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const pasos = ['Ingreso', 'Requisitos', 'Privacidad', 'Biometría', 'Sala', 'Examen', 'Cierre'];

  // Cargar la foto de perfil persistida (demo o backend) para mostrarla en el header
  // en cualquier página, no solo en el perfil.
  useEffect(() => {
    if (principal && !principal.foto_perfil) {
      api.obtenerFotoPerfil().then((foto) => { if (foto) setFotoPerfil(foto); }).catch(() => {});
    }
  }, [principal, setFotoPerfil]);

  return (
    <div className="h-[100dvh] flex flex-col bg-surface overflow-hidden">
      <header className="shrink-0 z-40 bg-surface-container-lowest/95 backdrop-blur border-b border-outline-variant/50">
        <div className="max-w-container-max mx-auto px-lg h-16 flex items-center justify-between gap-md">
          <div className="flex items-center gap-sm min-w-0">
            <Link to="/alumno" className="flex items-center gap-sm shrink-0">
              <div className="w-9 h-9 rounded-lg bg-primary text-on-primary flex items-center justify-center shadow-sm">
                <Icon name="verified_user" className="text-[20px]" fill />
              </div>
              <span className="font-headline text-title-lg text-on-surface">Active Exam</span>
            </Link>
          </div>
          <StudentUserMenu onLogoutClick={() => setConfirmandoLogout(true)} />
        </div>
        {typeof step === 'number' && (
          <div className="max-w-container-max mx-auto px-lg pb-sm overflow-x-auto no-scrollbar border-t border-outline-variant/40">
            <div className="flex items-center gap-base min-w-max py-base">
              {pasos.map((p, i) => (
                <div key={p} className="flex items-center gap-base">
                  <div className={`flex items-center gap-base px-sm py-base rounded-full text-label-sm font-semibold ${
                    i === step ? 'bg-primary text-on-primary' : i < step ? 'bg-primary-fixed text-on-primary-fixed-variant' : 'bg-surface-container text-on-surface-variant'
                  }`}>
                    <span className="w-5 h-5 rounded-full bg-current/20 flex items-center justify-center text-[11px]">
                      {i < step ? '✓' : i + 1}
                    </span>
                    <span className="hidden md:inline">{p}</span>
                  </div>
                  {i < pasos.length - 1 && <span className="w-4 h-px bg-outline-variant" />}
                </div>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Handle flotante (SOLO desktop): botón que despliega el menú lateral.
          En mobile el menú vive en la barra inferior. */}
      {!drawerOpen && (
        <button
          onClick={() => setDrawerOpen(true)}
          aria-label="Abrir menú de navegación"
          className="hidden md:flex fixed left-0 top-1/2 -translate-y-1/2 z-40 w-7 h-12 bg-primary/90 text-on-primary rounded-r-lg shadow-card items-center justify-center hover:w-9 transition-all"
        >
          <Icon name="chevron_right" className="text-[20px]" />
        </button>
      )}

      {/* Drawer lateral desplegado por el handle (desktop) */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40 animate-in fade-in duration-150" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-80 max-w-[85vw] bg-surface-container-lowest border-r border-outline-variant/50 flex flex-col shadow-card-lg animate-in fade-in duration-200">
            <div className="px-lg h-16 flex items-center justify-between border-b border-outline-variant/40">
              <span className="font-headline text-title-lg text-on-surface">Menú</span>
              <button
                onClick={() => setDrawerOpen(false)}
                aria-label="Cerrar menú"
                className="w-11 h-11 rounded-full hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
              >
                <Icon name="close" className="text-[26px]" />
              </button>
            </div>
            <nav className="flex-1 px-md py-md space-y-xs overflow-y-auto">
              {STUDENT_NAV.map((item) => {
                const active = path === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setDrawerOpen(false)}
                    className={`flex items-center gap-md px-md py-3.5 rounded-xl text-[16px] font-semibold transition-colors ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface hover:bg-surface-container'
                    }`}
                  >
                    <Icon name={item.icon} className="text-[26px] shrink-0" fill={active} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* Contenido scrolleable: el scroll vive acá adentro, no en el documento.
          Así la barra inferior es un hijo flex fijo abajo, siempre visible. */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-styled">
        <div className="w-full max-w-container-max mx-auto px-lg pt-xl pb-xl">{children}</div>
        {/* Footer solo en desktop; en mobile su lugar lo ocupa la barra inferior */}
        <div className="hidden md:block">
          <SharedFooter />
        </div>
      </main>

      {/* Barra de navegación inferior — hijo flex fijo abajo (NO position:fixed).
          Siempre visible en mobile, en toda página, sin depender de la barra de URL
          del navegador. En desktop la nav va desplegada en el header. */}
      <nav className="md:hidden shrink-0 z-40 bg-surface-container-lowest border-t border-outline-variant/50 flex items-stretch justify-around overflow-x-auto no-scrollbar pb-[env(safe-area-inset-bottom)]">
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
              <Icon name={item.icon} className="text-[24px]" fill={active} />
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

interface NavItem { to: string; icon: string; label: string; short?: string; }

/** Shell para staff (proctor / revisor / admin): sidebar (desktop) + drawer (mobile) + contenido. */
export function StaffShell({ children, nav, title, subtitle, help, actions }: { children: ReactNode; nav: NavItem[]; title: string; subtitle?: ReactNode; help?: ReactNode; actions?: ReactNode }) {
  const { path } = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const navList = (onItemClick?: () => void) => (
    <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
      {nav.map((item) => {
        const active = path === item.to;
        return (
          <Link key={item.to} to={item.to} onClick={onItemClick}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors ${
              active ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}>
            <Icon name={item.icon} className="text-[18px] shrink-0" fill={active} />
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen flex bg-surface">
      {/* Sidebar fija (desktop ≥ lg) */}
      <aside className="w-sidebar-width shrink-0 bg-surface-container-lowest border-r border-outline-variant/50 flex-col hidden lg:flex sticky top-0 h-screen">
        <div className="px-lg h-16 flex items-center border-b border-outline-variant/40">{LOGO}</div>
        {navList()}
      </aside>

      {/* Drawer (mobile < lg) */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40 animate-in fade-in duration-150" onClick={() => setMobileNavOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-[80vw] max-w-xs bg-surface-container-lowest border-r border-outline-variant/50 flex flex-col shadow-card-lg animate-in fade-in duration-200">
            <div className="px-lg h-16 flex items-center justify-between border-b border-outline-variant/40">
              {LOGO}
              <button onClick={() => setMobileNavOpen(false)} aria-label="Cerrar menú" className="w-9 h-9 rounded-full hover:bg-surface-container flex items-center justify-center text-on-surface-variant">
                <Icon name="close" className="text-[22px]" />
              </button>
            </div>
            {navList(() => setMobileNavOpen(false))}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Header bar: marco superior. NO muestra el título (ese vive en el
            contenido). En mobile aloja el botón de menú; en desktop es una franja
            limpia sticky. */}
        <header className="sticky top-0 z-30 bg-surface/80 backdrop-blur border-b border-outline-variant/40 px-lg h-16 flex items-center gap-sm">
          <button onClick={() => setMobileNavOpen(true)} aria-label="Abrir menú" className="lg:hidden -ml-1 w-10 h-10 rounded-full hover:bg-surface-container flex items-center justify-center text-on-surface-variant shrink-0">
            <Icon name="menu" className="text-[24px]" />
          </button>
          <div className="ml-auto">
            <UserMenu />
          </div>
        </header>
        <main className="flex-1 p-lg">
          {/* Encabezado de página en el contenido: título + ayuda (al lado, centrada)
              + subtítulo + acciones. Fuente única del título (prop `title`). */}
          <div className="mb-lg flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="font-headline text-headline-sm text-on-surface truncate">{title}</h1>
                {help}
              </div>
              {subtitle && <p className="text-[13px] text-on-surface-variant mt-1">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

function SharedFooter() {
  return (
    <footer className="border-t border-outline-variant/50 bg-surface-container-lowest py-lg">
      <div className="max-w-container-max mx-auto px-lg text-center text-label-sm text-on-surface-variant">
        <span><span className="font-semibold text-primary">Active Exam</span> · Transparencia radical en integridad académica.</span>
      </div>
    </footer>
  );
}
