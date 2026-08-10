/**
 * ImportarBancoModal — importa un XML de Moodle directo al banco de preguntas.
 *
 * Flujo en 2 pasos (sin crear examen — el banco es el destino):
 *  1. Elegís el archivo → se previsualiza: árbol de categorías/subcategorías
 *     detectadas en el XML + cuántas preguntas de cada tipo trae cada una,
 *     y las omitidas (si las hay). Nada se persiste todavía.
 *  2. Confirmás → recién ahí se importa de verdad, y se muestra el resumen
 *     final (nuevas / actualizadas / omitidas), estilo chips.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from '../../ui/components';
import {
  previewImportarBancoXml,
  importarBancoXml,
  type PreviewImportBancoResult,
  type ImportarBancoXmlResult,
  type PreguntaImportadaItem,
} from '../../lib/apiAdmin/bancoPreguntasApi';

export interface ImportarBancoModalProps {
  abierto: boolean;
  materiaId: string;
  onCerrar: () => void;
  onImportado: (resultado: ImportarBancoXmlResult) => void;
}

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero/Falso',
  cloze: 'Cloze',
  ddwtos: 'Arrastrar y soltar en el texto',
  // Tipos NO soportados — solo aparecen en "omitidas", nunca se importan.
  matching: 'Emparejamiento',
  essay: 'Ensayo',
  numerical: 'Numérica',
  shortanswer: 'Respuesta corta',
  description: 'Descripción (sin respuesta)',
};

/** Tipos de Moodle que hoy SÍ se importan al banco. */
const TIPOS_SOPORTADOS = ['Opción múltiple', 'Verdadero/Falso', 'Cloze', 'Arrastrar y soltar en el texto'];

/** Debe coincidir con SIN_CATEGORIA_SENTINEL del backend (import_service.py). */
const SIN_CATEGORIA_KEY = '__sin_categoria__';

function tipoLabel(tipo: string): string {
  return TIPO_PREGUNTA_LABEL[tipo] ?? tipo;
}

function resumenTipos(porTipo: Record<string, number>): string {
  return Object.entries(porTipo)
    .map(([tipo, n]) => `${n} · ${tipoLabel(tipo)}`)
    .join(', ');
}

function totalTipos(porTipo: Record<string, number>): number {
  return Object.values(porTipo).reduce((acc, n) => acc + n, 0);
}

/** Sección desplegable con el detalle de qué preguntas entraron (Nuevas/Actualizadas). */
function ListaPreguntasDesplegable({
  titulo,
  items,
  abierto,
  onToggle,
}: {
  titulo: string;
  items: PreguntaImportadaItem[];
  abierto: boolean;
  onToggle: () => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-lg border border-outline-variant/40">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-label-md font-medium text-on-surface"
      >
        <Icon name={abierto ? 'expand_less' : 'expand_more'} className="text-[18px]" />
        {titulo} ({items.length})
      </button>
      {abierto && (
        <ul className="max-h-40 overflow-y-auto border-t border-outline-variant/20 px-3 py-2 space-y-1.5">
          {items.map((p, i) => (
            <li key={i} className="flex items-center gap-2 text-label-sm">
              <span className="text-on-surface truncate flex-1">{p.enunciado}</span>
              <span className="text-on-surface-variant shrink-0">{tipoLabel(p.tipo)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Fase = 'seleccionar' | 'previsualizando' | 'preview' | 'importando' | 'resumen' | 'error';

export function ImportarBancoModal({
  abierto,
  materiaId,
  onCerrar,
  onImportado,
}: ImportarBancoModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cerrarRef = useRef<HTMLButtonElement>(null);

  const [fase, setFase] = useState<Fase>('seleccionar');
  const [file, setFile] = useState<File | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [preview, setPreview] = useState<PreviewImportBancoResult | null>(null);
  const [resumen, setResumen] = useState<ImportarBancoXmlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showOmitidas, setShowOmitidas] = useState(false);
  const [showNuevas, setShowNuevas] = useState(false);
  const [showActualizadas, setShowActualizadas] = useState(false);
  const [excluidas, setExcluidas] = useState<Set<string>>(new Set());
  const [expandidas, setExpandidas] = useState<Set<string>>(new Set());

  const reset = useCallback(() => {
    setFase('seleccionar');
    setFile(null);
    setArrastrando(false);
    setPreview(null);
    setResumen(null);
    setError(null);
    setShowOmitidas(false);
    setShowNuevas(false);
    setShowActualizadas(false);
    setExcluidas(new Set());
    setExpandidas(new Set());
  }, []);

  function toggleExcluida(key: string) {
    setExcluidas((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleExpandida(key: string) {
    setExpandidas((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  useEffect(() => {
    if (!abierto) reset();
  }, [abierto, reset]);

  useEffect(() => {
    if (!abierto) return;
    cerrarRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && fase !== 'previsualizando' && fase !== 'importando') onCerrar();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [abierto, onCerrar, fase]);

  if (!abierto) return null;

  async function tomarArchivo(files: FileList | null) {
    const f = files?.[0];
    if (!f || !f.name.toLowerCase().endsWith('.xml')) return;
    setFile(f);
    setFase('previsualizando');
    setError(null);
    setExcluidas(new Set());
    try {
      const resultado = await previewImportarBancoXml(f);
      setPreview(resultado);
      setFase('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al leer el XML.');
      setFase('error');
    }
  }

  async function handleConfirmar() {
    if (!file) return;
    setFase('importando');
    setError(null);
    try {
      const rutasExcluidas = Array.from(excluidas).map((key) =>
        key === SIN_CATEGORIA_KEY ? [SIN_CATEGORIA_KEY] : key.split('/'),
      );
      const resultado = await importarBancoXml(materiaId, file, rutasExcluidas);
      setResumen(resultado);
      setFase('resumen');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al importar el XML.');
      setFase('error');
    }
  }

  function handleClose() {
    if (fase === 'resumen' && resumen) onImportado(resumen);
    else onCerrar();
  }

  const bloqueado = fase === 'previsualizando' || fase === 'importando';

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto p-4 bg-black/40"
      onClick={bloqueado ? undefined : handleClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="importar-banco-titulo"
        className="my-auto w-full max-w-lg rounded-2xl bg-white shadow-xl border border-outline-variant/40 max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-6 pt-6 pb-4 border-b border-outline-variant/30 shrink-0">
          <div>
            <h2 id="importar-banco-titulo" className="text-title-md font-semibold text-on-surface">
              Importar al banco de preguntas
            </h2>
            <p className="text-label-md text-on-surface-variant mt-0.5">
              {fase === 'seleccionar' && 'Subí el XML exportado del banco de preguntas de Moodle.'}
              {fase === 'previsualizando' && 'Leyendo el archivo…'}
              {fase === 'preview' && 'Revisá qué va a entrar antes de confirmar.'}
              {fase === 'importando' && 'Importando…'}
              {fase === 'resumen' && 'Importación completada.'}
              {fase === 'error' && 'Algo salió mal.'}
            </p>
          </div>
          <button
            ref={cerrarRef}
            type="button"
            onClick={handleClose}
            disabled={bloqueado}
            aria-label="Cerrar"
            className="p-1.5 rounded-lg hover:bg-surface-100 text-on-surface-variant shrink-0 disabled:opacity-40"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        <div className="px-6 py-5 overflow-y-auto flex-1">
          {fase === 'seleccionar' && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xml"
                className="sr-only"
                onChange={(e) => tomarArchivo(e.target.files)}
              />
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
                className={`flex w-full flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed px-4 py-8 text-center transition-colors ${
                  arrastrando
                    ? 'border-primary bg-primary/5'
                    : 'border-outline-variant hover:border-primary hover:bg-surface-50'
                }`}
              >
                <Icon name="upload_file" className="text-[28px] text-primary" />
                <span className="text-label-md font-medium text-primary">Seleccioná un archivo</span>
                <span className="text-label-sm text-on-surface-variant">
                  o arrastrá el XML de Moodle aquí
                </span>
              </button>
            </>
          )}

          {fase === 'previsualizando' && (
            <div className="flex flex-col items-center gap-3 py-10">
              <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <p className="text-label-md text-on-surface-variant">
                Analizando {file?.name}…
              </p>
            </div>
          )}

          {fase === 'preview' && preview && (
            <div className="space-y-4">
              <div className="rounded-lg bg-primary/5 px-3 py-2.5 text-label-md text-on-surface">
                <strong>
                  {preview.total_preguntas -
                    preview.categorias
                      .filter((c) => excluidas.has(c.ruta.join('/')))
                      .reduce((acc, c) => acc + totalTipos(c.preguntas_por_tipo), 0) -
                    (excluidas.has(SIN_CATEGORIA_KEY) ? totalTipos(preview.sin_categoria_por_tipo) : 0)}
                </strong>{' '}
                pregunta{preview.total_preguntas !== 1 ? 's' : ''} para importar
                {preview.omitidas.length > 0 && (
                  <> · <span className="text-error">{preview.omitidas.length} omitida{preview.omitidas.length !== 1 ? 's' : ''}</span></>
                )}
              </div>

              {preview.categorias.length > 0 && (
                <div className="rounded-lg border border-outline-variant/40 divide-y divide-outline-variant/20">
                  {preview.categorias.map((c) => {
                    const key = c.ruta.join('/');
                    const tildado = !excluidas.has(key);
                    const expandida = expandidas.has(key);
                    const breadcrumb = c.ruta.length > 1 ? c.ruta.slice(0, -1).join(' › ') : null;
                    return (
                      <div key={key}>
                        <div
                          className="flex items-center gap-2 px-3 py-2"
                          style={{ paddingLeft: `${12 + (c.ruta.length - 1) * 16}px` }}
                        >
                          <input
                            type="checkbox"
                            checked={tildado}
                            onChange={() => toggleExcluida(key)}
                            className="shrink-0 accent-primary cursor-pointer"
                          />
                          <Icon name="folder" className="text-[16px] text-on-surface-variant shrink-0" />
                          <button
                            type="button"
                            onClick={() => toggleExpandida(key)}
                            className={`flex-1 min-w-0 text-left ${tildado ? '' : 'opacity-50'}`}
                          >
                            {breadcrumb && (
                              <div className="text-label-sm text-on-surface-variant/70 truncate">
                                {breadcrumb}
                              </div>
                            )}
                            <div className="text-label-md text-on-surface truncate">
                              {c.ruta[c.ruta.length - 1]}
                            </div>
                            <div className="text-label-sm text-on-surface-variant">
                              {resumenTipos(c.preguntas_por_tipo)}
                            </div>
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleExpandida(key)}
                            aria-label={expandida ? 'Colapsar preguntas' : 'Ver preguntas'}
                            className="shrink-0 p-1 rounded hover:bg-surface-100 text-on-surface-variant"
                          >
                            <Icon name={expandida ? 'expand_less' : 'expand_more'} className="text-[18px]" />
                          </button>
                        </div>
                        {expandida && (
                          <ul className="max-h-40 overflow-y-auto bg-surface-50 px-3 py-2 space-y-1.5">
                            {c.preguntas.map((p, i) => (
                              <li key={i} className="flex items-center gap-2 text-label-sm">
                                <span className="text-on-surface truncate flex-1">{p.enunciado}</span>
                                <span className="text-on-surface-variant shrink-0">{tipoLabel(p.tipo)}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {Object.keys(preview.sin_categoria_por_tipo).length > 0 && (
                <div className="rounded-lg border border-outline-variant/40 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={!excluidas.has(SIN_CATEGORIA_KEY)}
                      onChange={() => toggleExcluida(SIN_CATEGORIA_KEY)}
                      className="shrink-0 accent-primary cursor-pointer"
                    />
                    <Icon name="folder_off" className="text-[16px] text-on-surface-variant shrink-0" />
                    <button
                      type="button"
                      onClick={() => toggleExpandida(SIN_CATEGORIA_KEY)}
                      className={`flex-1 min-w-0 text-left ${excluidas.has(SIN_CATEGORIA_KEY) ? 'opacity-50' : ''}`}
                    >
                      <div className="text-label-md text-on-surface">Sin clasificar</div>
                      <div className="text-label-sm text-on-surface-variant">
                        {resumenTipos(preview.sin_categoria_por_tipo)}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleExpandida(SIN_CATEGORIA_KEY)}
                      aria-label={expandidas.has(SIN_CATEGORIA_KEY) ? 'Colapsar preguntas' : 'Ver preguntas'}
                      className="shrink-0 p-1 rounded hover:bg-surface-100 text-on-surface-variant"
                    >
                      <Icon
                        name={expandidas.has(SIN_CATEGORIA_KEY) ? 'expand_less' : 'expand_more'}
                        className="text-[18px]"
                      />
                    </button>
                  </div>
                  {expandidas.has(SIN_CATEGORIA_KEY) && (
                    <ul className="max-h-40 overflow-y-auto bg-surface-50 px-3 py-2 space-y-1.5">
                      {preview.sin_categoria_preguntas.map((p, i) => (
                        <li key={i} className="flex items-center gap-2 text-label-sm">
                          <span className="text-on-surface truncate flex-1">{p.enunciado}</span>
                          <span className="text-on-surface-variant shrink-0">{tipoLabel(p.tipo)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {preview.omitidas.length > 0 && (
                <div className="rounded-lg border border-error-container/60">
                  <button
                    type="button"
                    onClick={() => setShowOmitidas((s) => !s)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-label-md font-medium text-error"
                  >
                    <Icon name={showOmitidas ? 'expand_less' : 'expand_more'} className="text-[18px]" />
                    {preview.omitidas.length} pregunta{preview.omitidas.length !== 1 ? 's' : ''} omitida{preview.omitidas.length !== 1 ? 's' : ''}
                  </button>
                  {showOmitidas && (
                    <ul className="max-h-40 overflow-y-auto border-t border-error-container/60 px-3 py-2 space-y-1">
                      {preview.omitidas.map((o, i) => (
                        <li key={i} className="text-label-sm text-on-surface-variant">
                          <span className="font-medium text-on-surface">{o.nombre}</span>
                          {' — '}
                          {o.motivo === 'tipo no soportado'
                            ? `tipo no soportado (${tipoLabel(o.tipo)})`
                            : o.motivo}
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="px-3 py-2 border-t border-error-container/60 text-label-sm text-on-surface-variant">
                    Se importan: {TIPOS_SOPORTADOS.join(', ')}. El resto de los tipos de Moodle
                    (emparejamiento, ensayo, numérica, respuesta corta…) se omite.
                  </p>
                </div>
              )}
            </div>
          )}

          {fase === 'importando' && (
            <div className="flex flex-col items-center gap-3 py-10">
              <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <p className="text-label-md text-on-surface-variant">Importando al banco…</p>
            </div>
          )}

          {fase === 'resumen' && resumen && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Icon name="check_circle" className="text-[24px] text-success" fill />
                <p className="text-label-md font-medium text-on-surface">
                  {resumen.preguntas_nuevas + resumen.preguntas_actualizadas > 0
                    ? 'Importación completada'
                    : 'Nada nuevo para importar'}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-success-container px-3 py-2 text-center">
                  <div className="text-title-sm font-bold text-success">{resumen.preguntas_nuevas}</div>
                  <div className="text-label-sm text-success">Nuevas</div>
                </div>
                <div className="rounded-lg bg-surface-100 px-3 py-2 text-center">
                  <div className="text-title-sm font-bold text-on-surface">{resumen.preguntas_actualizadas}</div>
                  <div className="text-label-sm text-on-surface-variant">Actualizadas</div>
                </div>
                <div className="rounded-lg bg-error-container/40 px-3 py-2 text-center">
                  <div className="text-title-sm font-bold text-error">{resumen.omitidas.length}</div>
                  <div className="text-label-sm text-error">Omitidas</div>
                </div>
              </div>

              <ListaPreguntasDesplegable
                titulo="Nuevas"
                items={resumen.nuevas}
                abierto={showNuevas}
                onToggle={() => setShowNuevas((s) => !s)}
              />
              <ListaPreguntasDesplegable
                titulo="Actualizadas"
                items={resumen.actualizadas}
                abierto={showActualizadas}
                onToggle={() => setShowActualizadas((s) => !s)}
              />

              {resumen.omitidas.length > 0 && (
                <div className="rounded-lg border border-error-container/60">
                  <button
                    type="button"
                    onClick={() => setShowOmitidas((s) => !s)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-label-md font-medium text-error"
                  >
                    <Icon name={showOmitidas ? 'expand_less' : 'expand_more'} className="text-[18px]" />
                    Omitidas ({resumen.omitidas.length})
                  </button>
                  {showOmitidas && (
                    <ul className="max-h-40 overflow-y-auto border-t border-error-container/60 px-3 py-2 space-y-1">
                      {resumen.omitidas.map((o, i) => (
                        <li key={i} className="text-label-sm text-on-surface-variant">
                          <span className="font-medium text-on-surface">{o.nombre}</span>: {o.motivo}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {fase === 'error' && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <Icon name="error" className="text-[40px] text-error" fill />
              <p className="font-medium text-on-surface">No se pudo importar</p>
              <p className="text-label-md text-on-surface-variant">{error}</p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-outline-variant/30 shrink-0">
          {fase === 'preview' && (
            <>
              <Button variant="ghost" onClick={reset}>Elegir otro archivo</Button>
              <Button variant="primary" onClick={handleConfirmar}>
                Confirmar importación
              </Button>
            </>
          )}
          {(fase === 'seleccionar' || fase === 'error') && (
            <Button variant="ghost" onClick={onCerrar}>Cancelar</Button>
          )}
          {fase === 'resumen' && (
            <Button variant="primary" onClick={handleClose}>Cerrar</Button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default ImportarBancoModal;
