/**
 * LtiLanding — aterrizaje del launch LTI (C-75 §7.1).
 *
 * El backend valida el launch LTI (firma del id_token + allowlist), provisiona JIT
 * al alumno si no existe, emite el JWT de sesión propio (mismo emisor que
 * /auth/login) y redirige acá con los tokens en el FRAGMENT (#), no en la query:
 *
 *     /lti-login#access_token=...&refresh_token=...
 *
 * El fragment NO viaja al servidor: no entra a los logs de Nginx/uvicorn ni al
 * header Referer. Por eso leemos de `location.hash`, no de `location.search`.
 *
 * Esta pantalla NO decide identidad: sólo adopta los tokens ya emitidos (con el
 * mismo mecanismo que un login normal) y manda al alumno a su dashboard. Si el
 * primer login trae `debe_cambiar_password=true`, el gate de RequireAuth lo
 * intercepta después (fijá tu contraseña) — no es responsabilidad de acá.
 *
 * Falla cerrado: sin tokens válidos, vuelve a /login con un aviso, nunca a un
 * estado a medias.
 */
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../lib/authStore';
import { useNavigate } from '../lib/router';
import { Icon } from '../ui/components';

export default function LtiLanding() {
  const loginWithTokens = useAuth((s) => s.loginWithTokens);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  // Evita ejecutar la adopción dos veces (StrictMode monta el efecto 2x en dev).
  const yaProceso = useRef(false);

  useEffect(() => {
    if (yaProceso.current) return;
    yaProceso.current = true;

    // Los tokens vienen en el fragment (#a=1&b=2), no en la query string.
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const accessToken = params.get('access_token') ?? '';
    const refreshToken = params.get('refresh_token') ?? undefined;

    if (!accessToken) {
      setError('El enlace de acceso no trae una sesión válida.');
      return;
    }

    const ok = loginWithTokens(accessToken, refreshToken);
    if (!ok) {
      setError('No pudimos iniciar tu sesión desde el campus.');
      return;
    }

    // Limpiamos los tokens de la URL (que no queden en el historial) y vamos al
    // portal del alumno. `replace` para que el botón "atrás" no vuelva acá.
    window.history.replaceState({}, '', '/alumno');
    navigate('/alumno');
  }, [loginWithTokens, navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface px-lg text-center">
        <div className="w-14 h-14 rounded-2xl bg-error-container text-error flex items-center justify-center">
          <Icon name="link_off" className="text-[28px]" fill />
        </div>
        <div>
          <h1 className="font-headline text-headline-md text-on-surface">No pudimos abrir tu sesión</h1>
          <p className="text-body-md text-on-surface-variant mt-base max-w-sm">{error}</p>
          <button
            className="mt-lg text-primary underline"
            onClick={() => navigate('/login')}
          >
            Ir al inicio de sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface text-on-surface-variant">
      <Icon name="progress_activity" className="ae-spin text-[32px] text-primary" />
      <p className="text-label-md">Iniciando tu sesión desde el campus…</p>
    </div>
  );
}
