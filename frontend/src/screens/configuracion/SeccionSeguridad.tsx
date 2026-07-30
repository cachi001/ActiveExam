import { useState } from 'react';
import { Button, Icon } from '../../ui/components';
import { adminApi } from '../../lib/apiAdmin';

const LABEL = 'block text-[13px] font-medium text-on-surface mb-1.5';
const HINT  = 'mt-1.5 text-[12px] text-on-surface-variant/70 leading-relaxed';

export default function SeccionSeguridad() {
  const [abierto, setAbierto] = useState(false);
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  function abrir() { setAbierto(true); setError(null); setOk(false); }
  function cancelar() {
    setAbierto(false);
    setActual(''); setNueva(''); setConfirmar('');
    setError(null);
  }

  async function guardar() {
    setError(null);
    if (nueva.length < 8) { setError('La contraseña debe tener al menos 8 caracteres.'); return; }
    if (nueva !== confirmar) { setError('Las contraseñas no coinciden.'); return; }
    setGuardando(true);
    try {
      await adminApi.cambiarContrasena({ contrasena_actual: actual, contrasena_nueva: nueva });
      setOk(true);
      cancelar();
    } catch (err) {
      const e = err as { message?: string };
      setError(e.message || 'No se pudo cambiar la contraseña.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div>
      <h3 className="text-[15px] font-semibold text-on-surface mb-1">Seguridad</h3>
      <p className={HINT}>Actualizá tu contraseña periódicamente.</p>

      {ok && (
        <div className="mt-4 flex items-center gap-2 text-[12.5px] text-success bg-success-container/30 border border-success/30 rounded px-3 py-2">
          <Icon name="check_circle" className="text-[15px]" fill />
          Contraseña actualizada correctamente.
        </div>
      )}

      {!abierto ? (
        <div className="mt-4">
          <Button variant="outline" size="sm" icon="lock" onClick={abrir}>
            Cambiar contraseña
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-5">
          <div>
            <label className={LABEL} htmlFor="seg-actual">Contraseña actual</label>
            <input
              id="seg-actual"
              type="password"
              className="input w-full"
              value={actual}
              onChange={(e) => setActual(e.target.value)}
              disabled={guardando}
              autoComplete="current-password"
            />
          </div>

          <div>
            <label className={LABEL} htmlFor="seg-nueva">Nueva contraseña</label>
            <input
              id="seg-nueva"
              type="password"
              className="input w-full"
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              disabled={guardando}
              autoComplete="new-password"
            />
            <p className={HINT}>Mínimo 8 caracteres.</p>
          </div>

          <div>
            <label className={LABEL} htmlFor="seg-confirmar">Repetir nueva contraseña</label>
            <input
              id="seg-confirmar"
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

          <div className="flex items-center gap-sm pt-1">
            <Button variant="primary" size="sm" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar'}
            </Button>
            <Button variant="ghost" size="sm" onClick={cancelar} disabled={guardando}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
