import { useEffect } from 'react';
import { Icon, Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useAuth } from '../lib/authStore';
import type { Rol } from '../lib/types';
import { INSTITUTION } from '../config/institution';

/** Home de cada rol tras el login. admin_sistema centraliza administración + revisión. */
function homePorRol(roles: Rol[]): string {
  if (roles.includes('admin_sistema')) return '/admin';
  if (roles.includes('proctor')) return '/proctor';
  return '/alumno/dashboard';
}

export default function Login() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);
  const principal = useAuth((s) => s.principal);
  const login = useAuth((s) => s.login);

  // Si ya hay sesión iniciada (volvimos del redirect de Keycloak), entrar al home del rol.
  useEffect(() => {
    if (status === 'authenticated' && principal) {
      navigate(homePorRol(principal.roles));
    }
  }, [status, principal, navigate]);

  const cargando = status === 'loading';

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
      {/* Panel de marca (color con presencia) — solo desktop */}
      <aside className="hidden lg:flex flex-col justify-between p-xxl bg-gradient-to-br from-primary to-primary-700 text-on-primary relative overflow-hidden">
        <span className="pointer-events-none absolute -top-16 -right-16 w-72 h-72 rounded-full bg-white/10" aria-hidden />
        <span className="pointer-events-none absolute bottom-10 -left-20 w-80 h-80 rounded-full bg-white/5" aria-hidden />

        <div className="flex items-center gap-sm relative">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Icon name="verified_user" className="text-[24px]" fill />
          </div>
          <span className="font-headline text-title-lg">Active Exam</span>
        </div>

        <div className="relative max-w-md">
          <h2 className="font-headline text-display-lg leading-tight">Integridad académica, con soberanía de datos.</h2>
          <p className="text-body-lg text-white/80 mt-md">
            Supervisión de exámenes remotos con evidencia de cadena de custodia y decisión disciplinaria siempre humana.
          </p>
        </div>

        <div className="relative flex items-center gap-xs text-label-sm text-white/70">
          <Icon name="lock" className="text-[18px]" fill />
          Self-hosted · Ley 25.326 · DPIA aprobado
        </div>
      </aside>

      {/* Panel de acceso */}
      <main className="flex flex-col items-center justify-center px-lg py-xl">
        <div className="w-full max-w-sm flex flex-col gap-xxl animate-in fade-in slide-in-from-bottom-4 duration-700">
          {/* Marca compacta (visible también en mobile) */}
          <header className="flex flex-col items-center gap-md text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary text-on-primary flex items-center justify-center shadow-sm lg:hidden">
              <Icon name="verified_user" className="text-[28px]" fill />
            </div>
            <div>
              <h1 className="font-headline text-headline-lg text-on-surface tracking-tight">Iniciar sesión</h1>
              <p className="text-body-md text-on-surface-variant mt-xs">
                Accedé a la plataforma de exámenes supervisados.
              </p>
            </div>
          </header>

          <section className="flex flex-col gap-lg">
            {/* Institución: fila limpia con acento de color, sin caja gris */}
            <div className="flex items-center gap-sm pb-md border-b border-outline-variant/60">
              <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name="account_balance" className="text-[22px]" fill />
              </div>
              <div className="min-w-0">
                <p className="text-label-sm text-on-surface-variant">Tu institución</p>
                <p className="text-body-md font-semibold text-on-surface truncate">{INSTITUTION.nombre}</p>
              </div>
            </div>

            <Button onClick={login} disabled={cargando} size="lg" iconRight={cargando ? undefined : 'arrow_forward'} className="w-full">
              {cargando ? (
                <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Conectando…</span>
              ) : 'Ingresar con mi cuenta institucional'}
            </Button>
            <p className="text-label-sm text-on-surface-variant text-center">
              Mismas credenciales del campus · OIDC con MFA
            </p>
          </section>

          <p className="flex items-center justify-center gap-xs text-label-sm text-on-surface-variant">
            <Icon name="lock" className="text-outline text-[16px]" fill />
            Tu privacidad está protegida — Ley 25.326
          </p>
        </div>
      </main>
    </div>
  );
}
