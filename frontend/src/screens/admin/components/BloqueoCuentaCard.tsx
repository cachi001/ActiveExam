/**
 * BloqueoCuentaCard — ver y levantar el bloqueo por intentos fallidos.
 *
 * El login bloquea la cuenta 15 minutos tras 5 intentos fallidos, y corta por ese
 * bloqueo ANTES de mirar la contraseña. Faltaban las dos mitades del problema:
 *
 * - **Nadie veía el bloqueo.** Ninguna pantalla mostraba el estado, así que el
 *   admin se enteraba solo si la persona avisaba.
 * - **La única forma de destrabar era resetear la contraseña**, que además le
 *   cambia la clave y la obliga a elegir una nueva antes de poder rendir. En
 *   pleno examen eso es tiempo perdido por algo que no hizo falta.
 *
 * Esta tarjeta muestra el estado con un reloj y ofrece un desbloqueo que **no
 * toca la contraseña**: la persona vuelve a entrar con la que ya sabe.
 *
 * Los intentos acumulados se muestran aunque el bloqueo haya vencido: el
 * contador no se limpia solo, así que con 4 encima el próximo error vuelve a
 * bloquear otros 15 minutos.
 */
import { useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../../ui/components';
import { useToast } from '../../../ui/toast';
import { adminApi } from '../../../lib/apiAdmin';
import { textoDeEspera } from '../../../lib/auth/bloqueoCuenta';
import type { UsuarioAdmin } from '../../../lib/types';

interface Props {
  usuario: UsuarioAdmin;
  /** Se llama tras destrabar, para que la pantalla recargue el detalle. */
  onDesbloqueado?: () => void;
}

export function BloqueoCuentaCard({ usuario, onDesbloqueado }: Props) {
  const toast = useToast();
  const [enviando, setEnviando] = useState(false);
  const [desbloqueado, setDesbloqueado] = useState(false);
  const [segundos, setSegundos] = useState<number | null>(
    usuario.bloqueo_segundos_restantes ?? null,
  );

  // El reloj corre en el cliente desde los segundos que mandó el servidor, así no
  // depende de que los dos relojes coincidan (mismo criterio que el cartel del
  // login). Al llegar a cero la cuenta se destraba sola.
  useEffect(() => {
    if (segundos === null || segundos <= 0) return;
    const t = setTimeout(() => setSegundos((s) => (s === null ? null : s - 1)), 1000);
    return () => clearTimeout(t);
  }, [segundos]);

  const bloqueado =
    !desbloqueado && (usuario.bloqueado ?? false) && (segundos === null || segundos > 0);
  const intentos = desbloqueado ? 0 : usuario.intentos_fallidos ?? 0;

  const nombreVisible =
    usuario.nombre && usuario.apellido
      ? `${usuario.nombre} ${usuario.apellido}`
      : usuario.username || usuario.email;

  async function desbloquear() {
    setEnviando(true);
    try {
      const r = await adminApi.desbloquearUsuario(usuario.id);
      setDesbloqueado(true);
      setSegundos(null);
      toast.success(
        r.estaba_bloqueada
          ? `Cuenta destrabada. ${nombreVisible} ya puede entrar con su contraseña de siempre.`
          : 'La cuenta no estaba bloqueada. Se limpió el contador de intentos fallidos.',
      );
      onDesbloqueado?.();
    } catch (err) {
      const e = err as { mensaje?: string };
      toast.error(e.mensaje ?? 'No se pudo desbloquear la cuenta.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        icon="lock_clock"
        sub="Cinco intentos fallidos bloquean la cuenta 15 minutos. Acá se ve y se levanta."
      >
        Bloqueo por intentos fallidos
      </SectionTitle>

      {bloqueado ? (
        <div
          role="alert"
          className="flex items-start gap-xs rounded-lg bg-error-container/60 px-md py-sm text-body-sm text-on-surface"
        >
          <Icon name="lock" className="text-[18px] shrink-0 mt-0.5" fill />
          <span>
            La cuenta está <strong>bloqueada</strong> por intentos fallidos.
            {segundos !== null && (
              <>
                {' '}
                Se destraba sola en{' '}
                <strong className="tabular-nums">{textoDeEspera(segundos)}</strong>.
              </>
            )}
          </span>
        </div>
      ) : intentos > 0 ? (
        <p className="text-body-sm text-on-surface-variant">
          La cuenta no está bloqueada, pero arrastra{' '}
          <strong>
            {intentos} {intentos === 1 ? 'intento fallido' : 'intentos fallidos'}
          </strong>
          . El contador no se limpia con el tiempo: al llegar a 5, la cuenta queda
          bloqueada 15 minutos.
        </p>
      ) : (
        <p className="text-body-sm text-on-surface-variant">
          La cuenta no tiene bloqueos ni intentos fallidos pendientes.
        </p>
      )}

      {(bloqueado || intentos > 0) && (
        <div className="mt-md">
          <Button
            variant="outline"
            icon="lock_open"
            disabled={enviando}
            onClick={() => void desbloquear()}
          >
            {enviando ? 'Desbloqueando…' : 'Desbloquear la cuenta'}
          </Button>
          <p className="mt-xs text-label-sm text-on-surface-variant">
            No le cambia la contraseña: entra con la que ya sabe.
          </p>
        </div>
      )}
    </Card>
  );
}

export default BloqueoCuentaCard;
