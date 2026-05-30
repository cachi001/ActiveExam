import { useState } from 'react';
import { Icon, Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';

export default function Login() {
  const navigate = useNavigate();
  const { setPrincipal, setExamenActivo, resetSesion } = useApp();
  const [cargando, setCargando] = useState(false);

  const ingresar = async () => {
    setCargando(true);
    resetSesion();
    const principal = await api.login('estudiante');
    setPrincipal(principal, 'estudiante');
    const examenes = await api.listExams();
    setExamenActivo(examenes.find((e) => e.estado === 'en_curso') ?? examenes[0]);
    setCargando(false);
    navigate('/requisitos');
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative glass-glow px-lg bg-surface">
      <div className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none opacity-40 blur-[100px] bg-primary-fixed-dim rounded-full translate-x-1/2 -translate-y-1/2" />

      <main className="w-full max-w-md z-10">
        <div className="bg-surface-container-lowest rounded-xl p-xl flex flex-col gap-xl shadow-card-lg border border-outline-variant/50 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <header className="flex flex-col items-center gap-md text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary text-on-primary flex items-center justify-center shadow-sm">
              <Icon name="verified_user" className="text-[28px]" fill />
            </div>
            <div>
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Acceso a tu evaluación</h1>
              <p className="text-body-md text-on-surface-variant mt-xs">Ingresá con tu cuenta institucional federada para continuar.</p>
            </div>
          </header>

          <section className="flex flex-col gap-md">
            <div className="space-y-base">
              <label className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold">Institución</label>
              <div className="flex items-center gap-sm bg-surface-container-low border border-outline-variant rounded-xl px-md py-sm">
                <Icon name="account_balance" className="text-on-surface-variant text-[20px]" />
                <span className="text-body-md font-semibold text-on-surface">Universidad de Buenos Aires — UBA</span>
              </div>
            </div>

            <Button onClick={ingresar} disabled={cargando} icon={cargando ? undefined : 'login'} iconRight={cargando ? undefined : 'arrow_forward'} className="w-full h-14">
              {cargando ? (
                <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Conectando con Keycloak…</span>
              ) : 'Ingresar con UBA ID'}
            </Button>
            <p className="text-label-sm text-on-surface-variant text-center px-md">
              Usás las mismas credenciales del campus (OAuth2 / OIDC con MFA).
            </p>
          </section>

          <nav className="flex justify-center items-center gap-lg border-t border-outline-variant/60 pt-lg">
            <a className="text-label-md text-primary hover:underline" href="#/requisitos">Requisitos técnicos</a>
            <span className="w-1 h-1 bg-outline-variant rounded-full" />
            <a className="text-label-md text-primary hover:underline" href="#/">Necesito ayuda</a>
          </nav>
        </div>

        <footer className="mt-xl flex items-center justify-center gap-xs px-md py-sm bg-surface-container-low rounded-full border border-outline-variant/40">
          <Icon name="lock" className="text-outline text-[18px]" fill />
          <p className="text-label-sm text-on-surface-variant">Tu privacidad está protegida. ActiveExam nunca comparte tus datos. (Ley 25.326)</p>
        </footer>
      </main>
    </div>
  );
}
