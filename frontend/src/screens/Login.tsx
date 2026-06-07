import { useEffect, useState } from 'react';
import { Icon, Button } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useAuth } from '../lib/authStore';
import type { Rol } from '../lib/types';
import { INSTITUTION } from '../config/institution';
import { AUTH_PROVIDER_TYPE } from '../lib/authProvider';

/** Home de cada rol tras el login. admin_sistema centraliza administración + revisión. */
function homePorRol(roles: Rol[]): string {
  if (roles.includes('admin_sistema')) return '/admin';
  if (roles.includes('proctor')) return '/proctor';
  return '/alumno/dashboard';
}

// ---------------------------------------------------------------------------
// Formulario de login JWT (provider propio — C-55)
// ---------------------------------------------------------------------------

function FormularioJwt() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);
  const principal = useAuth((s) => s.principal);
  const login = useAuth((s) => s.login);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect cuando hay sesión.
  useEffect(() => {
    if (status === 'authenticated' && principal) {
      navigate(homePorRol(principal.roles));
    }
  }, [status, principal, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ username, password });
      // La navegación la hace el useEffect de arriba.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Credenciales inválidas.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
      {/* Panel de marca — solo desktop */}
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
            {/* Institución */}
            <div className="flex items-center gap-sm pb-md border-b border-outline-variant/60">
              <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name="account_balance" className="text-[22px]" fill />
              </div>
              <div className="min-w-0">
                <p className="text-label-sm text-on-surface-variant">Tu institución</p>
                <p className="text-body-md font-semibold text-on-surface truncate">{INSTITUTION.nombre}</p>
              </div>
            </div>

            {/* Formulario JWT */}
            <form onSubmit={handleSubmit} className="flex flex-col gap-md">
              <div className="flex flex-col gap-xs">
                <label htmlFor="username" className="text-label-sm text-on-surface-variant">
                  Usuario o email
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={loading}
                  required
                  className="px-md py-sm rounded-lg border border-outline text-body-md bg-surface text-on-surface focus:outline-none focus:border-primary disabled:opacity-50"
                  placeholder="usuario o email institucional"
                />
              </div>

              <div className="flex flex-col gap-xs">
                <label htmlFor="password" className="text-label-sm text-on-surface-variant">
                  Contraseña
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  required
                  className="px-md py-sm rounded-lg border border-outline text-body-md bg-surface text-on-surface focus:outline-none focus:border-primary disabled:opacity-50"
                  placeholder="contraseña"
                />
              </div>

              {error && (
                <div className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
                  <Icon name="error" className="text-[18px] shrink-0" fill />
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading || !username || !password}
                size="lg"
                iconRight={loading ? undefined : 'arrow_forward'}
                className="w-full"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-xs">
                    <Icon name="progress_activity" className="ae-spin text-[20px]" />
                    Verificando…
                  </span>
                ) : 'Ingresar'}
              </Button>
            </form>
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

// ---------------------------------------------------------------------------
// Selector de rol demo (provider demo — comportamiento existente)
// ---------------------------------------------------------------------------

function SelectorRolDemo() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);
  const principal = useAuth((s) => s.principal);
  const loginDemo = useAuth((s) => s.loginDemo);

  useEffect(() => {
    if (status === 'authenticated' && principal) {
      navigate(homePorRol(principal.roles));
    }
  }, [status, principal, navigate]);

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
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

      <main className="flex flex-col items-center justify-center px-lg py-xl">
        <div className="w-full max-w-sm flex flex-col gap-xxl animate-in fade-in slide-in-from-bottom-4 duration-700">
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
            <div className="flex items-center gap-sm pb-md border-b border-outline-variant/60">
              <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name="account_balance" className="text-[22px]" fill />
              </div>
              <div className="min-w-0">
                <p className="text-label-sm text-on-surface-variant">Tu institución</p>
                <p className="text-body-md font-semibold text-on-surface truncate">{INSTITUTION.nombre}</p>
              </div>
            </div>

            <div className="flex flex-col gap-sm">
              <p className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold text-center">Entrar como</p>
              <Button variant="primary" onClick={() => loginDemo('estudiante')} icon="school" size="lg" className="w-full">Estudiante</Button>
              <Button variant="outline" onClick={() => loginDemo('proctor')} icon="visibility" size="lg" className="w-full">Proctor</Button>
              <Button variant="outline" onClick={() => loginDemo('admin_sistema')} icon="admin_panel_settings" size="lg" className="w-full">Administrador</Button>
              <p className="text-label-sm text-on-surface-variant text-center mt-xs">Modo demostración · sin autenticación real</p>
            </div>
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

// ---------------------------------------------------------------------------
// Login con Keycloak (comportamiento existente C-06)
// ---------------------------------------------------------------------------

function LoginKeycloak() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);
  const principal = useAuth((s) => s.principal);
  const login = useAuth((s) => s.login);

  useEffect(() => {
    if (status === 'authenticated' && principal) {
      navigate(homePorRol(principal.roles));
    }
  }, [status, principal, navigate]);

  const cargando = status === 'loading';

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface">
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

      <main className="flex flex-col items-center justify-center px-lg py-xl">
        <div className="w-full max-w-sm flex flex-col gap-xxl animate-in fade-in slide-in-from-bottom-4 duration-700">
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
            <div className="flex items-center gap-sm pb-md border-b border-outline-variant/60">
              <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name="account_balance" className="text-[22px]" fill />
              </div>
              <div className="min-w-0">
                <p className="text-label-sm text-on-surface-variant">Tu institución</p>
                <p className="text-body-md font-semibold text-on-surface truncate">{INSTITUTION.nombre}</p>
              </div>
            </div>

            <Button onClick={() => void login()} disabled={cargando} size="lg" iconRight={cargando ? undefined : 'arrow_forward'} className="w-full">
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

// ---------------------------------------------------------------------------
// Componente principal: elige la variante según el provider activo
// ---------------------------------------------------------------------------

export default function Login() {
  if (AUTH_PROVIDER_TYPE === 'demo') return <SelectorRolDemo />;
  if (AUTH_PROVIDER_TYPE === 'keycloak') return <LoginKeycloak />;
  // Default: jwt — formulario de login propio (C-55)
  return <FormularioJwt />;
}
