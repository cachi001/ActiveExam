/**
 * ImportExamModal — Modal de importación de exámenes Moodle XML (C-69).
 *
 * Reemplaza la navegación a /admin/examenes/importar por un modal accesible que
 * concentra TODO el flujo de importación en un solo paso:
 *   1. Subir el XML de Moodle + título.
 *   2. Asociar materia + comisión (existente o creando nuevas).
 *   3. (Opcional) Destino de la nota en Moodle (courseid + cmid).
 *
 * Reusa el patrón de portal/overlay/Escape/foco de ConfirmModal. Renderiza vía
 * createPortal a document.body. Cierra con Escape y click en el backdrop.
 *
 * Estilo de inputs (pedido explícito): esquinas rectas (rounded-none), grandes
 * (px-4 py-3, text-base), full-width, separados (space-y-5), label arriba.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from '../../ui/components';
import { api } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  altaInlineMateriaComision,
  asociarExamenAComision,
} from '../../lib/examContentAdmin';
import type { Materia, Comision } from '../../lib/types';

export interface ImportExamModalProps {
  abierto: boolean;
  onCerrar: () => void;
  /** Se llama tras importar con éxito. `importadas` = cantidad de preguntas. */
  onImportado: (importadas: number) => void;
}

type ModoMateria = 'existente' | 'nueva';

interface ImportReport {
  examen_id: string;
  importadas: number;
}

// Clases compartidas de los inputs: rectos, grandes, separados, foco visible.
const INPUT_CLASS =
  'w-full rounded-none border border-outline bg-surface px-4 py-3 text-base ' +
  'text-on-surface outline-none transition-colors focus:border-primary ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';
const LABEL_CLASS = 'block text-label-md font-medium text-on-surface';
const HELPER_CLASS = 'mt-1 text-label-sm text-on-surface-variant';

export function ImportExamModal({ abierto, onCerrar, onImportado }: ImportExamModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cerrarRef = useRef<HTMLButtonElement>(null);

  // ── Paso 1: archivo + título ──────────────────────────────────────────────
  const [file, setFile] = useState<File | null>(null);
  const [titulo, setTitulo] = useState('');

  // ── Paso 2: materia + comisión ────────────────────────────────────────────
  const [modo, setModo] = useState<ModoMateria>('existente');
  // Existente
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [materiaId, setMateriaId] = useState('');
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [comisionId, setComisionId] = useState('');
  const [cargandoMaterias, setCargandoMaterias] = useState(false);
  const [cargandoComisiones, setCargandoComisiones] = useState(false);
  // Nueva
  const [materiaCodigo, setMateriaCodigo] = useState('');
  const [materiaNombre, setMateriaNombre] = useState('');
  const [comisionCodigo, setComisionCodigo] = useState('');
  const [comisionNombre, setComisionNombre] = useState('');

  // ── Paso 3: destino Moodle (opcional, colapsable) ─────────────────────────
  const [mostrarDestino, setMostrarDestino] = useState(false);
  const [courseId, setCourseId] = useState('');
  const [cmid, setCmid] = useState('');

  // ── Estado de envío ───────────────────────────────────────────────────────
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setFile(null);
    setTitulo('');
    setModo('existente');
    setMateriaId('');
    setComisiones([]);
    setComisionId('');
    setMateriaCodigo('');
    setMateriaNombre('');
    setComisionCodigo('');
    setComisionNombre('');
    setMostrarDestino(false);
    setCourseId('');
    setCmid('');
    setError(null);
    setEnviando(false);
  }, []);

  // Al cerrar (controlado por el padre) limpiamos el formulario.
  useEffect(() => {
    if (!abierto) resetForm();
  }, [abierto, resetForm]);

  // Foco inicial + cierre con Escape.
  useEffect(() => {
    if (!abierto) return;
    cerrarRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCerrar();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [abierto, onCerrar]);

  // Cargar materias disponibles al abrir (para el modo "Usar existente").
  useEffect(() => {
    if (!abierto) return;
    let cancelado = false;
    setCargandoMaterias(true);
    api
      .materiasDisponibles()
      .then((items) => {
        if (!cancelado) setMaterias(items);
      })
      .catch(() => {
        if (!cancelado) setMaterias([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoMaterias(false);
      });
    return () => {
      cancelado = true;
    };
  }, [abierto]);

  // Cargar comisiones cuando cambia la materia elegida.
  useEffect(() => {
    if (!materiaId) {
      setComisiones([]);
      setComisionId('');
      return;
    }
    let cancelado = false;
    setCargandoComisiones(true);
    setComisionId('');
    api
      .comisionesDeMateria(materiaId)
      .then((items) => {
        if (!cancelado) setComisiones(items);
      })
      .catch(() => {
        if (!cancelado) setComisiones([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoComisiones(false);
      });
    return () => {
      cancelado = true;
    };
  }, [materiaId]);

  // ── Validación ─────────────────────────────────────────────────────────────
  const materiaComisionOk =
    modo === 'existente'
      ? Boolean(materiaId && comisionId)
      : Boolean(
          materiaCodigo.trim() &&
            materiaNombre.trim() &&
            comisionCodigo.trim() &&
            comisionNombre.trim(),
        );

  const puedeEnviar = Boolean(file && titulo.trim()) && materiaComisionOk && !enviando;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !puedeEnviar) return;

    setEnviando(true);
    setError(null);

    const tieneDestino = courseId.trim() !== '' || cmid.trim() !== '';

    try {
      // 1. Import del XML (multipart). Mandamos el destino en el mismo request si
      //    se completó, así no hace falta un segundo call a setMoodleTarget.
      const formData = new FormData();
      formData.append('file', file);
      formData.append('titulo', titulo.trim());
      if (courseId.trim()) formData.append('moodle_courseid', courseId.trim());
      if (cmid.trim()) formData.append('moodle_cmid', cmid.trim());

      const token = authProvider.getToken();
      const resp = await fetch('/api/v1/exam-content/moodle-import', {
        method: 'POST',
        // No seteamos Content-Type: el browser fija el boundary del multipart.
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${resp.status}`);
      }
      const report = (await resp.json()) as ImportReport;

      // 2. Asociar materia + comisión.
      if (modo === 'existente') {
        await asociarExamenAComision(report.examen_id, comisionId);
      } else {
        await altaInlineMateriaComision(
          { codigo: materiaCodigo.trim(), nombre: materiaNombre.trim() },
          { codigo: comisionCodigo.trim(), nombre: comisionNombre.trim() },
          report.examen_id,
        );
      }

      // 3. (El destino ya viajó en el import si se completó; nada más que hacer.)
      void tieneDestino;

      // 4. Éxito: el padre cierra el modal y refresca la lista.
      onImportado(report.importadas ?? 0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Error al importar el examen. Intentá de nuevo.',
      );
      setEnviando(false);
    }
  }

  if (!abierto) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto p-md
        bg-black/40 animate-in fade-in sm:items-center"
      onClick={onCerrar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-modal-titulo"
        className="my-auto w-full max-w-[560px] bg-surface-container-lowest shadow-card-lg
          border border-outline-variant/40 animate-in zoom-in fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-md border-b border-outline-variant/40 px-lg py-base">
          <div className="min-w-0">
            <h2
              id="import-modal-titulo"
              className="font-headline text-title-lg tracking-tight text-on-surface"
            >
              Importar examen
            </h2>
            <p className="mt-0.5 text-label-sm text-on-surface-variant">
              Subí un XML de Moodle y asocialo a una materia y comisión.
            </p>
          </div>
          <button
            ref={cerrarRef}
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar"
            className="shrink-0 rounded-md p-1 text-on-surface-variant transition-colors
              hover:bg-surface-container hover:text-on-surface
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <Icon name="close" className="text-[22px]" />
          </button>
        </div>

        {/* Body scrolleable */}
        <form onSubmit={handleSubmit} className="max-h-[70vh] overflow-y-auto px-lg py-lg">
          <div className="space-y-5">
            {/* 1. Archivo XML (obligatorio) */}
            <div>
              <label className={LABEL_CLASS} htmlFor="import-file">
                Archivo Moodle XML <span className="text-error">*</span>
              </label>
              <p className={HELPER_CLASS}>Exportá el banco de preguntas desde Moodle en formato XML.</p>
              <input
                ref={fileInputRef}
                id="import-file"
                type="file"
                accept=".xml"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-2 block w-full cursor-pointer rounded-none border border-outline
                  bg-surface px-4 py-3 text-base text-on-surface outline-none transition-colors
                  focus:border-primary
                  file:mr-4 file:rounded-none file:border-0 file:bg-primary file:px-4 file:py-2
                  file:text-label-md file:font-medium file:text-on-primary hover:file:bg-primary-700"
              />
              {file && (
                <p className="mt-2 flex items-center gap-1 text-label-sm text-on-surface-variant">
                  <Icon name="description" className="text-[16px]" />
                  <span className="truncate">{file.name}</span>
                </p>
              )}
            </div>

            {/* 2. Título (obligatorio) */}
            <div>
              <label className={LABEL_CLASS} htmlFor="import-titulo">
                Título del examen <span className="text-error">*</span>
              </label>
              <input
                id="import-titulo"
                type="text"
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                placeholder="Ej: Parcial Programación 1 — 2026"
                className={`${INPUT_CLASS} mt-2`}
              />
            </div>

            {/* 3. Materia y comisión (obligatorias) */}
            <div>
              <span className={LABEL_CLASS}>
                Materia y comisión <span className="text-error">*</span>
              </span>

              {/* Toggle segmented */}
              <div className="mt-2 inline-flex w-full border border-outline" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={modo === 'existente'}
                  onClick={() => setModo('existente')}
                  className={`flex-1 px-4 py-2.5 text-label-md font-medium transition-colors ${
                    modo === 'existente'
                      ? 'bg-primary text-on-primary'
                      : 'bg-surface text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  Usar existente
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={modo === 'nueva'}
                  onClick={() => setModo('nueva')}
                  className={`flex-1 border-l border-outline px-4 py-2.5 text-label-md font-medium transition-colors ${
                    modo === 'nueva'
                      ? 'bg-primary text-on-primary'
                      : 'bg-surface text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  Crear nueva
                </button>
              </div>

              {modo === 'existente' ? (
                <div className="mt-4 space-y-4">
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-materia">
                      Materia
                    </label>
                    <select
                      id="import-materia"
                      value={materiaId}
                      onChange={(e) => setMateriaId(e.target.value)}
                      disabled={cargandoMaterias}
                      className={`${INPUT_CLASS} mt-2`}
                    >
                      <option value="">
                        {cargandoMaterias ? 'Cargando materias…' : 'Elegí una materia'}
                      </option>
                      {materias.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.nombre}
                          {m.codigo ? ` (${m.codigo})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-comision">
                      Comisión
                    </label>
                    <select
                      id="import-comision"
                      value={comisionId}
                      onChange={(e) => setComisionId(e.target.value)}
                      disabled={!materiaId || cargandoComisiones}
                      className={`${INPUT_CLASS} mt-2`}
                    >
                      <option value="">
                        {!materiaId
                          ? 'Elegí primero una materia'
                          : cargandoComisiones
                            ? 'Cargando comisiones…'
                            : 'Elegí una comisión'}
                      </option>
                      {comisiones.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre}
                          {c.codigo ? ` (${c.codigo})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-materia-codigo">
                      Materia — código
                    </label>
                    <input
                      id="import-materia-codigo"
                      type="text"
                      value={materiaCodigo}
                      onChange={(e) => setMateriaCodigo(e.target.value)}
                      placeholder="Ej: PROG1"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-materia-nombre">
                      Materia — nombre
                    </label>
                    <input
                      id="import-materia-nombre"
                      type="text"
                      value={materiaNombre}
                      onChange={(e) => setMateriaNombre(e.target.value)}
                      placeholder="Ej: Programación 1"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-comision-codigo">
                      Comisión — código
                    </label>
                    <input
                      id="import-comision-codigo"
                      type="text"
                      value={comisionCodigo}
                      onChange={(e) => setComisionCodigo(e.target.value)}
                      placeholder="Ej: C1"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-comision-nombre">
                      Comisión — nombre
                    </label>
                    <input
                      id="import-comision-nombre"
                      type="text"
                      value={comisionNombre}
                      onChange={(e) => setComisionNombre(e.target.value)}
                      placeholder="Ej: Comisión 1"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 4. Destino Moodle (opcional, colapsable) */}
            <div className="border border-outline-variant/60">
              <button
                type="button"
                onClick={() => setMostrarDestino((v) => !v)}
                aria-expanded={mostrarDestino}
                className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-surface-container"
              >
                <span className="text-label-md font-medium text-on-surface">
                  Destino de la nota en Moodle{' '}
                  <span className="font-normal text-on-surface-variant">(opcional)</span>
                </span>
                <Icon
                  name={mostrarDestino ? 'expand_less' : 'expand_more'}
                  className="text-[22px] text-on-surface-variant"
                />
              </button>
              {mostrarDestino && (
                <div className="space-y-4 border-t border-outline-variant/60 px-4 py-4">
                  <p className="text-label-sm text-on-surface-variant">
                    A qué curso y actividad de Moodle se le devolverá la nota. Podés
                    completarlo ahora o más tarde.
                  </p>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-courseid">
                      ID del curso (courseid)
                    </label>
                    <input
                      id="import-courseid"
                      type="number"
                      inputMode="numeric"
                      value={courseId}
                      onChange={(e) => setCourseId(e.target.value)}
                      placeholder="Ej: 42"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLASS} htmlFor="import-cmid">
                      ID de la actividad (cmid)
                    </label>
                    <input
                      id="import-cmid"
                      type="number"
                      inputMode="numeric"
                      value={cmid}
                      onChange={(e) => setCmid(e.target.value)}
                      placeholder="Ej: 128"
                      className={`${INPUT_CLASS} mt-2`}
                    />
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="border border-error-200 bg-error-50 px-4 py-3 text-label-md text-error-700">
                {error}
              </div>
            )}
          </div>

          {/* Footer acciones */}
          <div className="mt-6 flex items-center justify-end gap-sm border-t border-outline-variant/40 pt-4">
            <Button type="button" variant="ghost" size="md" onClick={onCerrar} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" size="md" icon="upload" disabled={!puedeEnviar}>
              {enviando ? 'Importando…' : 'Importar examen'}
            </Button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}

export default ImportExamModal;
