/**
 * SeccionMoodle — credencial de servicio del campus (Moodle).
 *
 * Es UNA credencial institucional, no una por docente: el envío de notas lo hace
 * una cuenta de servicio del campus. El token se guarda CIFRADO en la base y la
 * API nunca lo devuelve, así que acá solo se puede ver si hay uno cargado y sus
 * últimos 4 caracteres — para reconocer cuál es sin poder leerlo.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { adminApi, type CredencialMoodle } from '../../lib/apiAdmin';

const INPUT_CLS =
  'w-full rounded-lg border border-surface-300 bg-white px-4 py-2.5 text-body-md text-on-surface placeholder:text-on-surface-variant shadow-sm hover:border-surface-400 focus:border-surface-500 focus:outline-none transition-colors ' +
  'disabled:bg-surface-100 disabled:text-on-surface-variant disabled:border-surface-200 disabled:shadow-none disabled:cursor-not-allowed';
const LABEL_CLS = 'block text-label-md font-semibold text-on-surface mb-1.5';

const AYUDA = (
  <HelpButton title="¿Qué es esto?">
    <p>
      Para que las notas de los exámenes lleguen solas a la libreta del campus, el
      sistema necesita una <strong className="text-on-surface">llave de acceso</strong> (un
      “token”) que le da el campus. Es una sola llave para toda la institución.
    </p>
    <p>
      La llave se guarda <strong className="text-on-surface">cifrada</strong>: una vez que la
      cargás, nadie puede volver a verla desde acá — ni vos. Solo se muestran los
      últimos 4 caracteres para que sepas cuál está puesta.
    </p>
    <p>
      Si la llave cambia (por seguridad se rota cada tanto), pegás la nueva acá y listo:
      no hace falta reiniciar nada ni tocar el servidor.
    </p>
  </HelpButton>
);

export default function SeccionMoodle() {
  const [cred, setCred] = useState<CredencialMoodle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState('');
  const [courseid, setCourseid] = useState('');
  const [cmid, setCmid] = useState('');
  const [component, setComponent] = useState<'mod_assign' | 'mod_quiz'>('mod_assign');

  const [guardando, setGuardando] = useState(false);
  const [ok, setOk] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const aplicar = useCallback((c: CredencialMoodle) => {
    setCred(c);
    setBaseUrl(c.base_url ?? '');
    setCourseid(String(c.courseid ?? 0));
    setCmid(String(c.cmid ?? 0));
    setComponent(c.component ?? 'mod_assign');
    setToken('');
  }, []);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      aplicar(await adminApi.obtenerCredencialMoodle());
    } catch (err: unknown) {
      setErrorCarga(
        err instanceof Error ? err.message : 'No se pudo cargar la configuración del campus.',
      );
    } finally {
      setCargando(false);
    }
  }, [aplicar]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardar() {
    setGuardando(true);
    setOk(false);
    setErrorGuardar(null);
    try {
      const c = await adminApi.guardarCredencialMoodle({
        base_url: baseUrl.trim(),
        // Vacío = no tocar el token guardado.
        ...(token.trim() ? { token: token.trim() } : {}),
        courseid: Number(courseid) || 0,
        cmid: Number(cmid) || 0,
        component,
      });
      aplicar(c);
      setOk(true);
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  }

  async function borrarToken() {
    setGuardando(true);
    setOk(false);
    setErrorGuardar(null);
    try {
      aplicar(await adminApi.borrarTokenMoodle());
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo borrar la llave.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Card>
      <SectionTitle sub="Llave de acceso al campus para enviar las notas. Se guarda cifrada.">
        Conexión con el campus (Moodle) {AYUDA}
      </SectionTitle>

      {cargando && (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-surface-100 rounded-lg" />
          ))}
        </div>
      )}

      {!cargando && errorCarga && (
        <div className="space-y-md">
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {errorCarga}
          </div>
          <Button variant="outline" size="sm" icon="refresh" onClick={cargar}>
            Reintentar
          </Button>
        </div>
      )}

      {!cargando && !errorCarga && cred && (
        <div className="space-y-5">
          {/* Estado actual de la llave */}
          <div
            className={`flex items-start gap-sm rounded-lg px-4 py-3 text-label-sm border ${
              cred.token_configurado
                ? 'border-success/40 bg-success-container/40 text-on-surface'
                : 'border-warning/40 bg-warning-container/50 text-on-surface'
            }`}
          >
            <Icon
              name={cred.token_configurado ? 'check_circle' : 'key_off'}
              className={`text-[18px] shrink-0 mt-0.5 ${cred.token_configurado ? 'text-success' : 'text-warning'}`}
              fill
            />
            <div className="min-w-0">
              {cred.token_configurado ? (
                <>
                  <p className="font-semibold">Hay una llave cargada</p>
                  <p className="text-on-surface-variant mt-0.5">
                    {cred.token_pista
                      ? `Termina en «${cred.token_pista}».`
                      : 'Viene de la configuración del servidor.'}{' '}
                    {cred.actualizado_por && `Última vez cargada por ${cred.actualizado_por}.`}
                  </p>
                </>
              ) : (
                <>
                  <p className="font-semibold">Todavía no hay llave</p>
                  <p className="text-on-surface-variant mt-0.5">
                    Sin llave, las notas se calculan y quedan guardadas, pero no se envían al
                    campus.
                  </p>
                </>
              )}
            </div>
          </div>

          {ok && (
            <div className="flex items-center gap-sm text-success bg-success-container rounded-lg px-4 py-3 text-label-sm">
              <Icon name="check_circle" className="text-[18px] shrink-0" fill />
              Configuración guardada.
            </div>
          )}
          {errorGuardar && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-lg px-4 py-3 text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorGuardar}
            </div>
          )}

          <div>
            <label className={LABEL_CLS} htmlFor="moodle-url">Dirección del campus</label>
            <input
              id="moodle-url"
              type="url"
              className={INPUT_CLS}
              placeholder="https://campus.miuniversidad.edu.ar"
              value={baseUrl}
              disabled={guardando}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>

          <div>
            <label className={LABEL_CLS} htmlFor="moodle-token">
              Llave de acceso {cred.token_configurado && '(dejala vacía para no cambiarla)'}
            </label>
            <input
              id="moodle-token"
              type="password"
              autoComplete="off"
              className={INPUT_CLS}
              placeholder={cred.token_configurado ? '••••••••••••••••' : 'Pegá acá la llave que te dio el campus'}
              value={token}
              disabled={guardando}
              onChange={(e) => setToken(e.target.value)}
            />
            <p className="mt-1.5 text-label-sm text-on-surface-variant">
              Se guarda cifrada. No vas a poder volver a verla: si la perdés, pedí una nueva
              al campus y pegala acá.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className={LABEL_CLS} htmlFor="moodle-courseid">Curso por defecto (ID)</label>
              <input
                id="moodle-courseid"
                type="number"
                min={0}
                inputMode="numeric"
                className={INPUT_CLS}
                value={courseid}
                disabled={guardando}
                onChange={(e) => setCourseid(e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS} htmlFor="moodle-cmid">Actividad por defecto (ID)</label>
              <input
                id="moodle-cmid"
                type="number"
                min={0}
                inputMode="numeric"
                className={INPUT_CLS}
                value={cmid}
                disabled={guardando}
                onChange={(e) => setCmid(e.target.value)}
              />
            </div>
          </div>
          <p className="-mt-3 text-label-sm text-on-surface-variant">
            Se usan solo cuando un examen no tiene su propio destino configurado.
          </p>

          <div>
            <label className={LABEL_CLS} htmlFor="moodle-component">Tipo de actividad</label>
            <select
              id="moodle-component"
              className={INPUT_CLS}
              value={component}
              disabled={guardando}
              onChange={(e) => setComponent(e.target.value as 'mod_assign' | 'mod_quiz')}
            >
              <option value="mod_assign">Tarea (mod_assign)</option>
              <option value="mod_quiz">Cuestionario (mod_quiz)</option>
            </select>
          </div>

          <div className="flex justify-between items-center gap-md pt-2 border-t border-outline-variant/40">
            {cred.token_configurado && cred.token_pista ? (
              <Button variant="ghost" size="sm" icon="delete" onClick={borrarToken} disabled={guardando}>
                Borrar la llave
              </Button>
            ) : (
              <span />
            )}
            <Button variant="primary" icon={guardando ? undefined : 'save'} onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
