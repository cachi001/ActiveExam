/**
 * ResetearPasswordCard — destrabar el acceso de alguien que olvidó su contraseña.
 *
 * El endpoint `POST /users/{id}/resetear-password` existe desde c-78, pero
 * **ninguna pantalla lo llamaba**: la única forma de usarlo era pegarle a la API a
 * mano. O sea, la funcionalidad estaba construida y era inalcanzable — si un docente
 * olvidaba su clave el día del examen, nadie podía ayudarlo desde la aplicación.
 *
 * Dos cuidados que el diseño del endpoint ya impone y esta pantalla respeta:
 *
 * - La temporal se muestra UNA sola vez y no se guarda en claro en ningún lado. Si
 *   se cierra sin copiarla, hay que resetear de nuevo. Por eso el aviso es
 *   explícito y el valor queda a la vista hasta que la persona lo saque de acá.
 * - El usuario queda obligado a cambiarla al entrar: el admin destraba el acceso
 *   pero no se queda sabiendo la clave de nadie.
 */
import { useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../../ui/components';
import { useToast } from '../../../ui/toast';
import { ConfirmModal } from '../../../ui/ConfirmModal';
import { adminApi } from '../../../lib/apiAdmin';
import type { UsuarioAdmin } from '../../../lib/types';

export function ResetearPasswordCard({ usuario }: { usuario: UsuarioAdmin }) {
  const toast = useToast();
  const [confirmando, setConfirmando] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [temporal, setTemporal] = useState<string | null>(null);

  const nombreVisible =
    usuario.nombre && usuario.apellido
      ? `${usuario.nombre} ${usuario.apellido}`
      : usuario.username || usuario.email;

  async function resetear() {
    setConfirmando(false);
    setGenerando(true);
    try {
      const r = await adminApi.resetearPasswordUsuario(usuario.id);
      setTemporal(r.password_temporal);
    } catch (err) {
      const e = err as { status?: number; mensaje?: string };
      // 409 = cuenta que entra por el campus: no usa contraseña, así que darle una
      // temporal le abriría un camino de entrada que hoy no tiene.
      toast.error(
        e.status === 409
          ? 'Esta cuenta entra por el campus y no usa contraseña.'
          : e.mensaje ?? 'No se pudo generar la contraseña temporal.',
      );
    } finally {
      setGenerando(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        icon="lock_reset"
        sub="Si la persona olvidó su contraseña, generá una temporal para que pueda entrar."
      >
        Contraseña
      </SectionTitle>

      {temporal ? (
        <div className="space-y-sm">
          <p className="text-body-sm text-on-surface-variant">
            Contraseña temporal de <strong>{nombreVisible}</strong>. Pasásela por un
            medio seguro: al entrar, el sistema le va a pedir que defina la suya.
          </p>
          <div className="flex items-center gap-sm rounded-lg border border-outline-variant/60 bg-surface-container-lowest px-md py-sm">
            <code className="flex-1 font-mono text-title-sm text-on-surface break-all">
              {temporal}
            </code>
            <Button
              variant="ghost"
              size="sm"
              icon="content_copy"
              onClick={() => {
                void navigator.clipboard?.writeText(temporal);
                toast.success('Contraseña copiada.');
              }}
            >
              Copiar
            </Button>
          </div>
          <p
            role="alert"
            className="flex items-start gap-xs rounded-lg bg-warning-container/60 px-md py-sm text-label-sm text-on-surface"
          >
            <Icon name="warning" className="text-[18px] shrink-0 mt-0.5" />
            <span>
              Guardala ahora: no se muestra de nuevo. Si la perdés, generá otra.
            </span>
          </p>
        </div>
      ) : (
        <Button
          variant="outline"
          icon="lock_reset"
          disabled={generando}
          onClick={() => setConfirmando(true)}
        >
          {generando ? 'Generando…' : 'Generar contraseña temporal'}
        </Button>
      )}

      <ConfirmModal
        abierto={confirmando}
        titulo="Generar una contraseña temporal"
        variante="danger"
        textoConfirmar="Generar"
        mensaje={
          <>
            <p>
              La contraseña actual de <strong>«{nombreVisible}»</strong> deja de
              funcionar en el momento.
            </p>
            <p className="mt-2">
              Vas a ver la nueva una sola vez y tenés que pasársela. Al entrar, el
              sistema le pide que defina la suya.
            </p>
          </>
        }
        onConfirmar={() => void resetear()}
        onCancelar={() => setConfirmando(false)}
      />
    </Card>
  );
}

export default ResetearPasswordCard;
