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
 * Estilo (rediseño minimalista): modal compacto (max-w-md), título sobrio,
 * ritmo prolijo (space-y-4), inputs de altura moderada (py-2.5 text-sm) con
 * radio chico consistente, y un dropzone elegante para el archivo (en vez del
 * input nativo feo). El color de acción es el primary del design system.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from '../../ui/components';
import { api, API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import {
  altaInlineMateriaComision,
  asociarExamenAComision,
} from '../../lib/examContentAdmin';
import type { Materia, Comision } from '../../lib/types';

import { fetchAutenticado } from '../../lib/fetchAutenticado';
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

// Clases compartidas de los inputs: compactos, radio chico, foco con primary.
// Borde suave (outline-variant) para que no se vean oscuros; el foco vira a primary.
const INPUT_CLASS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';
const LABEL_CLASS = 'block text-sm font-medium text-on-surface';
const HELPER_CLASS = 'mt-1 text-xs text-on-surface-variant';

export function ImportExamModal({ abierto, onCerrar, onImportado }: ImportExamModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cerrarRef = useRef<HTMLButtonElement>(null);

  // ── Paso 1: archivo + título ──────────────────────────────────────────────
  const [file, setFile] = useState<File | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
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

  // Toma el primer archivo de un FileList (acepta solo .xml; si arrastran otro
  // formato lo ignoramos en silencio, igual que el accept del input).
  const tomarArchivo = useCallback((files: FileList | null) => {
    const f = files?.[0];
    if (f && f.name.toLowerCase().endsWith('.xml')) setFile(f);
  }, []);

  const quitarArchivo = useCallback(() => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const resetForm = useCallback(() => {
    setFile(null);
    setArrastrando(false);
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
      const resp = await fetchAutenticado(`${API_BASE}/exam-content/moodle-import`, {
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
        className="my-auto flex max-h-[85vh] w-full max-w-md sm:max-w-2xl flex-col overflow-hidden
          rounded-xl bg-surface-container-lowest shadow-card-lg
          border border-outline-variant/40 animate-in zoom-in fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header sticky, sobrio */}
        <div className="flex shrink-0 items-start justify-between gap-sm border-b border-outline-variant/60 px-5 py-4">
          <div className="min-w-0">
            <h2
              id="import-modal-titulo"
              className="text-lg font-semibold leading-tight tracking-tight text-on-surface"
            >
              Importar examen
            </h2>
            <p className="mt-0.5 text-sm text-on-surface-variant">
              Subí un XML de Moodle y asocialo a una materia y comisión.
            </p>
          </div>
          <button
            ref={cerrarRef}
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar"
            className="-mr-1 -mt-0.5 shrink-0 rounded-md p-1.5 text-on-surface-variant transition-colors
              hover:bg-surface-container hover:text-on-surface
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        {/* Body scrolleable */}
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
            {/* 1. Archivo XML (obligatorio) — dropzone elegante */}
            <div>
              <label className={LABEL_CLASS} htmlFor="import-file">
                Archivo Moodle XML <span className="text-error">*</span>
              </label>

              {/* Input nativo oculto: lo disparamos desde el dropzone/chip. */}
              <input
                ref={fileInputRef}
                id="import-file"
                type="file"
                accept=".xml"
                className="sr-only"
                onChange={(e) => tomarArchivo(e.target.files)}
              />

              {file ? (
                // Chip prolijo con el archivo elegido.
                <div className="mt-2 flex items-center gap-3 rounded-md border border-outline-variant bg-surface-container-low px-3 py-2.5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-fixed text-primary">
                    <Icon name="description" className="text-[20px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-on-surface">{file.name}</p>
                    <p className="text-xs text-on-surface-variant">
                      {(file.size / 1024).toFixed(0)} KB · XML de Moodle
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={quitarArchivo}
                    aria-label="Quitar archivo"
                    className="shrink-0 rounded-md p-1.5 text-on-surface-variant transition-colors
                      hover:bg-surface-container hover:text-on-surface
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                  >
                    <Icon name="close" className="text-[18px]" />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setArrastrando(true);
                  }}
                  onDragLeave={() => setArrastrando(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setArrastrando(false);
                    tomarArchivo(e.dataTransfer.files);
                  }}
                  className={`mt-2 flex w-full flex-col items-center justify-center gap-1.5
                    rounded-md border border-dashed px-4 py-6 text-center transition-colors
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 ${
                      arrastrando
                        ? 'border-primary bg-primary-fixed/40'
                        : 'border-outline-variant hover:border-primary hover:bg-surface-container-low'
                    }`}
                >
                  <Icon name="upload_file" className="text-[26px] text-primary" />
                  <span className="text-sm font-medium text-primary">Seleccioná un archivo</span>
                  <span className="text-xs text-on-surface-variant">
                    o arrastrá el XML de Moodle aquí
                  </span>
                </button>
              )}
              <p className={HELPER_CLASS}>
                Exportá el banco de preguntas desde Moodle en formato XML.
              </p>
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

              {/* Toggle segmentado prolijo */}
              <div
                className="mt-2 inline-flex w-full gap-1 rounded-md border border-outline-variant bg-surface-container-low p-1"
                role="tablist"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={modo === 'existente'}
                  onClick={() => setModo('existente')}
                  className={`flex-1 rounded-[5px] px-3 py-1.5 text-sm font-medium transition-colors ${
                    modo === 'existente'
                      ? 'bg-primary text-on-primary shadow-sm'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Usar existente
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={modo === 'nueva'}
                  onClick={() => setModo('nueva')}
                  className={`flex-1 rounded-[5px] px-3 py-1.5 text-sm font-medium transition-colors ${
                    modo === 'nueva'
                      ? 'bg-primary text-on-primary shadow-sm'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Crear nueva
                </button>
              </div>

              {modo === 'existente' ? (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
            <div className="rounded-md border border-outline-variant/60">
              <button
                type="button"
                onClick={() => setMostrarDestino((v) => !v)}
                aria-expanded={mostrarDestino}
                className="flex w-full items-center justify-between rounded-md px-3 py-2.5 text-left transition-colors hover:bg-surface-container-low"
              >
                <span className="text-sm font-medium text-on-surface">
                  Destino de la nota en Moodle{' '}
                  <span className="font-normal text-on-surface-variant">(opcional)</span>
                </span>
                <Icon
                  name={mostrarDestino ? 'expand_less' : 'expand_more'}
                  className="text-[20px] text-on-surface-variant"
                />
              </button>
              {mostrarDestino && (
                <div className="space-y-4 border-t border-outline-variant/60 px-3 py-3.5">
                  <p className="text-xs text-on-surface-variant">
                    A qué curso y actividad de Moodle se le devolverá la nota. Podés
                    completarlo ahora o más tarde.
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2">
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
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-md border border-error-200 bg-error-50 px-3 py-2.5 text-sm text-error-700">
                <Icon name="error" className="mt-0.5 shrink-0 text-[18px]" />
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Footer acciones — alineado a la derecha, sticky al fondo */}
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-outline-variant/60 px-5 py-3.5">
            <Button type="button" variant="ghost" size="sm" onClick={onCerrar} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" size="sm" icon="upload" disabled={!puedeEnviar}>
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
