/**
 * MiCuentaCampus — la conexión personal del docente con el campus (C-73 §10.7).
 *
 * Por qué existe: la nota SIEMPRE se devuelve a Moodle con la cuenta del docente a
 * cargo de la comisión, para que en la libreta figure quién la puso. Sin esta
 * conexión, las notas de sus comisiones quedan retenidas — no se mandan con una
 * cuenta institucional, porque eso las dejaría sin responsable.
 *
 * La contraseña NO se guarda: se canjea una vez por un token del campus y se
 * descarta. Por eso el campo se vacía apenas se guarda.
 */
import { useCallback, useEffect, useState } from 'react';
import { adminApi, type MiCuentaCampus as Estado } from '../../lib/apiAdmin';
import { Button, Icon } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';

type Modo = 'password' | 'token';

const AYUDA = (
  <HelpButton title="Conectar tu cuenta del campus">
    <p>
      Cuando un alumno tuyo termina un examen, la nota se manda al campus <strong>con tu
      cuenta</strong>. Así, en la libreta figura que la nota la pusiste vos y no un sistema
      anónimo.
    </p>
    <p>
      Por eso necesitás conectarte una vez. Mientras no lo hagas, las notas de tus
      comisiones se calculan y se guardan, pero <strong>no viajan al campus</strong>.
    </p>
    <p>
      <strong>Tu contraseña no se guarda.</strong> Se usa una sola vez para pedirle al campus
      una llave de acceso, y esa llave es lo único que queda guardado (cifrado). Si cambiás
      la contraseña del campus, esto sigue funcionando.
    </p>
  </HelpButton>
);

export default function MiCuentaCampus({
  mostrarCampus = true,
}: {
  /** El admin ve la dirección del campus en la sección institucional; repetirla
   *  acá daba dos campos iguales en la misma pantalla. */
  mostrarCampus?: boolean;
}) {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [cargando, setCargando] = useState(true);
  const [modo, setModo] = useState<Modo>('password');
  const [usuario, setUsuario] = useState('');
  const [secreto, setSecreto] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const aplicar = useCallback((e: Estado) => {
    setEstado(e);
    setUsuario(e.moodle_username ?? '');
    setSecreto('');
  }, []);

  useEffect(() => {
    let vivo = true;
    adminApi
      .obtenerMiCuentaCampus()
      .then((e) => vivo && aplicar(e))
      .catch(() => vivo && setError('No se pudo leer el estado de tu conexión.'))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, [aplicar]);

  async function guardar() {
    setError(null);
    setOk(null);
    if (!usuario.trim() || !secreto.trim()) {
      setError('Completá tu usuario del campus y la contraseña.');
      return;
    }
    setGuardando(true);
    try {
      const e = await adminApi.guardarMiCuentaCampus({
        moodle_username: usuario.trim(),
        ...(modo === 'password' ? { password: secreto } : { token: secreto }),
      });
      aplicar(e);
      setOk('Tu cuenta quedó conectada.');
    } catch (err) {
      // `realFetch` adjunta `mensaje` del {detail:{error,mensaje}} del backend. Se
      // muestra TAL CUAL porque está redactado para el docente y distingue casos con
      // arreglos distintos: "usuario o contraseña incorrectos" lo resuelve él, y
      // "el campus no habilita este servicio" lo resuelve el admin del campus.
      // Nunca incluye la contraseña (garantizado por test en token_exchange).
      const e = err as { mensaje?: string; status?: number };
      setError(
        e.mensaje ??
          (e.status === 403
            ? 'No tenés permiso para conectar una cuenta del campus.'
            : 'No se pudo conectar con el campus. Revisá los datos.'),
      );
    } finally {
      setGuardando(false);
    }
  }

  async function desconectar() {
    setError(null);
    setOk(null);
    setGuardando(true);
    try {
      aplicar(await adminApi.desconectarMiCuentaCampus());
      setOk('Tu cuenta quedó desconectada.');
    } catch {
      setError('No se pudo desconectar.');
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return <div className="h-[180px] bg-surface-container-low rounded-md animate-pulse" />;
  }

  const conectada = estado?.configurada && estado.estado === 'activa';
  const caida = estado?.configurada && estado.estado === 'caida';

  return (
    <div>
      <div className="mb-md">
        <h3 className="text-title-md font-semibold text-on-surface flex items-center gap-1.5">
          Tu cuenta del campus
          {AYUDA}
        </h3>
        <p className="text-label-sm text-on-surface-variant mt-0.5">
          En la libreta figura que la nota la pusiste vos.
        </p>
      </div>

      {/* Estado actual — lo primero que se lee */}
      <div
        className={`flex items-center gap-sm rounded-md border px-md py-sm mb-md ${
          conectada
            ? 'border-success/40 bg-success-container/30'
            : caida
              ? 'border-error/40 bg-error-container/30'
              : 'border-outline-variant bg-surface-container-low'
        }`}
      >
        <Icon
          name={conectada ? 'link' : caida ? 'link_off' : 'info'}
          className={
            conectada ? 'text-success' : caida ? 'text-error' : 'text-on-surface-variant'
          }
        />
        <div className="min-w-0">
          {conectada && (
            <p className="text-label-md text-on-surface">
              Conectado como <strong>{estado?.moodle_username}</strong>
              {estado?.token_pista && (
                <span className="text-on-surface-variant"> · ****{estado.token_pista}</span>
              )}
            </p>
          )}
          {caida && (
            <p className="text-label-md text-on-surface">
              El campus dejó de aceptar tu llave. Volvé a conectarte para que tus notas
              puedan viajar.
            </p>
          )}
          {!estado?.configurada && (
            <p className="text-label-md text-on-surface">
              Todavía no conectaste tu cuenta. Tus notas se guardan, pero no llegan al
              campus.
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-md">
        {mostrarCampus && (
          <div>
            <label className="text-label-sm text-on-surface-variant" htmlFor="campus-url">
              Campus
            </label>
            <input
              id="campus-url"
              className="input w-full mt-1 bg-surface-container-low text-on-surface-variant"
              value={estado?.base_url || ''}
              readOnly
            />
          </div>
        )}

        <div>
          <label className="text-label-sm text-on-surface-variant" htmlFor="campus-user">
            Tu usuario del campus
          </label>
          <input
            id="campus-user"
            className="input w-full mt-1"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="off"
          />
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label className="text-label-sm text-on-surface-variant" htmlFor="campus-secret">
              {modo === 'password' ? 'Tu contraseña del campus' : 'Llave que te dieron'}
            </label>
            <button
              type="button"
              className="text-label-sm text-primary hover:underline"
              onClick={() => {
                setModo(modo === 'password' ? 'token' : 'password');
                setSecreto('');
              }}
            >
              {modo === 'password' ? 'Tengo una llave' : 'Usar mi contraseña'}
            </button>
          </div>
          <input
            id="campus-secret"
            type="password"
            className="input w-full mt-1"
            value={secreto}
            onChange={(e) => setSecreto(e.target.value)}
            autoComplete="new-password"
            placeholder={modo === 'password' ? '••••••••' : 'Pegá la llave acá'}
          />
        </div>

        {error && (
          <p className="text-label-sm text-error flex items-center gap-1.5">
            <Icon name="error" className="text-[16px]" />
            {error}
          </p>
        )}
        {ok && (
          <p className="text-label-sm text-success flex items-center gap-1.5">
            <Icon name="check_circle" className="text-[16px]" />
            {ok}
          </p>
        )}

        <div className="flex items-center gap-sm">
          <Button
            variant="primary"
            icon={guardando ? undefined : 'link'}
            onClick={guardar}
            disabled={guardando}
          >
            {guardando
              ? 'Conectando…'
              : estado?.configurada
                ? 'Volver a conectar'
                : 'Conectar'}
          </Button>
          {estado?.configurada && (
            <Button variant="ghost" size="sm" onClick={desconectar} disabled={guardando}>
              Desconectar
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
