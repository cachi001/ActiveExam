import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { fechaEnArgentino } from '../../lib/fechaArgentina';
import {
  getExamConfig,
  publicarNotasExamen,
  puedeAvanzarVisibilidad,
  setExamConfig,
  type ExamConfig,
  type MostrarNota,
} from '../../lib/examContentAdmin';

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
  /** Tope de preguntas del examen. Cadena vacía = sin tope. */
  limitePreguntas: string;
  mostrarNota: MostrarNota;
  revisionHabilitada: boolean;
  /** c-78 D10 (E-02): el alumno ve sus eventos de proctoring mientras rinde. */
  mostrarEventosAlumno: boolean;
  politicaIntentos: 'mas_alta' | 'ultimo' | 'primero' | 'manual';
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
    limitePreguntas: cfg.limite_preguntas != null ? String(cfg.limite_preguntas) : '',
    // c-78 D9: el default de un examen nuevo es 'nunca' — la nota no se publica
    // sola, la publica una persona cuando terminó de revisar.
    mostrarNota: cfg.mostrar_nota ?? 'nunca',
    revisionHabilitada: !!cfg.revision_habilitada,
    mostrarEventosAlumno: !!cfg.mostrar_eventos_alumno,
    politicaIntentos: cfg.politica_intentos ?? 'mas_alta',
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
  if (max > 100) {
    return 'La nota máxima no puede superar 100.';
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
    mostrar_eventos_alumno: form.mostrarEventosAlumno,
    politica_intentos: form.politicaIntentos,
  };
  if (bloqueada) {
    const patch: Partial<ExamConfig> = { ...publicacion };
    // `cierre` (solo EXTENDER) e `intentos_permitidos` (solo AUMENTAR) son ampliables:
    // se envían SOLO si el tutor los cambió, para no gatillar un falso 409 por
    // truncar la precisión de una fecha que en realidad no tocó.
    if (original && form.cierre !== original.cierre) {
      patch.cierre = localInputToIso(form.cierre);
    }
    if (original && form.intentosPermitidos !== original.intentosPermitidos) {
      patch.intentos_permitidos = Number(form.intentosPermitidos);
    }
    // `apertura` está congelada, pero un examen viejo pudo quedar SIN ella y el
    // formulario la exige. Completarla se manda (el backend la acepta cuando estaba
    // vacía); si ya tenía una, no se toca.
    if (original && !original.apertura && form.apertura) {
      patch.apertura = localInputToIso(form.apertura);
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
    // `mezclar_preguntas` NO se manda: es siempre true server-side y el PATCH lo
    // rechaza (extra='forbid').
    ...publicacion,
  };
}

export function ConfiguracionExamenSection({
  examenId,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- lo pasa el padre
  sorteado: _sorteado = false,
}: {
  examenId: string;
  /** Si el examen sortea por intento, el tope de preguntas no se muestra: ya lo
   *  decidiste al elegir cuántas sortear de cada categoría. */
  sorteado?: boolean;
}) {
  const [form, setForm] = useState<ConfigForm | null>(null);
  // Config tal como vino del backend: baseline para saber si el tutor amplió
  // `cierre`/`intentos_permitidos` (candado direccional) al guardar bloqueado.
  const [original, setOriginal] = useState<ConfigForm | null>(null);
  const [bloqueada, setBloqueada] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [okGuardado, setOkGuardado] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  // c-78 D9: publicación de notas. `publicacion` guarda quién y cuándo, para
  // que el estado se pueda mostrar sin ambigüedad ("ocultas" vs "publicadas
  // el {fecha} por {persona}").
  const [publicacion, setPublicacion] = useState<{ en: string | null; por: string | null }>(
    { en: null, por: null },
  );
  const [confirmarPublicar, setConfirmarPublicar] = useState(false);
  const [publicando, setPublicando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const cfg = await getExamConfig(examenId);
      const f = configToForm(cfg);
      setForm(f);
      setOriginal(f);
      setBloqueada(!!cfg.bloqueada);
      setPublicacion({
        en: cfg.notas_publicadas_en ?? null,
        por: cfg.notas_publicadas_por ?? null,
      });
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

  async function publicarNotas() {
    setConfirmarPublicar(false);
    setPublicando(true);
    setErrorGuardar(null);
    try {
      const cfg = await publicarNotasExamen(examenId);
      const f = configToForm(cfg);
      setForm(f);
      setOriginal(f);
      setPublicacion({
        en: cfg.notas_publicadas_en ?? null,
        por: cfg.notas_publicadas_por ?? null,
      });
      setOkGuardado(true);
    } catch (err: unknown) {
      setErrorGuardar(
        err instanceof Error ? err.message : 'No se pudieron publicar las notas.',
      );
    } finally {
      setPublicando(false);
    }
  }

  const notasOcultas = form?.mostrarNota === 'nunca';

  return (
    <Card>
      <SectionTitle icon="settings" sub="La define el tutor; la plataforma la aplica al rendir.">
        Configuración del examen
      </SectionTitle>

      {/* c-78 D9: el estado de publicación arriba de todo, con su acción. El
          docente no razona en enums, razona en "reviso y publico". */}
      {!cargando && !errorCarga && form && (
        <div className="mb-lg flex flex-wrap items-center justify-between gap-md rounded-lg border border-outline-variant px-4 py-3">
          <div className="min-w-0">
            <p className="text-label-md font-semibold text-on-surface">
              {notasOcultas ? 'Las notas están ocultas' : 'Las notas están publicadas'}
            </p>
            <p className="text-label-sm text-on-surface-variant mt-0.5">
              {notasOcultas
                ? 'Los alumnos no ven su nota. Revisá primero y publicalas cuando estés listo.'
                : publicacion.en
                  ? `Publicadas el ${new Date(publicacion.en).toLocaleString('es-AR', {
                      dateStyle: 'short',
                      timeStyle: 'short',
                    })}${publicacion.por ? ` por ${publicacion.por}` : ''}.`
                  : 'Los alumnos ya pueden ver su nota.'}
            </p>
          </div>
          {notasOcultas && (
            <Button
              size="sm"
              icon="campaign"
              disabled={publicando || guardando}
              onClick={() => setConfirmarPublicar(true)}
            >
              {publicando ? 'Publicando…' : 'Publicar notas ahora'}
            </Button>
          )}
        </div>
      )}

      {/* Aviso ANTES de confirmar: la acción no se puede deshacer. */}
      {confirmarPublicar && (
        <div className="mb-lg rounded-lg border border-warning bg-warning-container/40 px-4 py-3">
          <p className="text-label-md font-semibold text-on-surface">
            Esto no se puede deshacer
          </p>
          <p className="text-label-sm text-on-surface-variant mt-0.5">
            Una vez publicadas, los alumnos van a poder ver su nota y no vas a poder
            volver a ocultarla. Si todavía estás revisando, cancelá.
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={publicarNotas}>
              Sí, publicar
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmarPublicar(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

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
        <div className="space-y-6">
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
                // Congelada SOLO si ya tenía una fecha. Un examen viejo que quedó sin
                // apertura hay que poder completarlo: el formulario la exige, y
                // dejarla deshabilitada y vacía volvía imposible guardar CUALQUIER
                // cambio. El backend aplica el mismo criterio (completar lo que nunca
                // se fijó no es modificarlo); cambiar una apertura ya puesta sigue
                // bloqueado en los dos lados.
                disabled={guardando || (bloqueada && !!original?.apertura)}
                onChange={(e) => update('apertura', e.target.value)}
              />
              {/* El control lo dibuja el NAVEGADOR con su idioma: en inglés esto
                  mismo se ve 08/27/2026 10:49 PM y el sitio no lo puede cambiar.
                  El mes con letras saca la ambigüedad. */}
              <p className="mt-1.5 text-label-sm text-on-surface-variant">
                {form.apertura ? fechaEnArgentino(form.apertura) : 'Se escribe día/mes/año.'}
              </p>
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
              <p className="mt-1.5 text-label-sm text-on-surface-variant">
                {form.cierre ? fechaEnArgentino(form.cierre) : 'Se escribe día/mes/año.'}
              </p>
              {bloqueada && (
                <p className="mt-1.5 text-label-sm text-on-surface-variant">
                  Con el examen ya rendido, el cierre solo se puede <strong>extender</strong>.
                </p>
              )}
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className={LABEL_CLS} htmlFor="cfg-nota-max">Nota máxima</label>
              <input
                id="cfg-nota-max"
                type="number"
                min={1}
                max={100}
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
              {/* c-78 D9: publicar es camino de ida, así que las opciones que
                  significan MENOS visibilidad que la actual se deshabilitan. El
                  backend las rechaza igual (409); acá se evita ofrecer algo que
                  va a fallar. */}
              <option value="nunca" disabled={!puedeAvanzarVisibilidad(form.mostrarNota, 'nunca')}>
                No mostrarla todavía (recomendado)
              </option>
              <option
                value="al_cerrar"
                disabled={!puedeAvanzarVisibilidad(form.mostrarNota, 'al_cerrar')}
              >
                Al cerrar el examen
              </option>
              <option value="inmediata">Inmediatamente al entregar</option>
            </select>
            <p className="text-label-sm text-on-surface-variant mt-1.5">
              {form.mostrarNota === 'nunca'
                ? 'Las notas están ocultas. Revisá y después publicalas con el botón de arriba.'
                : 'Ya se publicaron: no se pueden volver a ocultar. El alumno pudo haberlas visto.'}
            </p>
          </div>

          {/* c-78 D10 (E-02): mostrar u ocultar al alumno los eventos que genera
              el proctoring mientras rinde. Default NO. */}
          <div className="flex items-center justify-between gap-md border border-outline-variant rounded-lg px-4 py-3">
            <div className="min-w-0">
              <p className="text-label-md font-semibold text-on-surface">
                Mostrarle al alumno los avisos del control
              </p>
              <p className="text-label-sm text-on-surface-variant mt-0.5">
                Si lo activás, mientras rinde ve los avisos que genera el control
                (por ejemplo "no se detecta tu cara"). Apagado, rinde sin verlos:
                el control sigue funcionando igual y queda todo registrado.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.mostrarEventosAlumno}
              aria-label="Mostrarle al alumno los avisos del control"
              disabled={guardando}
              onClick={() => update('mostrarEventosAlumno', !form.mostrarEventosAlumno)}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                form.mostrarEventosAlumno ? 'bg-primary' : 'bg-surface-300'
              } disabled:opacity-50`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  form.mostrarEventosAlumno ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div>
            <label className={LABEL_CLS} htmlFor="cfg-politica-intentos">
              Nota a enviar a Moodle (cuando hay más de un intento)
            </label>
            <select
              id="cfg-politica-intentos"
              className={INPUT_CLS}
              value={form.politicaIntentos}
              disabled={guardando}
              onChange={(e) => update('politicaIntentos', e.target.value as ConfigForm['politicaIntentos'])}
            >
              <option value="mas_alta">La nota más alta (recomendado)</option>
              <option value="ultimo">El último intento</option>
              <option value="primero">El primer intento</option>
              <option value="manual">Manual — el admin elige cuál sincronizar</option>
            </select>
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

          {/* Acá vivía el aviso "Las preguntas se mezclan siempre". Se sacó el
              29/8/2026 por pedido del dueño: además de ser ruido en una pantalla
              de configuración (no se puede apagar, así que no es una decisión que
              el tutor tenga que tomar), su texto era FALSO en los exámenes
              sorteados — decía "todos rinden las mismas preguntas" justo donde
              cada alumno recibe un sorteo distinto del pool. */}
          {original && JSON.stringify(form) !== JSON.stringify(original) && (
            <div className="space-y-sm">
              {/* El resultado va PEGADO al botón. Estaba solo arriba de todo, a una
                  pantalla de scroll de acá: se apretaba Guardar, el guardado fallaba
                  con su motivo, y desde donde miraba el tutor "no pasaba nada". Un
                  error que nadie ve es un error que no existe. Arriba se conserva,
                  para el que llega scrolleando desde el principio. */}
              {errorGuardar && (
                <div className="flex items-start gap-sm text-error bg-error-container/40 rounded-lg px-4 py-3 text-label-sm">
                  <Icon name="error" className="text-[18px] shrink-0 mt-0.5" fill />
                  <span>{errorGuardar}</span>
                </div>
              )}
              {okGuardado && (
                <div className="flex items-center gap-sm text-success bg-success-container rounded-lg px-4 py-3 text-label-sm">
                  <Icon name="check_circle" className="text-[18px] shrink-0" fill />
                  Configuración guardada.
                </div>
              )}
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
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
