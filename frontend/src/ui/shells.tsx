import { useState } from 'react';
import type { ReactNode } from 'react';
import { Icon } from './components';
import { Link, useRouter, useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { INSTITUTION } from '../config/institution';
import { GlossaryPanel } from './GlossaryPanel';

const LOGO = (
  <div className="flex items-center gap-sm">
    <div className="w-9 h-9 rounded-lg bg-primary text-on-primary flex items-center justify-center shadow-sm">
      <Icon name="verified_user" className="text-[20px]" fill />
    </div>
    <div className="leading-tight">
      <div className="font-headline text-title-lg text-on-surface">ActiveExam</div>
    </div>
  </div>
);

/** Shell para el flujo del estudiante: barra superior + contenido centrado. */
export function StudentShell({ children, step }: { children: ReactNode; step?: number }) {
  const principal = useApp((s) => s.principal);
  const navigate = useNavigate();
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const pasos = ['Ingreso', 'Requisitos', 'Privacidad', 'Biometría', 'Sala', 'Examen', 'Cierre'];
  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <header className="sticky top-0 z-40 bg-surface-container-lowest/90 backdrop-blur border-b border-outline-variant/50">
        <div className="max-w-container-max mx-auto px-lg h-16 flex items-center justify-between">
          <Link to="/login">{LOGO}</Link>
          <div className="flex items-center gap-md">
            {principal && (
              <div className="text-right hidden sm:block">
                <div className="text-label-md text-on-surface font-semibold">{principal.nombre}</div>
                <div className="text-label-sm text-on-surface-variant">{principal.id_institucional}</div>
              </div>
            )}
            <button onClick={() => navigate('/login')} className="w-10 h-10 rounded-full bg-surface-container hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant" title="Salir">
              <Icon name="logout" className="text-[20px]" />
            </button>
          </div>
        </div>
        {typeof step === 'number' && (
          <div className="max-w-container-max mx-auto px-lg pb-sm overflow-x-auto">
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
      <main className="flex-1 w-full max-w-container-max mx-auto px-lg py-xl">{children}</main>
      <SharedFooter onGlossaryOpen={() => setGlossaryOpen(true)} />
      <GlossaryPanel isOpen={glossaryOpen} onClose={() => setGlossaryOpen(false)} />
    </div>
  );
}

interface NavItem { to: string; icon: string; label: string; }

/** Shell para staff (proctor / revisor / admin): sidebar + contenido. */
export function StaffShell({ children, nav, title }: { children: ReactNode; nav: NavItem[]; title: string }) {
  const { path } = useRouter();
  const principal = useApp((s) => s.principal);
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex bg-surface">
      <aside className="w-sidebar-width shrink-0 bg-surface-container-lowest border-r border-outline-variant/50 flex-col hidden lg:flex sticky top-0 h-screen">
        <div className="px-lg h-16 flex items-center border-b border-outline-variant/40">{LOGO}</div>
        <nav className="flex-1 p-md space-y-base overflow-y-auto">
          {nav.map((item) => {
            const active = path === item.to;
            return (
              <Link key={item.to} to={item.to}
                className={`flex items-center gap-sm px-sm py-sm rounded-xl text-label-md font-semibold transition-colors ${
                  active ? 'bg-primary-fixed text-on-primary-fixed-variant' : 'text-on-surface-variant hover:bg-surface-container'
                }`}>
                <Icon name={item.icon} className="text-[22px]" fill={active} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-md border-t border-outline-variant/40">
          <div className="flex items-center gap-sm px-sm py-sm rounded-xl bg-surface-container">
            {/* Task 9.1: avatar condicional — foto circular si foto_perfil existe, inicial si no */}
            {principal?.foto_perfil ? (
              <img
                src={principal.foto_perfil}
                className="w-9 h-9 rounded-full object-cover"
                alt={`Foto de ${principal?.nombre}`}
              />
            ) : (
              <div className="w-9 h-9 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-semibold">
                {principal?.nombre.charAt(0) ?? '?'}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-label-md text-on-surface font-semibold truncate">{principal?.nombre ?? 'Invitado'}</div>
              <div className="text-label-sm text-on-surface-variant truncate">{principal?.roles.join(', ')}</div>
            </div>
            <button onClick={() => navigate('/login')} title="Salir" className="text-on-surface-variant hover:text-error">
              <Icon name="logout" className="text-[20px]" />
            </button>
          </div>
        </div>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 bg-surface/80 backdrop-blur border-b border-outline-variant/40 px-lg h-16 flex items-center">
          <h1 className="font-headline text-title-lg text-on-surface">{title}</h1>
        </header>
        <main className="flex-1 p-lg">{children}</main>
      </div>
    </div>
  );
}

function SharedFooter({ onGlossaryOpen }: { onGlossaryOpen: () => void }) {
  return (
    <footer className="border-t border-outline-variant/50 bg-surface-container-lowest py-lg">
      <div className="max-w-container-max mx-auto px-lg flex flex-col sm:flex-row items-center justify-between gap-sm text-label-sm text-on-surface-variant">
        <span><span className="font-semibold text-primary">ActiveExam</span> · Transparencia radical en integridad académica.</span>
        <div className="flex gap-md">
          <a className="hover:text-primary" href="#/">Retención (30 días)</a>
          <a className="hover:text-primary" href="#/">{INSTITUTION.soporteLabel}</a>
          <a className="hover:text-primary" href="#/">Ley 25.326</a>
          <button
            type="button"
            onClick={onGlossaryOpen}
            aria-label="Abrir glosario de términos"
            className="hover:text-primary inline-flex items-center gap-[2px] focus:outline-none focus:underline"
          >
            Glosario
          </button>
        </div>
      </div>
    </footer>
  );
}
