import { useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Icon, BackButton } from './components';
import { Link, useRouter, useNavigate } from '../lib/router';
import { nombreCompleto } from '../lib/types';
import { useAuth } from '../lib/authStore';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';
import { WizardStepper, type WizardPaso } from '../screens/enrollment/EnrollmentStepLayout';
import {
  TOPBAR_H, SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED,
  useIsDesktop, useSidebarCollapsed, LogoMark, SidebarSection,
  type StudentNavItem,
} from './shell/ShellShared';

const STUDENT_NAV: StudentNavItem[] = [
  { to: '/alumno',              icon: 'home',            label: 'Inicio',       short: 'Inicio' },
  { to: '/alumno/materias',     icon: 'menu_book',       label: 'Mis materias', short: 'Materias' },
  { to: '/alumno/mis-examenes', icon: 'assignment',      label: 'Mis exámenes', short: 'Exámenes' },
  { to: '/alumno/perfil',       icon: 'manage_accounts', label: 'Mi perfil',    short: 'Perfil' },
];

/**
 * Menú de usuario en el header (desktop): avatar + nombre + dropdown con
 * "Mi perfil" y "Cerrar sesión". Reemplaza al pie de la sidebar — la identidad
 * y el logout viven arriba a la derecha, como en el StaffShell.
 */
function StudentUserMenu({ onLogoutClick }: { onLogoutClick: () => void }) {
  const principal = useAuth((s) => s.principal);
  const [open, setOpen] = useState(false);
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
  const inicial = principal.nombre.charAt(0).toUpperCase();
  const secundario = principal.email ?? principal.id_institucional ?? 'Estudiante';

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex items-center gap-2 px-2 py-1.5 rounded-md transition-colors hover:bg-surface-50 ${open ? 'bg-surface-50' : ''}`}
      >
        {principal.foto_perfil ? (
          <img src={principal.foto_perfil} alt={principal.nombre} className="w-8 h-8 rounded-full object-cover" />
        ) : (
          <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px]">
            {inicial}
          </div>
        )}
        <div className="hidden lg:block text-left max-w-[180px] leading-tight">
          <div className="text-[12px] font-medium text-on-surface truncate">{nombreCompleto(principal)}</div>
          <div className="text-[11px] text-on-surface-variant truncate">{secundario}</div>
        </div>
        <Icon name="expand_more" className={`text-[16px] text-on-surface-variant transition-transform hidden lg:block ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-2 z-50 w-56 rounded-lg border border-surface-200 bg-white shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
          <div className="px-4 py-3 border-b border-surface-200">
            <div className="text-sm font-medium text-on-surface truncate">{nombreCompleto(principal)}</div>
            <div className="text-xs text-on-surface-variant truncate">{secundario}</div>
          </div>
          <Link
            to="/alumno/perfil"
            onClick={() => setOpen(false)}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-on-surface hover:bg-surface-50 transition-colors"
          >
            <Icon name="manage_accounts" className="text-[18px] text-on-surface-variant" /> Mi perfil
          </Link>
          <button
            onClick={() => { setOpen(false); onLogoutClick(); }}
            role="menuitem"
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-error hover:bg-error-container/40 transition-colors"
          >
            <Icon name="logout" className="text-[18px]" /> Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}

function HeaderAvatar() {
  const principal = useAuth((s) => s.principal);
  if (!principal) return null;

  const inicial = principal.nombre.charAt(0).toUpperCase();

  return (
    <Link
      to="/alumno/perfil"
      className="flex items-center justify-center w-8 h-8 rounded-full hover:opacity-80 transition-opacity"
      aria-label="Mi perfil"
    >
      {principal.foto_perfil ? (
        <img src={principal.foto_perfil} alt={principal.nombre} className="w-8 h-8 rounded-full object-cover" />
      ) : (
        <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px]">
          {inicial}
        </div>
      )}
    </Link>
  );
}

export function StudentShell({
  children,
  step,
  backTo = '/alumno',
  locked = false,
}: {
  children: ReactNode;
  step?: number;
  backTo?: string;
  /** Lockdown del examen en curso (C-69 sección 5): oculta sidebar, bottom-nav y
   *  cualquier link de navegación (logo, menú de usuario). El alumno no debe
   *  poder salir de la pantalla del examen por otra vía que no sea entregarlo. */
  locked?: boolean;
}) {
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const { path } = useRouter();
  const principal = useAuth((s) => s.principal);
  const setFotoPerfil = useAuth((s) => s.setFotoPerfil);
  const isDesktop = useIsDesktop();
  const [collapsed, toggleCollapsed] = useSidebarCollapsed();
  const [confirmandoLogout, setConfirmandoLogout] = useState(false);

  // Gating de perfil: hasta que el alumno complete el enrollment (consentimiento
  // + biometría) NO puede navegar por la sidebar/bottom-nav. Se lo funnelea a
  // completar el perfil desde el dashboard (CTA) o el menú de usuario del header.
  const enrollmentStatus = useApp((s) => s.enrollmentStatus);
  const isProfileComplete = useApp((s) => s.isProfileComplete);
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);

  // Cargamos el enrollment al montar si el store aún no lo tiene, para que el
  // lock sea correcto en cualquier pantalla (incluida una recarga o entrada
  // directa por URL). Otras pantallas también lo setean; es idempotente.
  useEffect(() => {
    if (enrollmentStatus === null) {
      api.getEnrollment().then(setEnrollmentStatus).catch(() => {});
    }
  }, [enrollmentStatus, setEnrollmentStatus]);

  // Solo bloqueamos cuando YA sabemos que el perfil está incompleto (evita
  // parpadear la ausencia de sidebar a un alumno con perfil completo mientras
  // carga). Durante el lockdown del examen (`locked`) la sidebar ya está oculta.
  // Mientras el perfil no esté completo NO se muestra la sidebar ni el bottom-nav:
  // el alumno se funnelea a completarlo (CTA del dashboard / menú de usuario).
  const perfilBloqueado = !locked && enrollmentStatus !== null && !isProfileComplete;

  // La sidebar/nav se muestran solo si no hay lockdown y el perfil está completo.
  const mostrarSidebarDesktop = isDesktop && !locked && !perfilBloqueado;
  const mostrarBottomNav = !locked && !perfilBloqueado;

  const PASOS_EXAMEN = ['Requisitos', 'Verificación', 'Sala'];
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
      {!locked && (
        <header
          className="fixed top-0 left-0 right-0 z-50 border-b border-surface-200/80 bg-white/95 backdrop-blur-sm"
          style={{ height: TOPBAR_H }}
        >
          <div className="h-full px-4 sm:px-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              {mostrarSidebarDesktop && (
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
            {/* Desktop: menú de usuario (nombre + logout) en el header.
                Mobile: avatar como link directo al perfil. */}
            {isDesktop
              ? <StudentUserMenu onLogoutClick={() => setConfirmandoLogout(true)} />
              : <HeaderAvatar />}
          </div>
        </header>
      )}

      {mostrarSidebarDesktop && (
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

      <div
        className="min-h-screen transition-[margin] duration-300 ease-in-out bg-surface"
        style={{
          paddingTop: locked ? 0 : TOPBAR_H,
          marginLeft: mostrarSidebarDesktop ? (showAsCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED) : 0,
        }}
      >
        <main className={`p-4 sm:p-6 ${locked ? '' : 'pb-24 md:pb-6'}`}>
          {typeof step === 'number' && (
            <div className="mb-6 space-y-4">
              <BackButton onClick={() => navigate(backTo)} />
              <WizardStepper pasos={pasosWizard} />
            </div>
          )}
          {children}
        </main>
      </div>

      {mostrarBottomNav && (
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
