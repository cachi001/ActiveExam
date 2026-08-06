/**
 * MiCuentaCampus — la conexión personal del tutor con el campus.
 *
 * Por qué existe: la nota SIEMPRE se devuelve a Moodle con la cuenta del tutor
 * a cargo de la comisión, para que en la libreta figure quién la puso. Sin esta
 * conexión, las notas de sus comisiones quedan retenidas.
 *
 * La contraseña NO se guarda: se canjea por un token y se descarta.
 * Cada docente ingresa su propia URL del campus + usuario + contraseña.
 */
import { useCallback, useEffect, useState } from 'react';
import { adminApi, type MiCuentaCampus as Estado } from '../../lib/apiAdmin';
import { Button, Icon } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { useToast } from '../../ui/toast';
import { avisoConexion } from './miCuentaCampus.helpers';

const LABEL = 'block text-[13px] font-medium text-on-surface mb-1.5';
const HINT  = 'mt-1.5 text-[12px] text-on-surface-variant/70 leading-relaxed';

// Se usa en el encabezado de la card contenedora (Configuracion.tsx), no acá:
// el título "Campus (Moodle)" ya vive afuera, un segundo título adentro era
// redundante.
export const MiCuentaCampusAyuda = (
  <HelpButton title="Conectar tu cuenta del campus">
    <p>
      Cuando un alumno tuyo termina un examen, la nota se manda al campus <strong>con
      tu cuenta</strong>. Así, en la libreta figura que la nota la pusiste vos y no
      un sistema anónimo.
    </p>
    <p>
      Por eso necesitás conectarte una vez. Mientras no lo hagas, las notas de tus
      comisiones se calculan y se guardan, pero <strong>no viajan al campus</strong>.
    </p>
    <p>
      <strong>Tu contraseña no se guarda.</strong> Se usa una sola vez para pedirle
      al campus una llave de acceso, y esa llave es lo único que queda guardado
      (cifrado). Si cambiás la contraseña del campus, esto sigue funcionando.
    </p>
  </HelpButton>
);

export default function MiCuentaCampus() {
  const toast = useToast();
  const [estado, setEstado] = useState<Estado | null>(null);
  const [cargando, setCargando] = useState(true);
  const [campusUrl, setCampusUrl] = useState('');
  const [usuario, setUsuario] = useState('');
  const [secreto, setSecreto] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const aplicar = useCallback((e: Estado) => {
    setEstado(e);
    setCampusUrl(e.base_url ?? '');
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
    return () => { vivo = false; };
  }, [aplicar]);

  async function guardar() {
    setError(null);
    setOk(null);
    if (!campusUrl.trim()) { setError('Ingresá la dirección de tu campus.'); return; }
    if (!usuario.trim() || !secreto.trim()) {
      setError('Completá tu usuario del campus y la contraseña.');
      return;
    }
    setGuardando(true);
    try {
      const e = await adminApi.guardarMiCuentaCampus({
        moodle_username: usuario.trim(),
        base_url: campusUrl.trim(),
        password: secreto,
      });
      aplicar(e);
      const msg = 'Tu cuenta quedó conectada.';
      setOk(msg);
      toast.success(msg);
    } catch (err) {
      const e = err as { mensaje?: string; status?: number };
      const msg =
        e.mensaje ??
        (e.status === 403
          ? 'No tenés permiso para conectar una cuenta del campus.'
          : 'No se pudo conectar con el campus. Revisá los datos.');
      setError(msg);
      toast.error(msg);
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
      const msg = 'Tu cuenta quedó desconectada.';
      setOk(msg);
      toast.success(msg);
    } catch {
      const msg = 'No se pudo desconectar.';
      setError(msg);
      toast.error(msg);
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return <div className="h-[200px] bg-surface-container-low rounded animate-pulse" />;
  }

  const aviso = avisoConexion(estado?.estado ?? null, estado?.actualizado_en ?? null);
  const conectada = aviso.tipo === 'ok' || aviso.tipo === 'por_vencer';
  const caida = aviso.tipo === 'caida';
  const vencida = aviso.tipo === 'vencida';
  const porVencer = aviso.tipo === 'por_vencer';

  return (
    <div>
      {/* Estado de conexión */}
      <div
        className={`flex items-start gap-3 rounded border px-4 py-3 text-[13px] ${
          porVencer
            ? 'border-warning-200/60 bg-warning-container/20 text-on-surface'
            : conectada
              ? 'border-success/30 bg-success-container/20 text-on-surface'
              : caida || vencida
                ? 'border-error/30 bg-error-container/20 text-on-surface'
                : 'border-outline-variant/60 bg-[#f4f5f6] text-on-surface-variant'
        }`}
      >
        <Icon
          name={porVencer ? 'error' : conectada ? 'check_circle' : vencida ? 'lock_clock' : caida ? 'link_off' : 'info'}
          className={`text-[16px] shrink-0 mt-0.5 ${
            porVencer ? 'text-warning-500' : conectada ? 'text-success' : caida || vencida ? 'text-error' : 'text-on-surface-variant'
          }`}
          fill={conectada || caida || vencida || porVencer}
        />
        <div className="min-w-0">
          {/* El usuario del campus ya se ve abajo en el formulario — repetirlo
              acá era redundante. Y si dejó de estar conectado (caída/vencida),
              decir "conectado como" no tiene sentido: ya no lo está. */}
          {aviso.tipo === 'ok' && <span>Conectado.</span>}
          {porVencer && aviso.tipo === 'por_vencer' && (
            <span>
              En {aviso.diasRestantes} {aviso.diasRestantes === 1 ? 'día' : 'días'}{' '}
              vencen tus credenciales y vas a tener que volver a ingresarlas por seguridad.
            </span>
          )}
          {caida && <span>El campus dejó de aceptar tu llave. Volvé a conectarte.</span>}
          {vencida && <span>Tu acceso venció por seguridad, volvé a ingresar tus credenciales.</span>}
          {!estado?.configurada && (
            <span>Todavía no conectaste tu cuenta. Tus notas se guardan, pero no llegan al campus.</span>
          )}
        </div>
      </div>

      {/* Formulario */}
      <div className="mt-6 space-y-5">
        <div>
          <label className={LABEL} htmlFor="campus-url">Dirección del campus</label>
          <input
            id="campus-url"
            type="url"
            className="input w-full"
            placeholder="https://campus.miuniversidad.edu.ar"
            value={campusUrl}
            onChange={(e) => setCampusUrl(e.target.value)}
            disabled={guardando}
            autoComplete="off"
          />
          <p className={HINT}>La URL de tu Moodle institucional.</p>
        </div>

        <div>
          <label className={LABEL} htmlFor="campus-user">Tu usuario del campus</label>
          <input
            id="campus-user"
            className="input w-full"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            disabled={guardando}
            autoComplete="off"
          />
        </div>

        <div>
          <label className={LABEL} htmlFor="campus-secret">Tu contraseña del campus</label>
          <input
            id="campus-secret"
            type="password"
            className="input w-full"
            value={secreto}
            onChange={(e) => setSecreto(e.target.value)}
            disabled={guardando}
            autoComplete="new-password"
            placeholder="••••••••"
          />
          <p className={HINT}>Tu contraseña no se guarda: se usa una vez para obtener una llave de acceso.</p>
        </div>

        {error && (
          <p className="text-[12.5px] text-error flex items-center gap-1.5">
            <Icon name="error" className="text-[15px]" fill />
            {error}
          </p>
        )}
        {ok && (
          <p className="text-[12.5px] text-success flex items-center gap-1.5">
            <Icon name="check_circle" className="text-[15px]" fill />
            {ok}
          </p>
        )}

        <div className="flex items-center gap-sm pt-1">
          <Button
            variant="primary"
            size="sm"
            icon={guardando ? undefined : 'link'}
            onClick={guardar}
            disabled={guardando}
          >
            {guardando ? 'Conectando…' : estado?.configurada ? 'Volver a conectar' : 'Conectar'}
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
