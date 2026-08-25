/**
 * CambioClaveObligatorio — pantalla bloqueante de primer login (clave temporal).
 *
 * Se muestra cuando el principal tiene `debe_cambiar_password = true`: la cuenta
 * fue creada por un admin con una contraseña temporal y el usuario todavía no
 * definió la suya. Hasta que la cambie, no puede acceder a ninguna otra sección
 * (el gate vive en RequireAuth).
 *
 * Dos variantes según el origen de la cuenta:
 * - Clave temporal (admin): pide la temporal (actual) + la nueva + confirmación.
 * - LTI (C-75): el alumno entró desde el campus y NUNCA recibió una temporal;
 *   se le pide sólo la nueva + confirmación. Definirla le permite entrar después
 *   directo con usuario+contraseña (además del campus).
 * Al cambiarla con éxito, limpia el gate y deja pasar.
 */
import { useState } from 'react';
import { Button, Icon } from '../ui/components';
import { useAuth } from '../lib/authStore';
import { cuentaApi } from '../lib/apiAdmin/cuenta';
import { validarPasswordFuerte, REQUISITOS_PASSWORD } from '../lib/passwordPolicy';

const LABEL = 'block text-[13px] font-medium text-on-surface mb-1.5';

export default function CambioClaveObligatorio() {
  const markPasswordChanged = useAuth((s) => s.markPasswordChanged);
  const refrescarAccessToken = useAuth((s) => s.refrescarAccessToken);
  const logout = useAuth((s) => s.logout);
  // Usuario LTI en su primer ingreso: no tiene contraseña temporal que pedirle.
  const esLti = useAuth((s) => s.principal?.auth_provider) === 'lti';

  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [username, setUsername] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const USERNAME_RE = /^[a-zA-Z0-9_.-]+$/;

  async function guardar() {
    setError(null);
    const debilidad = validarPasswordFuerte(nueva);
    if (debilidad) { setError(debilidad); return; }
    if (nueva !== confirmar) { setError('Las contraseñas no coinciden.'); return; }
    if (!esLti && nueva === actual) { setError('La nueva contraseña debe ser distinta de la temporal.'); return; }
    const usernameLimpio = username.trim();
    // LTI: el username actual es la clave sintética del campus (lti:...), no
    // sirve para loguearse directo — elegir uno propio es obligatorio acá, es
    // la ÚNICA oportunidad antes de que el alumno empiece a usar la cuenta.
    if (esLti && !usernameLimpio) {
      setError('Elegí un nombre de usuario para poder ingresar directo la próxima vez.');
      return;
    }
    if (usernameLimpio) {
      if (usernameLimpio.length < 3 || usernameLimpio.length > 50) {
        setError('El usuario debe tener entre 3 y 50 caracteres.');
        return;
      }
      if (!USERNAME_RE.test(usernameLimpio)) {
        setError('El usuario solo puede tener letras, números, puntos, guiones y guiones bajos.');
        return;
      }
    }

    setGuardando(true);
    try {
      const resp = await cuentaApi.cambiarContrasena({
        // LTI: sin contraseña actual (nunca la tuvo).
        ...(esLti ? {} : { contrasena_actual: actual }),
        contrasena_nueva: nueva,
        ...(usernameLimpio ? { nuevo_username: usernameLimpio } : {}),
      });
      // c-78 E-13: si eligió username, el backend re-emite el token con el
      // nombre nuevo. Sin adoptarlo acá, la app seguía mostrando `lti:1:7`.
      if (resp.access_token) refrescarAccessToken(resp.access_token);
      // Éxito: el gate deja de aplicar y el usuario pasa a su pantalla normal.
      markPasswordChanged();
    } catch (err) {
      const e = err as { message?: string };
      setError(e.message || 'No se pudo cambiar la contraseña.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-lg py-10">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-surface-200 p-8 flex flex-col gap-5">
        <div className="flex flex-col items-center text-center gap-2">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
            <Icon name="lock_reset" className="text-[28px]" />
          </div>
          <h1 className="text-headline-sm font-bold">
            {esLti ? 'Creá tu usuario y contraseña' : 'Definí tu contraseña'}
          </h1>
          <p className="text-body-md text-on-surface-variant">
            {esLti
              ? 'Entraste desde el campus. Elegí un usuario y una contraseña para poder ingresar también de forma directa la próxima vez.'
              : 'Ingresaste con una contraseña temporal. Por seguridad, creá tu propia contraseña para continuar.'}
          </p>
        </div>

        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (!guardando) guardar(); }}
        >
          {/* Username PRIMERO: en LTI es obligatorio (la cuenta arranca con la
              clave sintética del campus, no sirve para loguearse directo) y
              elegirlo es lo primero que hay que decidir, antes de la contraseña. */}
          <div>
            <label className={LABEL} htmlFor="cco-username">
              Creá tu usuario{!esLti && ' (opcional)'}
            </label>
            <input
              id="cco-username"
              type="text"
              className="input w-full"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={guardando}
              autoComplete="username"
              placeholder="ej: juan.perez"
              maxLength={50}
              required={esLti}
              autoFocus
            />
            <p className="mt-1.5 text-[12px] text-on-surface-variant/70 leading-relaxed">
              {esLti
                ? 'Para entrar directo la próxima vez, sin pasar por el campus.'
                : 'Dejalo vacío para mantener el usuario actual.'}
            </p>
          </div>

          {!esLti && (
            <div>
              <label className={LABEL} htmlFor="cco-actual">Contraseña temporal</label>
              <input
                id="cco-actual"
                type="password"
                className="input w-full"
                value={actual}
                onChange={(e) => setActual(e.target.value)}
                disabled={guardando}
                autoComplete="current-password"
              />
            </div>
          )}

          <div>
            <label className={LABEL} htmlFor="cco-nueva">Nueva contraseña</label>
            <input
              id="cco-nueva"
              type="password"
              className="input w-full"
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              disabled={guardando}
              autoComplete="new-password"
            />
            <p className="mt-1.5 text-[12px] text-on-surface-variant/70 leading-relaxed">
              {REQUISITOS_PASSWORD}
            </p>
          </div>

          <div>
            <label className={LABEL} htmlFor="cco-confirmar">Repetir nueva contraseña</label>
            <input
              id="cco-confirmar"
              type="password"
              className="input w-full"
              value={confirmar}
              onChange={(e) => setConfirmar(e.target.value)}
              disabled={guardando}
              autoComplete="new-password"
            />
          </div>

          {error && (
            <p className="text-[12.5px] text-error flex items-center gap-1.5">
              <Icon name="error" className="text-[15px]" fill />
              {error}
            </p>
          )}

          <Button
            type="submit"
            variant="primary"
            icon={guardando ? undefined : 'check'}
            disabled={guardando || (!esLti && !actual) || (esLti && !username.trim()) || !nueva || !confirmar}
            className="w-full justify-center"
          >
            {guardando ? 'Guardando…' : 'Guardar y continuar'}
          </Button>
        </form>

        <div className="flex justify-center">
          <Button variant="ghost" size="sm" icon="logout" onClick={() => logout()} disabled={guardando}>
            Cerrar sesión
          </Button>
        </div>
      </div>
    </div>
  );
}
