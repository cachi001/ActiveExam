/**
 * LtiConfirmar — confirmación de alta pendiente del launch LTI (primer ingreso).
 *
 * Antes, un launch LTI que resultaba en una cuenta NUEVA se auto-provisionaba
 * y logueaba en el mismo request, sin ningún paso intermedio (bug real
 * 2026-08-19: el dueño del proyecto entró con su cuenta ADMIN de Moodle y
 * quedó logueado como alumno sin haber confirmado nada). Ahora el backend
 * redirige acá con un `pendiente_id` de un solo uso (corta vida) en vez de
 * loguear directo — Y la cuenta NO se crea hasta que el usuario define acá
 * mismo su usuario y contraseña (pedido explícito del dueño: "no tiene
 * sentido que el POST se haga si el usuario todavía no definió username ni
 * contraseña" — ambos son obligatorios, no un paso posterior opcional).
 *
 * Flujo de un solo submit:
 *   1. POST /lti/confirmar-provisioning (crea la cuenta con los claims ya
 *      validados, emite sesión).
 *   2. Con esa sesión recién emitida, PUT /auth/change-password fija el
 *      usuario/contraseña elegidos (mismo endpoint que ya usa el primer login
 *      LTI de toda la vida — reusa su validación de formato/colisión).
 *   3. Recién ahí redirige a /alumno. El usuario nunca ve una cuenta "a medias".
 *
 * Un REINGRESO (cuenta ya existente) NUNCA pasa por acá — sigue logueando
 * directo desde `/lti-login`, sin fricción, y solo confirma que esa cuenta es
 * la suya (no vuelve a pedir usuario/contraseña).
 *
 * `nombre`/`email` vienen en el fragment SOLO para mostrarlos — quien decide
 * qué cuenta se crea es el backend, con los claims que ya validó y guardó
 * contra `pendiente_id` (no lo que diga esta URL).
 */
import { useEffect, useState } from 'react';
import { useAuth } from '../lib/authStore';
import { useNavigate } from '../lib/router';
import { Icon } from '../ui/components';
import { API_BASE } from '../lib/apiCore';
import { cuentaApi } from '../lib/apiAdmin/cuenta';
import { validarPasswordFuerte, REQUISITOS_PASSWORD } from '../lib/passwordPolicy';

const LABEL = 'block text-[13px] font-medium text-on-surface mb-1.5';
const USERNAME_RE = /^[a-zA-Z0-9_.-]+$/;

type Estado = 'confirmando' | 'enviando' | 'error';

export default function LtiConfirmar() {
  const loginWithTokens = useAuth((s) => s.loginWithTokens);
  const markPasswordChanged = useAuth((s) => s.markPasswordChanged);
  const navigate = useNavigate();
  const [estado, setEstado] = useState<Estado>('confirmando');
  const [error, setError] = useState<string | null>(null);
  const [pendienteId, setPendienteId] = useState<string | null>(null);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmarPassword, setConfirmarPassword] = useState('');

  useEffect(() => {
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const id = hashParams.get('pendiente_id');
    if (!id) {
      setError('El enlace de confirmación no es válido.');
      setEstado('error');
      return;
    }
    setPendienteId(id);
    setNombre(hashParams.get('nombre') ?? 'tu cuenta');
    setEmail(hashParams.get('email') ?? '');
  }, []);

  async function confirmar() {
    if (!pendienteId) return;
    setError(null);

    const usernameLimpio = username.trim().toLowerCase();
    if (usernameLimpio.length < 3 || usernameLimpio.length > 50) {
      setError('El usuario debe tener entre 3 y 50 caracteres.');
      return;
    }
    if (!USERNAME_RE.test(usernameLimpio)) {
      setError('El usuario solo puede tener letras, números, puntos, guiones y guiones bajos.');
      return;
    }
    const debilidad = validarPasswordFuerte(password);
    if (debilidad) {
      setError(debilidad);
      return;
    }
    if (password !== confirmarPassword) {
      setError('Las contraseñas no coinciden.');
      return;
    }

    setEstado('enviando');
    try {
      // 1) Crea la cuenta recién ahora (con los claims ya validados en /launch).
      const res = await fetch(`${API_BASE}/lti/confirmar-provisioning`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pendiente_id: pendienteId }),
      });
      if (!res.ok) {
        if (res.status === 410) {
          throw new Error('Este enlace de confirmación venció o ya se usó. Volvé a entrar desde Moodle.');
        }
        throw new Error('No pudimos crear tu cuenta. Volvé a entrar desde Moodle.');
      }
      const data = (await res.json()) as { access_token: string; refresh_token: string };
      const ok = loginWithTokens(data.access_token, data.refresh_token);
      if (!ok) throw new Error('No pudimos iniciar tu sesión.');

      // 2) Con la sesión recién emitida, fija usuario+contraseña elegidos —
      // mismo endpoint que ya usa el primer login LTI (valida formato y
      // colisión con otra cuenta).
      await cuentaApi.cambiarContrasena({
        contrasena_nueva: password,
        nuevo_username: usernameLimpio,
      });
      markPasswordChanged();

      window.history.replaceState({}, '', '/alumno');
      navigate('/alumno');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pudimos crear tu cuenta.');
      setEstado('confirmando');
    }
  }

  if (estado === 'error') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface px-lg text-center">
        <div className="w-14 h-14 rounded-2xl bg-error-container text-error flex items-center justify-center">
          <Icon name="link_off" className="text-[28px]" fill />
        </div>
        <div>
          <h1 className="font-headline text-headline-md text-on-surface">No pudimos crear tu cuenta</h1>
          <p className="text-body-md text-on-surface-variant mt-base max-w-sm">{error}</p>
          <button className="mt-lg text-primary underline" onClick={() => navigate('/login')}>
            Ir al inicio de sesión
          </button>
        </div>
      </div>
    );
  }

  const guardando = estado === 'enviando';
  const puedeEnviar =
    username.trim().length >= 3 && password.length > 0 && confirmarPassword.length > 0;

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-lg py-10">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-surface-200 p-8 flex flex-col gap-5">
        <div className="flex flex-col items-center text-center gap-2">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
            <Icon name="person_add" className="text-[28px]" fill />
          </div>
          <h1 className="text-headline-sm font-bold">Confirmá tu cuenta</h1>
          <p className="text-body-md text-on-surface-variant">
            Vas a crear una cuenta nueva en ActiveExam como{' '}
            <strong className="text-on-surface">{nombre}</strong>
            {email && (
              <>
                {' '}
                con el correo <strong className="text-on-surface">{email}</strong>
              </>
            )}
            . Elegí un usuario y una contraseña para entrar directo la próxima vez.
          </p>
        </div>

        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (!guardando) confirmar(); }}
        >
          <div>
            <label className={LABEL} htmlFor="lc-username">Creá tu usuario</label>
            <input
              id="lc-username"
              type="text"
              className="input w-full"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={guardando}
              autoComplete="username"
              placeholder="ej: juan.perez"
              maxLength={50}
              required
              autoFocus
            />
          </div>

          <div>
            <label className={LABEL} htmlFor="lc-password">Contraseña</label>
            <input
              id="lc-password"
              type="password"
              className="input w-full"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={guardando}
              autoComplete="new-password"
              required
            />
            <p className="mt-1.5 text-[12px] text-on-surface-variant/70 leading-relaxed">
              {REQUISITOS_PASSWORD}
            </p>
          </div>

          <div>
            <label className={LABEL} htmlFor="lc-password-confirmar">Repetir contraseña</label>
            <input
              id="lc-password-confirmar"
              type="password"
              className="input w-full"
              value={confirmarPassword}
              onChange={(e) => setConfirmarPassword(e.target.value)}
              disabled={guardando}
              autoComplete="new-password"
              required
            />
          </div>

          {error && (
            <p className="text-[12.5px] text-error flex items-center gap-1.5">
              <Icon name="error" className="text-[15px]" fill />
              {error}
            </p>
          )}

          <div className="flex items-center gap-md">
            <button
              type="button"
              className="text-on-surface-variant underline"
              onClick={() => navigate('/login')}
              disabled={guardando}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={guardando || !puedeEnviar}
              className="flex-1 inline-flex items-center justify-center gap-sm rounded-xl bg-primary text-on-primary px-lg py-sm font-medium disabled:opacity-60"
            >
              {guardando && <Icon name="progress_activity" className="ae-spin text-[18px]" />}
              {guardando ? 'Creando cuenta…' : 'Crear cuenta y continuar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
