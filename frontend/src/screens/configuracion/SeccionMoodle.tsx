/**
 * SeccionMoodle — conexión institucional con el campus (Moodle).
 *
 * OJO con lo que hace el token institucional: desde C-73 la NOTA ya NO se manda con
 * él, sino con la credencial del tutor a cargo (`MiCuentaCampus`), para que en la
 * libreta figure quién la puso. Al token institucional le quedan dos trabajos que la
 * cuenta de un tutor no puede hacer:
 *   1. resolver la identidad del alumno en el campus (`MoodleIdentityMapper`, por
 *      idnumber → email). Sin esto la nota no se puede dirigir a nadie y queda retenida.
 *   2. escribir el 0 de `anular_nota`: la anulación por fraude la decide un revisor,
 *      y firmarla con la cuenta del profesor le atribuiría una sanción que no tomó.
 *
 * `base_url` y `service_shortname` además son estructurales: sin ellos ningún tutor
 * puede canjear su contraseña por un token (ver backend `token_exchange.py`).
 *
 * El token se guarda CIFRADO y la API nunca lo devuelve: acá solo se ve si hay uno
 * cargado y sus últimos 4 caracteres, para reconocer cuál es sin poder leerlo.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Icon } from '../../ui/components';
import { HelpButton } from '../../ui/HelpButton';
import { adminApi, type CredencialMoodle } from '../../lib/apiAdmin';

// Mismo sistema visual que `MiCuentaCampus`: la clase `.input` de index.css y
// labels `label-sm`. Antes esta sección tenía inputs propios más grandes y labels
// en negrita, y las dos mitades de la misma tarjeta no parecían la misma pantalla.
const INPUT_CLS = 'input w-full mt-1';
const LABEL_CLS = 'text-label-sm text-on-surface-variant';

const AYUDA = (
  <HelpButton title="La conexión de la institución con el campus">
    <p>
      Estos datos son de toda la institución, no de una persona: <strong>a qué campus</strong>{' '}
      se conecta el sistema y <strong>con qué servicio</strong>. Sin ellos, ningún tutor
      puede conectar su cuenta.
    </p>
    <p>
      La <strong className="text-on-surface">llave de acceso</strong> (un “token”) la usa el
      sistema para dos cosas que no puede hacer con la cuenta de un tutor: encontrar a
      cada alumno en el campus, y poner un 0 cuando se anula un examen por fraude.
    </p>
    <p>
      La llave se guarda <strong className="text-on-surface">cifrada</strong>: una vez cargada
      nadie puede volver a verla desde acá — ni vos. Solo se muestran los últimos 4
      caracteres para reconocer cuál está puesta. Si el campus la rota, pegás la nueva y
      listo: no hace falta reiniciar nada.
    </p>
  </HelpButton>
);

export default function SeccionMoodle() {
  const [cred, setCred] = useState<CredencialMoodle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState('');
  const [component, setComponent] = useState<'mod_assign' | 'mod_quiz'>('mod_assign');
  const [servicio, setServicio] = useState('');

  const [guardando, setGuardando] = useState(false);
  const [ok, setOk] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const aplicar = useCallback((c: CredencialMoodle) => {
    setCred(c);
    setBaseUrl(c.base_url ?? '');
    setComponent(c.component ?? 'mod_assign');
    setServicio(c.service_shortname ?? '');
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
        component,
        service_shortname: servicio.trim(),
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
    <div>
      <div className="mb-md">
        <h3 className="text-title-md font-semibold text-on-surface flex items-center gap-1.5">
          Conexión de la institución
          {AYUDA}
        </h3>
        <p className="text-label-sm text-on-surface-variant mt-0.5">
          Se configura una vez y vale para todos los tutores.
        </p>
      </div>

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
                    Sin llave el sistema no puede encontrar a los alumnos en el campus: las
                    notas se calculan y quedan guardadas, pero no viajan — aunque el tutor
                    ya haya conectado su cuenta.
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

          {/* Sin `<p>` de ayuda bajo cada campo: todo eso vive en el HelpButton del
              encabezado. Repetirlo abajo duplicaba el texto y hacía que la sección
              pesara el triple que la de arriba. Solo queda la aclaración que cambia
              lo que el usuario TIENE QUE HACER. */}
          <div className="grid gap-md">
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
                Llave de acceso {cred.token_configurado && '· dejala vacía para no cambiarla'}
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
            </div>

            <div>
              <label className={LABEL_CLS} htmlFor="moodle-servicio">
                Nombre del servicio del campus
              </label>
              <input
                id="moodle-servicio"
                className={INPUT_CLS}
                placeholder="ej: activeexam"
                value={servicio}
                disabled={guardando}
                onChange={(e) => setServicio(e.target.value)}
              />
              <p className="mt-1 text-label-sm text-on-surface-variant">
                Sin esto los tutores no pueden conectar su cuenta.
              </p>
            </div>

            <div>
              <label className={LABEL_CLS} htmlFor="moodle-component">Tipo de actividad habitual</label>
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
              <p className="mt-1 text-label-sm text-on-surface-variant">
                Solo el valor por defecto: el destino real se elige en cada examen.
              </p>
            </div>
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
    </div>
  );
}
