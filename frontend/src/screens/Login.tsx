import { useEffect, useState } from 'react';
import { Icon, Button, TextField } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useAuth } from '../lib/authStore';
import { homePorRol } from '../lib/auth/homePorRol';


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
    <div className="lg:h-screen lg:overflow-hidden min-h-screen grid lg:grid-cols-2 bg-white">
      {/* Panel de marca — solo desktop. Altura fija a viewport para que cuando el
          form sea más largo, el branding del lado izquierdo no se estire. */}
      <aside className="hidden lg:flex flex-col justify-between p-xxl bg-gradient-to-br from-primary to-primary-700 text-on-primary relative overflow-hidden lg:h-screen lg:sticky lg:top-0">
        <span className="pointer-events-none absolute -top-16 -right-16 w-72 h-72 rounded-full bg-white/10" aria-hidden />
        <span className="pointer-events-none absolute bottom-10 -left-20 w-80 h-80 rounded-full bg-white/10" aria-hidden />
        <div className="flex items-center gap-sm relative">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Icon name="verified_user" className="text-[24px]" fill />
          </div>
          <span className="font-headline text-title-lg">Active Exam</span>
        </div>
        <div className="relative max-w-md">
          <h2 className="font-headline text-display-lg leading-tight">Integridad académica.</h2>
          <p className="text-body-lg text-white/80 mt-md">
            Supervisión de exámenes remotos con evidencia de cadena de custodia y decisión disciplinaria siempre humana.
          </p>
        </div>
        <div className="relative flex items-center gap-xs text-label-sm text-white/70">
          <Icon name="lock" className="text-[18px]" fill />
          Tu privacidad está protegida
        </div>
      </aside>

      {/* Panel de acceso */}
      <main className="flex flex-col items-center px-lg py-xl lg:overflow-y-auto lg:h-screen">
        <div className="w-full max-w-sm flex flex-col gap-lg animate-in fade-in slide-in-from-bottom-4 duration-700 my-auto">
          <header className="flex flex-col items-center gap-md text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary text-on-primary flex items-center justify-center shadow-sm lg:hidden">
              <Icon name="verified_user" className="text-[28px]" fill />
            </div>
            <div>
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Iniciar sesión</h1>
              <p className="text-label-md text-on-surface/60 mt-xs">
                Accedé a la plataforma de exámenes supervisados.
              </p>
            </div>
          </header>

          <section className="flex flex-col gap-lg">
            {/* Formulario JWT */}
            <form onSubmit={handleSubmit} className="flex flex-col gap-md">
              <TextField
                label="Usuario o correo"
                name="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
                required
                icon="person"
                placeholder="Ingresá tu usuario o correo"
              />

              <TextField
                label="Contraseña"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
                icon="lock"
                placeholder="Contraseña"
              />

              {error && (
                <div className="flex items-center gap-xs text-error-700 text-label-sm p-sm rounded-lg bg-error-50 border border-error-100">
                  <Icon name="error" className="text-[16px] shrink-0" fill />
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="w-full"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-xs">
                    <Icon name="progress_activity" className="ae-spin text-[18px]" />
                    Verificando…
                  </span>
                ) : 'Iniciar sesión'}
              </Button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente principal — único provider soportado: JWT propio (C-55)
// ---------------------------------------------------------------------------

export default function Login() {
  return <FormularioJwt />;
}
