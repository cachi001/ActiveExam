import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { getMoodleTarget, setMoodleTarget, buildMoodleTarget } from '../../lib/examContentAdmin';

const SOFT_INPUT_CLS =
  'w-full rounded-lg border border-surface-300 bg-white px-3 py-2.5 text-sm shadow-sm ' +
  'text-on-surface transition-colors hover:border-surface-400 focus:border-surface-500 focus:outline-none ' +
  'disabled:bg-surface-100 disabled:text-on-surface-variant disabled:border-surface-200 disabled:shadow-none disabled:cursor-not-allowed';
const SOFT_LABEL_CLS = 'block text-sm font-medium text-on-surface';

export function DestinoMoodleSection({ examenId }: { examenId: string }) {
  const [courseId, setCourseId] = useState('');
  const [cmid, setCmid] = useState('');
  const [originalCourseId, setOriginalCourseId] = useState('');
  const [originalCmid, setOriginalCmid] = useState('');

  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [ok, setOk] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const t = await getMoodleTarget(examenId);
      const cid = t.moodle_courseid != null ? String(t.moodle_courseid) : '';
      const cm = t.moodle_cmid != null ? String(t.moodle_cmid) : '';
      setCourseId(cid);
      setCmid(cm);
      setOriginalCourseId(cid);
      setOriginalCmid(cm);
    } catch (err: unknown) {
      setErrorCarga(err instanceof Error ? err.message : 'No se pudo cargar el destino de Moodle.');
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function update(setter: (v: string) => void, value: string) {
    setOk(false);
    setErrorGuardar(null);
    setter(value);
  }

  function limpiar() {
    setOk(false);
    setErrorGuardar(null);
    setCourseId('');
    setCmid('');
  }

  async function guardar() {
    setGuardando(true);
    setOk(false);
    setErrorGuardar(null);
    try {
      const res = await setMoodleTarget(examenId, buildMoodleTarget(courseId, cmid));
      const cid = res.moodle_courseid != null ? String(res.moodle_courseid) : '';
      const cm = res.moodle_cmid != null ? String(res.moodle_cmid) : '';
      setCourseId(cid);
      setCmid(cm);
      setOriginalCourseId(cid);
      setOriginalCmid(cm);
      setOk(true);
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo guardar el destino de Moodle.');
    } finally {
      setGuardando(false);
    }
  }

  const hayCambios = courseId !== originalCourseId || cmid !== originalCmid;
  const vacio = courseId.trim() === '' && cmid.trim() === '';

  return (
    <Card>
      <SectionTitle sub="A qué curso y actividad de Moodle se le devolverá la nota. Vacío = usa el destino global.">
        Destino de la nota en Moodle
      </SectionTitle>

      {cargando && (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map((i) => (
            <div key={i} className="h-12 bg-surface-100 rounded-lg" />
          ))}
        </div>
      )}

      {!cargando && errorCarga && (
        <div className="space-y-md">
          <div
            role="alert"
            className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
          >
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {errorCarga}
          </div>
          <Button variant="outline" size="sm" icon="refresh" onClick={cargar}>
            Reintentar
          </Button>
        </div>
      )}

      {!cargando && !errorCarga && (
        <div className="space-y-4">
          {ok && (
            <div
              role="status"
              className="flex items-center gap-sm text-success bg-success-container rounded-md px-3 py-2.5 text-label-sm"
            >
              <Icon name="check_circle" className="text-[18px] shrink-0" fill />
              Destino guardado.
            </div>
          )}
          {errorGuardar && (
            <div
              role="alert"
              className="flex items-center gap-sm text-error bg-error-container/40 rounded-md px-3 py-2.5 text-label-sm"
            >
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorGuardar}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={SOFT_LABEL_CLS} htmlFor="moodle-courseid">
                ID del curso (courseid)
              </label>
              <input
                id="moodle-courseid"
                type="number"
                inputMode="numeric"
                value={courseId}
                onChange={(e) => update(setCourseId, e.target.value)}
                disabled={guardando}
                placeholder="Ej: 42"
                className={`${SOFT_INPUT_CLS} mt-2`}
              />
            </div>
            <div>
              <label className={SOFT_LABEL_CLS} htmlFor="moodle-cmid">
                ID de la actividad (cmid)
              </label>
              <input
                id="moodle-cmid"
                type="number"
                inputMode="numeric"
                value={cmid}
                onChange={(e) => update(setCmid, e.target.value)}
                disabled={guardando}
                placeholder="Ej: 128"
                className={`${SOFT_INPUT_CLS} mt-2`}
              />
            </div>
          </div>

          {hayCambios && (
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                icon="backspace"
                onClick={limpiar}
                disabled={guardando || vacio}
              >
                Limpiar destino
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={guardando ? undefined : 'save'}
                onClick={guardar}
                disabled={guardando}
              >
                {guardando ? 'Guardando…' : 'Guardar destino'}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
