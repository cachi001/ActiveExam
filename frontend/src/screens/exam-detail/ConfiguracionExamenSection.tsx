import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { getExamConfig, setExamConfig, type ExamConfig } from '../../lib/examContentAdmin';

function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localInputToIso(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

export interface ConfigForm {
  sinLimite: boolean;
  tiempoLimiteMin: string;
  intentosPermitidos: string;
  apertura: string;
  cierre: string;
  notaMaxima: string;
  notaAprobacion: string;
  mezclarPreguntas: boolean;
  mostrarNota: 'al_cerrar' | 'inmediata';
  revisionHabilitada: boolean;
}

// Input moderno: EDITABLE = fondo blanco + borde limpio (se ve que se puede
// tocar); BLOQUEADO (disabled) = fondo gris claro + texto atenuado + cursor
// not-allowed (se nota que NO se puede cambiar). Focus gris (sin azul).
const INPUT_CLS =
  'w-full rounded-lg border border-surface-300 bg-white px-4 py-2.5 text-body-md text-on-surface placeholder:text-on-surface-variant shadow-sm hover:border-surface-400 focus:border-surface-500 focus:outline-none transition-colors ' +
  'disabled:bg-surface-100 disabled:text-on-surface-variant disabled:border-surface-200 disabled:shadow-none disabled:cursor-not-allowed';
const LABEL_CLS = 'block text-label-md font-semibold text-on-surface mb-1.5';

function configToForm(cfg: ExamConfig): ConfigForm {
  return {
    sinLimite: cfg.tiempo_limite_min === null,
    tiempoLimiteMin: cfg.tiempo_limite_min !== null ? String(cfg.tiempo_limite_min) : '',
    intentosPermitidos: String(cfg.intentos_permitidos ?? 1),
    apertura: isoToLocalInput(cfg.apertura),
    cierre: isoToLocalInput(cfg.cierre),
    notaMaxima: String(cfg.nota_maxima ?? 10),
    notaAprobacion: String(cfg.nota_aprobacion ?? 6),
    mezclarPreguntas: !!cfg.mezclar_preguntas,
    mostrarNota: cfg.mostrar_nota ?? 'al_cerrar',
    revisionHabilitada: !!cfg.revision_habilitada,
  };
}

function validarConfig(form: ConfigForm): string | null {
  if (!form.sinLimite) {
    const t = Number(form.tiempoLimiteMin);
    if (!form.tiempoLimiteMin.trim() || Number.isNaN(t) || t <= 0) {
      return 'El tiempo límite debe ser un número mayor a 0 (o marcá "sin límite").';
    }
  }
  const intentos = Number(form.intentosPermitidos);
  if (Number.isNaN(intentos) || intentos < 1) {
    return 'Los intentos permitidos deben ser al menos 1.';
  }
  const max = Number(form.notaMaxima);
  const aprob = Number(form.notaAprobacion);
  if (Number.isNaN(max) || max <= 0) {
    return 'La nota máxima debe ser un número mayor a 0.';
  }
  if (Number.isNaN(aprob) || aprob < 0) {
    return 'La nota de aprobación debe ser un número válido.';
  }
  if (aprob > max) {
    return 'La nota de aprobación no puede ser mayor que la nota máxima.';
  }
  // C-69: apertura y cierre son OBLIGATORIOS (el gate de "mostrar nota al cerrar"
  // depende de la fecha de cierre; el examen va de una fecha/hora a otra).
  if (!form.apertura || !form.cierre) {
    return 'La fecha de inicio y de cierre son obligatorias.';
  }
  if (new Date(form.apertura).getTime() >= new Date(form.cierre).getTime()) {
    return 'La fecha de inicio debe ser anterior a la de cierre.';
  }
  return null;
}

export function formToPatch(
  form: ConfigForm,
  bloqueada: boolean,
  original?: ConfigForm,
): Partial<ExamConfig> {
  // Candado DIRECCIONAL (C-72 secciones 6/18): con el examen ya rendido, la mecánica y
  // la nota (CONGELADO_DURO: tiempo, apertura, notas, mezclar) están congeladas en el
  // backend (409). La publicación es direccional (solo aflojar) → siempre se manda.
  const publicacion: Partial<ExamConfig> = {
    mostrar_nota: form.mostrarNota,
    revision_habilitada: form.revisionHabilitada,
  };
  if (bloqueada) {
    const patch: Partial<ExamConfig> = { ...publicacion };
    // `cierre` (solo EXTENDER) e `intentos_permitidos` (solo AUMENTAR) son ampliables:
    // se envían SOLO si el docente los cambió, para no gatillar un falso 409 por
    // truncar la precisión de una fecha que en realidad no tocó.
    if (original && form.cierre !== original.cierre) {
      patch.cierre = localInputToIso(form.cierre);
    }
    if (original && form.intentosPermitidos !== original.intentosPermitidos) {
      patch.intentos_permitidos = Number(form.intentosPermitidos);
    }
    return patch;
  }
  return {
    tiempo_limite_min: form.sinLimite ? null : Number(form.tiempoLimiteMin),
    intentos_permitidos: Number(form.intentosPermitidos),
    apertura: localInputToIso(form.apertura),
    cierre: localInputToIso(form.cierre),
    nota_maxima: Number(form.notaMaxima),
    nota_aprobacion: Number(form.notaAprobacion),
    mezclar_preguntas: form.mezclarPreguntas,
    ...publicacion,
  };
}

export function ConfiguracionExamenSection({ examenId }: { examenId: string }) {
  const [form, setForm] = useState<ConfigForm | null>(null);
  // Config tal como vino del backend: baseline para saber si el docente amplió
  // `cierre`/`intentos_permitidos` (candado direccional) al guardar bloqueado.
  const [original, setOriginal] = useState<ConfigForm | null>(null);
  const [bloqueada, setBloqueada] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [okGuardado, setOkGuardado] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const cfg = await getExamConfig(examenId);
      const f = configToForm(cfg);
      setForm(f);
      setOriginal(f);
      setBloqueada(!!cfg.bloqueada);
    } catch (err: unknown) {
      setErrorCarga(err instanceof Error ? err.message : 'No se pudo cargar la configuración.');
      setForm(null);
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function update<K extends keyof ConfigForm>(key: K, value: ConfigForm[K]) {
    setOkGuardado(false);
    setErrorGuardar(null);
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function guardar() {
    if (!form) return;
    const validationError = validarConfig(form);
    if (validationError) {
      setErrorGuardar(validationError);
      setOkGuardado(false);
      return;
    }
    setGuardando(true);
    setOkGuardado(false);
    setErrorGuardar(null);
    try {
      const cfg = await setExamConfig(examenId, formToPatch(form, bloqueada, original ?? undefined));
      const f = configToForm(cfg);
      setForm(f);
      setOriginal(f);
      setBloqueada(!!cfg.bloqueada);
      setOkGuardado(true);
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo guardar la configuración.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Card>
      <SectionTitle sub="La define el docente; la plataforma la aplica al rendir.">
        Configuración del examen
      </SectionTitle>

      {cargando && (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
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

      {!cargando && !errorCarga && form && (
        <div className="space-y-5">
          {bloqueada && (
            <div className="flex items-start gap-sm text-on-surface bg-warning-container/50 border border-warning/40 rounded-lg px-4 py-3 text-label-sm">
              <Icon name="lock" className="text-[18px] shrink-0 text-warning" fill />
              <span>
                Este examen ya tiene intentos finalizados. La mecánica y la nota
                (tiempo, apertura, notas, mezclar) quedaron <strong>congeladas</strong>
                para no alterar notas ya calculadas. Lo único que se puede mover es
                <strong> a favor del alumno</strong>: <strong>extender</strong> el cierre,
                <strong> aumentar</strong> los intentos, y aflojar la publicación
                (habilitar revisión / adelantar la nota). Nunca apretar lo que ya iba a
                tener.
              </span>
            </div>
          )}
          {okGuardado && (
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
            <label className={LABEL_CLS} htmlFor="cfg-tiempo">Tiempo límite (minutos)</label>
            <input
              id="cfg-tiempo"
              type="number"
              min={1}
              inputMode="numeric"
              className={INPUT_CLS}
              placeholder="Ej. 60"
              value={form.tiempoLimiteMin}
              disabled={form.sinLimite || guardando || bloqueada}
              onChange={(e) => update('tiempoLimiteMin', e.target.value)}
            />
            <label className="mt-2 inline-flex items-center gap-sm cursor-pointer select-none text-label-md text-on-surface-variant">
              <input
                type="checkbox"
                className="w-4 h-4 accent-primary"
                checked={form.sinLimite}
                disabled={guardando || bloqueada}
                onChange={(e) => update('sinLimite', e.target.checked)}
              />
              Sin límite de tiempo
            </label>
          </div>

          <div>
            <label className={LABEL_CLS} htmlFor="cfg-intentos">Intentos permitidos</label>
            <input
              id="cfg-intentos"
              type="number"
              // Bloqueado: solo se pueden AUMENTAR (min = los intentos vigentes).
              min={bloqueada ? Number(original?.intentosPermitidos ?? 1) : 1}
              inputMode="numeric"
              className={INPUT_CLS}
              value={form.intentosPermitidos}
              disabled={guardando}
              onChange={(e) => update('intentosPermitidos', e.target.value)}
            />
            {bloqueada && (
              <p className="mt-1.5 text-label-sm text-on-surface-variant">
                Con el examen ya rendido, los intentos solo se pueden <strong>aumentar</strong>.
              </p>
            )}
          </div>

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className={LABEL_CLS} htmlFor="cfg-apertura">Inicio del examen *</label>
              <input
                id="cfg-apertura"
                type="datetime-local"
                required
                className={INPUT_CLS}
                value={form.apertura}
                disabled={guardando || bloqueada}
                onChange={(e) => update('apertura', e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS} htmlFor="cfg-cierre">Cierre del examen *</label>
              <input
                id="cfg-cierre"
                type="datetime-local"
                required
                // Bloqueado: el cierre solo se puede EXTENDER (min = el cierre vigente).
                min={bloqueada ? original?.cierre : undefined}
                className={INPUT_CLS}
                value={form.cierre}
                disabled={guardando}
                onChange={(e) => update('cierre', e.target.value)}
              />
              {bloqueada && (
                <p className="mt-1.5 text-label-sm text-on-surface-variant">
                  Con el examen ya rendido, el cierre solo se puede <strong>extender</strong>.
                </p>
              )}
            </div>
          </div>
          <p className="-mt-3 text-label-sm text-on-surface-variant">
            El examen va de una fecha/hora a otra (obligatorio). La nota y la revisión se
            publican según el cierre.
          </p>

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className={LABEL_CLS} htmlFor="cfg-nota-max">Nota máxima</label>
              <input
                id="cfg-nota-max"
                type="number"
                min={0}
                step="any"
                inputMode="decimal"
                className={INPUT_CLS}
                value={form.notaMaxima}
                disabled={guardando || bloqueada}
                onChange={(e) => update('notaMaxima', e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS} htmlFor="cfg-nota-aprob">Nota de aprobación</label>
              <input
                id="cfg-nota-aprob"
                type="number"
                min={0}
                step="any"
                inputMode="decimal"
                className={INPUT_CLS}
                value={form.notaAprobacion}
                disabled={guardando || bloqueada}
                onChange={(e) => update('notaAprobacion', e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className={LABEL_CLS} htmlFor="cfg-mostrar-nota">¿Cuándo se muestra la nota al alumno?</label>
            <select
              id="cfg-mostrar-nota"
              className={INPUT_CLS}
              value={form.mostrarNota}
              disabled={guardando}
              onChange={(e) => update('mostrarNota', e.target.value as ConfigForm['mostrarNota'])}
            >
              <option value="al_cerrar">Al cerrar el examen (recomendado)</option>
              <option value="inmediata">Inmediatamente al entregar</option>
            </select>
            <p className="mt-1.5 text-label-sm text-on-surface-variant">
              "Al cerrar" evita que se filtren resultados mientras otros rinden: la nota
              aparece sola después de la fecha de cierre.
            </p>
          </div>

          <div className="flex items-center justify-between gap-md border border-outline-variant rounded-lg px-4 py-3">
            <div className="min-w-0">
              <p className="text-label-md font-semibold text-on-surface">Permitir revisión de respuestas</p>
              <p className="text-label-sm text-on-surface-variant mt-0.5">
                El alumno puede ver la corrección (respuestas correctas), solo después del cierre.
                Apagalo para no exponer las respuestas.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.revisionHabilitada}
              aria-label="Permitir revisión de respuestas"
              disabled={guardando}
              onClick={() => update('revisionHabilitada', !form.revisionHabilitada)}
              className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors disabled:opacity-50
                ${form.revisionHabilitada ? 'bg-primary' : 'bg-surface-200'}`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform
                  ${form.revisionHabilitada ? 'translate-x-6' : 'translate-x-1'}`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between gap-md border border-outline-variant rounded-lg px-4 py-3">
            <div className="min-w-0">
              <p className="text-label-md font-semibold text-on-surface">Mezclar preguntas</p>
              <p className="text-label-sm text-on-surface-variant mt-0.5">
                Cada alumno ve las preguntas en un orden aleatorio (la nota no depende del orden).
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.mezclarPreguntas}
              aria-label="Mezclar preguntas"
              disabled={guardando || bloqueada}
              onClick={() => update('mezclarPreguntas', !form.mezclarPreguntas)}
              className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors disabled:opacity-50
                ${form.mezclarPreguntas ? 'bg-primary' : 'bg-surface-200'}`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform
                  ${form.mezclarPreguntas ? 'translate-x-6' : 'translate-x-1'}`}
              />
            </button>
          </div>

          {original && JSON.stringify(form) !== JSON.stringify(original) && (
            <div className="flex justify-end">
              <Button
                variant="primary"
                icon={guardando ? undefined : 'save'}
                onClick={guardar}
                disabled={guardando}
              >
                {guardando ? 'Guardando…' : 'Guardar configuración'}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
