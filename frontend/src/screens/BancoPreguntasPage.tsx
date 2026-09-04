import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Card, Icon, LoadingSpinner } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { api } from '../lib/api';
import { useToast } from '../ui/toast';
import type { Materia } from '../lib/types';
import type {
  CategoriaPregunta,
  EstadoPregunta,
  PreguntaBanco,
  UsoDeCategoria,
} from '../lib/apiAdmin/bancoPreguntasApi';
import {
  listarCategorias,
  crearCategoria,
  renombrarCategoria,
  borrarCategoria,
  reactivarCategoria,
  listarPreguntasBanco,
  moverPreguntaCategoria,
  moverCategoria,
  darDeBajaPregunta,
  reactivarPregunta,
  usoDeCategoria,
} from '../lib/apiAdmin/bancoPreguntasApi';
import { CategoriasTree, serializarDnd } from './banco-preguntas/CategoriasTree';
import { PreviewPreguntaModal } from './banco-preguntas/PreviewPreguntaModal';
import { limpiarEnunciadoCloze } from '../lib/cloze';
import { ModalOverlay } from '../ui/ModalOverlay';
import { HelpButton } from '../ui/HelpButton';
import { AvisoUsoCategoria } from '../ui/AvisoUsoCategoria';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { ImportarBancoModal } from './banco-preguntas/ImportarBancoModal';
import type { ImportarBancoXmlResult } from '../lib/apiAdmin/bancoPreguntasApi';

// ---------------------------------------------------------------------------
// Diálogo inline (crear / renombrar categoría)
// ---------------------------------------------------------------------------

function DialogoCategoria({
  titulo,
  valorInicial,
  placeholder = 'Nombre de la categoría',
  aviso,
  onConfirmar,
  onCancelar,
}: {
  titulo: string;
  valorInicial: string;
  placeholder?: string;
  /** Aviso de uso (al renombrar). Informa, nunca deshabilita el botón. */
  aviso?: ReactNode;
  onConfirmar: (nombre: string) => void;
  onCancelar: () => void;
}) {
  const [nombre, setNombre] = useState(valorInicial);
  return (
    <ModalOverlay etiqueta={titulo} onCerrar={onCancelar}>
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm flex flex-col gap-4">
        <h3 className="text-title-md font-semibold">{titulo}</h3>
        {aviso}
        <input
          className="border rounded-lg px-3 py-2 text-body-md w-full focus:outline-none focus:ring-2 focus:ring-primary"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && nombre.trim() && onConfirmar(nombre.trim())}
          autoFocus
          placeholder={placeholder}
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancelar}>Cancelar</Button>
          <Button
            variant="primary"
            onClick={() => nombre.trim() && onConfirmar(nombre.trim())}
            disabled={!nombre.trim()}
          >
            Confirmar
          </Button>
        </div>
      </div>
    </ModalOverlay>
  );
}

// ---------------------------------------------------------------------------
// Diálogo de confirmación para borrar
// ---------------------------------------------------------------------------

function DialogoBorrar({
  categoria,
  aviso,
  onConfirmar,
  onCancelar,
}: {
  categoria: CategoriaPregunta;
  /** Aviso de uso. Se muestra ANTES de confirmar y NO bloquea la baja: la baja
   *  no cambia notas ni saca preguntas de un examen ya armado. */
  aviso?: ReactNode;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  return (
    <ModalOverlay etiqueta={`Dar de baja ${categoria.nombre}`} onCerrar={onCancelar}>
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm flex flex-col gap-4">
        {/* El texto viejo describía el borrado FÍSICO que hacía antes: "las
            preguntas quedarán sin clasificar, las subcategorías se borrarán en
            cascada". Eso ya no pasa: la baja es lógica, las preguntas conservan
            su categoría y todo se recupera. */}
        <h3 className="text-title-md font-semibold">Dar de baja la categoría</h3>
        <p className="text-body-md text-on-surface-variant">
          <strong>{categoria.nombre}</strong> y sus subcategorías salen del árbol del
          banco y dejan de ofrecerse para armar exámenes.
        </p>
        <p className="text-body-md text-on-surface-variant">
          No se borra nada: las preguntas siguen guardadas con su categoría, y podés
          devolverla cuando quieras desde «Categorías dadas de baja».
        </p>
        {aviso}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancelar}>Cancelar</Button>
          <Button variant="danger" onClick={onConfirmar}>
            Dar de baja
          </Button>
        </div>
      </div>
    </ModalOverlay>
  );
}

// ---------------------------------------------------------------------------
// Lista de preguntas del bucket seleccionado
// ---------------------------------------------------------------------------

function ListaPreguntas({
  preguntas,
  categorias,
  categoriaActualId,
  cargando,
  pageSize,
  onMover,
  onDarDeBaja,
  onReactivar,
}: {
  preguntas: PreguntaBanco[];
  categorias: CategoriaPregunta[];
  categoriaActualId: string | null;
  cargando: boolean;
  pageSize: number;
  onMover: (preguntaId: string, nuevaCatId: string | null) => void;
  onDarDeBaja: (pregunta: PreguntaBanco) => void;
  onReactivar: (preguntaId: string) => void;
}) {
  const [moviendoId, setMoviendoId] = useState<string | null>(null);
  // c-78 E-08 (15.3): pregunta abierta en la vista previa. null = modal cerrado.
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [pagina, setPagina] = useState(1);

  // Volver a la página 1 al cambiar cuántas preguntas se ven por página.
  useEffect(() => setPagina(1), [pageSize]);

  const totalPaginas = Math.max(1, Math.ceil(preguntas.length / pageSize));
  const paginaActual = Math.min(pagina, totalPaginas);
  const preguntasPagina = preguntas.slice((paginaActual - 1) * pageSize, paginaActual * pageSize);

  if (cargando) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="md" label="Cargando preguntas…" />
      </div>
    );
  }

  if (preguntas.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-on-surface-variant gap-2">
        <Icon name="inbox" className="text-[40px]" />
        <p className="text-body-md">No hay preguntas en esta categoría.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        {preguntasPagina.map((p) => {
          // Preview sin exponer la respuesta correcta: los campos cloze {..} → "____".
          const preview = limpiarEnunciadoCloze(p.enunciado) || '(sin enunciado)';
          return (
          <div
            key={p.id}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/x-banco', serializarDnd({ kind: 'question', id: p.id }));
              e.dataTransfer.effectAllowed = 'move';
            }}
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-surface-200 bg-white hover:bg-surface-50 hover:border-surface-300 transition-all duration-200 shadow-xs cursor-grab active:cursor-grabbing"
          >
            <div className="w-7 h-7 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center shrink-0">
              <Icon
                name={p.tipo === 'truefalse' ? 'toggle_on' : p.tipo === 'cloze' ? 'text_fields' : 'quiz'}
                className="text-[15px]"
              />
            </div>
            <div className="flex-1 min-w-0">
              <p
                className="text-label-md truncate"
                title={preview}
              >
                {preview}
              </p>
              <p className="text-label-sm text-on-surface-variant flex items-center gap-1.5">
                <span>{p.tipo}</span>
                {p.categoria_manual && (
                  <span
                    className="inline-flex items-center gap-0.5 text-primary"
                    title="La moviste vos. Ni el import de XML ni el sync desde Moodle la vuelven a cambiar de categoría."
                  >
                    <Icon name="push_pin" className="text-[13px]" fill />
                    Fijada por vos
                  </span>
                )}
              </p>
            </div>
            {moviendoId === p.id ? (
              <div className="flex items-center gap-2">
                <select
                  className="text-label-md border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary"
                  defaultValue={categoriaActualId ?? ''}
                  onChange={async (e) => {
                    const val = e.target.value || null;
                    await onMover(p.id, val);
                    setMoviendoId(null);
                  }}
                >
                  <option value="">Sin clasificar</option>
                  {categorias.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
                <button
                  className="p-1 rounded hover:bg-surface-200"
                  onClick={() => setMoviendoId(null)}
                >
                  <Icon name="close" className="text-[16px]" />
                </button>
              </div>
            ) : (
              <>
                {/* c-78 E-08 (15.3): ver la pregunta como la ve el alumno. Antes,
                    la única forma de saber si quedó bien importada era tomar el
                    examen. */}
                <button
                  className="p-1.5 rounded-lg hover:bg-surface-200 text-on-surface-variant"
                  title="Ver como la ve el alumno"
                  onClick={() => setPreviewId(p.id)}
                >
                  <Icon name="visibility" className="text-[16px]" />
                </button>
                <button
                  className="p-1.5 rounded-lg hover:bg-surface-200 text-on-surface-variant"
                  title="Mover a categoría"
                  onClick={() => setMoviendoId(p.id)}
                >
                  <Icon name="drive_file_move" className="text-[16px]" />
                </button>
                {/* Baja LÓGICA: la pregunta sale del banco y de los exámenes que
                    se armen de ahora en más, pero no se borra y se puede
                    reactivar. El backend rechaza la baja si la pregunta está en
                    un examen vigente, donde se seguiría sorteando. */}
                {p.eliminada_en ? (
                  <button
                    className="p-1.5 rounded-lg hover:bg-success-container text-success"
                    title="Devolver esta pregunta al banco"
                    onClick={() => onReactivar(p.id)}
                  >
                    <Icon name="restore_from_trash" className="text-[16px]" />
                  </button>
                ) : (
                  <button
                    className="p-1.5 rounded-lg hover:bg-error-container/40 text-on-surface-variant hover:text-error"
                    title="Dar de baja esta pregunta"
                    onClick={() => onDarDeBaja(p)}
                  >
                    <Icon name="delete_outline" className="text-[16px]" />
                  </button>
                )}
              </>
            )}
          </div>
          );
        })}
      </div>

      {/* Paginación */}
      {preguntas.length > 0 && (
        <Pagination
          currentPage={paginaActual}
          totalPages={totalPaginas}
          totalElements={preguntas.length}
          pageSize={pageSize}
          onPageChange={setPagina}
          className="!px-3 !py-2 text-label-sm"
        />
      )}

      <PreviewPreguntaModal
        preguntaId={previewId}
        onCerrar={() => setPreviewId(null)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pantalla principal
// ---------------------------------------------------------------------------

export default function BancoPreguntasPage() {
  const toast = useToast();

  const [materias, setMaterias] = useState<Materia[]>([]);
  const [materiaId, setMateriaId] = useState<string>('');

  const [categorias, setCategorias] = useState<CategoriaPregunta[]>([]);
  const [cargandoCats, setCargandoCats] = useState(false);

  const [catSeleccionada, setCatSeleccionada] = useState<string | null>(null);
  const [preguntas, setPreguntas] = useState<PreguntaBanco[]>([]);
  const [cargandoPregs, setCargandoPregs] = useState(false);
  const [sinClasificarCount, setSinClasificarCount] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  // Filtro de baja lógica. Default 'activa': el banco es lo que se puede usar.
  // Sin este filtro, dar de baja sería indistinguible de borrar y no habría
  // forma de recuperar una pregunta.
  const [estadoPreguntas, setEstadoPreguntas] = useState<EstadoPregunta>('activa');

  // Diálogos
  const [dialogoCrear, setDialogoCrear] = useState<{ padreId: string | null } | null>(null);
  const [dialogoRenombrar, setDialogoRenombrar] = useState<CategoriaPregunta | null>(null);
  const [dialogoBorrar, setDialogoBorrar] = useState<CategoriaPregunta | null>(null);
  // Categorías dadas de baja de esta materia. Se listan aparte del árbol: sirven
  // para recuperarlas, no para clasificar preguntas nuevas.
  const [categoriasDeBaja, setCategoriasDeBaja] = useState<CategoriaPregunta[]>([]);
  const [dialogoImportar, setDialogoImportar] = useState(false);

  // Uso de la categoría del diálogo abierto (renombrar o dar de baja). Se
  // consulta al ABRIR el diálogo: el aviso tiene que estar delante del docente
  // antes de que confirme, no después. Nunca bloquea nada.
  const [uso, setUso] = useState<UsoDeCategoria | null>(null);
  const [usoCargando, setUsoCargando] = useState(false);
  const [usoError, setUsoError] = useState<string | null>(null);
  const categoriaEnDialogo = dialogoRenombrar?.id ?? dialogoBorrar?.id ?? null;

  useEffect(() => {
    if (!categoriaEnDialogo) {
      setUso(null);
      setUsoError(null);
      return;
    }
    let vigente = true;
    setUso(null);
    setUsoError(null);
    setUsoCargando(true);
    usoDeCategoria(categoriaEnDialogo)
      .then((u) => { if (vigente) setUso(u); })
      // No se calla: un aviso perdido en silencio hace que el docente confirme
      // creyendo que la categoría no la usa ningún examen.
      .catch(() => { if (vigente) setUsoError('no se pudo consultar'); })
      .finally(() => { if (vigente) setUsoCargando(false); });
    return () => { vigente = false; };
  }, [categoriaEnDialogo]);

  useEffect(() => {
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, []);

  const cargarCategorias = useCallback(async (mid: string) => {
    setCargandoCats(true);
    try {
      // El árbol muestra las categorías vigentes; el contador de la papelera se
      // pide aparte para poder avisar que hay categorías dadas de baja sin
      // ensuciar el árbol con ellas.
      const [cats, sinClasificar, deBaja] = await Promise.all([
        listarCategorias(mid),
        listarPreguntasBanco(mid, null),
        listarCategorias(mid, 'eliminada').catch(() => []),
      ]);
      setCategorias(cats);
      setCategoriasDeBaja(deBaja);
      setSinClasificarCount(sinClasificar.length);
      // Sin nada sin clasificar, el bucket queda oculto (CategoriasTree) — no
      // tiene sentido dejar la selección apuntando a un bucket invisible.
      setCatSeleccionada((prev) => {
        if (prev !== null) return prev;
        return sinClasificar.length > 0 ? null : (cats[0]?.id ?? null);
      });
    } catch {
      toast.error('No se pudieron cargar las categorías.');
    } finally {
      setCargandoCats(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!materiaId) { setCategorias([]); setCatSeleccionada(null); setPreguntas([]); return; }
    setCatSeleccionada(null);
    setPreguntas([]);
    cargarCategorias(materiaId);
  }, [materiaId, cargarCategorias]);

  const cargarPreguntas = useCallback(
    async (mid: string, catId: string | null, est: EstadoPregunta) => {
      setCargandoPregs(true);
      try {
        const preg = await listarPreguntasBanco(mid, catId, est);
        setPreguntas(preg);
      } catch {
        toast.error('No se pudieron cargar las preguntas.');
      } finally {
        setCargandoPregs(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    if (!materiaId) return;
    cargarPreguntas(materiaId, catSeleccionada, estadoPreguntas);
  }, [materiaId, catSeleccionada, estadoPreguntas, cargarPreguntas]);

  // Baja LÓGICA de una pregunta. El backend responde 409 si está en el pool de un
  // examen vigente: ahí se seguiría sorteando, así que el mensaje que trae dice en
  // cuáles está y se muestra tal cual en vez de un "no se pudo" genérico.
  async function handleDarDeBaja(pregunta: PreguntaBanco) {
    const texto = limpiarEnunciadoCloze(pregunta.enunciado).slice(0, 60);
    if (
      !window.confirm(
        `¿Dar de baja esta pregunta?\n\n"${texto}…"\n\nSale del banco y de los ` +
          'exámenes que armes de ahora en más. No se borra: la podés reactivar ' +
          'desde el filtro "Dadas de baja".',
      )
    ) {
      return;
    }
    try {
      await darDeBajaPregunta(pregunta.id);
      toast.success('Pregunta dada de baja. La podés reactivar cuando quieras.');
      await cargarPreguntas(materiaId, catSeleccionada, estadoPreguntas);
      await cargarCategorias(materiaId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'No se pudo dar de baja.');
    }
  }

  async function handleReactivarPregunta(preguntaId: string) {
    try {
      await reactivarPregunta(preguntaId);
      toast.success('Pregunta devuelta al banco.');
      await cargarPreguntas(materiaId, catSeleccionada, estadoPreguntas);
      await cargarCategorias(materiaId);
    } catch {
      toast.error('No se pudo reactivar la pregunta.');
    }
  }

  async function handleCrear(nombre: string) {
    if (!materiaId) return;
    try {
      await crearCategoria({ materia_id: materiaId, nombre, categoria_padre_id: dialogoCrear?.padreId ?? null });
      toast.success('Categoría creada.');
      await cargarCategorias(materiaId);
    } catch {
      toast.error('Error al crear la categoría.');
    } finally {
      setDialogoCrear(null);
    }
  }

  async function handleRenombrar(nombre: string) {
    if (!dialogoRenombrar) return;
    try {
      await renombrarCategoria(dialogoRenombrar.id, nombre);
      toast.success('Categoría renombrada.');
      await cargarCategorias(materiaId);
    } catch {
      toast.error('Error al renombrar la categoría.');
    } finally {
      setDialogoRenombrar(null);
    }
  }

  async function handleBorrar() {
    if (!dialogoBorrar) return;
    try {
      await borrarCategoria(dialogoBorrar.id);
      toast.success('Categoría dada de baja. La podés devolver cuando quieras.');
      if (catSeleccionada === dialogoBorrar.id) setCatSeleccionada(null);
      await cargarCategorias(materiaId);
    } catch {
      toast.error('No se pudo dar de baja la categoría.');
    } finally {
      setDialogoBorrar(null);
    }
  }

  async function handleReactivarCategoria(categoriaId: string) {
    try {
      await reactivarCategoria(categoriaId);
      toast.success('Categoría devuelta al banco, con sus subcategorías.');
      await cargarCategorias(materiaId);
    } catch {
      toast.error('No se pudo reactivar la categoría.');
    }
  }

  function handleImportado(resultado: ImportarBancoXmlResult) {
    setDialogoImportar(false);
    const { preguntas_nuevas, preguntas_actualizadas, omitidas } = resultado;
    const partes = [
      preguntas_nuevas > 0 ? `${preguntas_nuevas} nueva${preguntas_nuevas !== 1 ? 's' : ''}` : null,
      preguntas_actualizadas > 0 ? `${preguntas_actualizadas} actualizada${preguntas_actualizadas !== 1 ? 's' : ''}` : null,
    ].filter(Boolean);
    toast.success(partes.length > 0 ? `Importado: ${partes.join(', ')}.` : 'Nada nuevo para importar.');
    if (omitidas.length > 0) {
      toast.error(`${omitidas.length} pregunta${omitidas.length !== 1 ? 's' : ''} omitida${omitidas.length !== 1 ? 's' : ''} (tipo no soportado o inválida).`);
    }
    if (materiaId) {
      cargarCategorias(materiaId);
      cargarPreguntas(materiaId, catSeleccionada, estadoPreguntas);
    }
  }

  async function handleMoverPregunta(preguntaId: string, nuevaCatId: string | null) {
    try {
      await moverPreguntaCategoria(preguntaId, nuevaCatId);
      toast.success('Pregunta movida.');
      await cargarPreguntas(materiaId, catSeleccionada, estadoPreguntas);
    } catch {
      toast.error('Error al mover la pregunta.');
    }
  }

  async function handleMoverCategoria(categoriaId: string, nuevoPadreId: string | null) {
    try {
      await moverCategoria(categoriaId, nuevoPadreId);
      toast.success(nuevoPadreId ? 'Categoría anidada.' : 'Categoría movida a raíz.');
      await cargarCategorias(materiaId);
    } catch (e) {
      // El backend explica el motivo (ciclo / materia distinta) en el mensaje.
      toast.error(e instanceof Error ? e.message : 'Error al mover la categoría.');
    }
  }

  const tituloCategoria = catSeleccionada === null
    ? 'Sin clasificar'
    : (categorias.find((c) => c.id === catSeleccionada)?.nombre ?? '');

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Banco de preguntas"
      subtitle="Organizá las preguntas por categorías para armar exámenes por sorteo."
      help={
        <HelpButton title="Banco de preguntas">
          <p>
            Acá organizás las preguntas de una materia en <strong>categorías</strong> (como
            carpetas): por tema, por unidad, por dificultad… lo que te sirva.
          </p>
          <p>
            Las preguntas se traen <strong>importando el XML</strong> que exportás del banco
            de preguntas de Moodle. Ese archivo ya trae las categorías incluidas: al
            importarlo, la organización queda igual que en Moodle, y después la podés
            reorganizar a mano.
          </p>
          <p>
            Después, al crear un examen podés <strong>armarlo por sorteo</strong>: elegís de
            qué categorías salen las preguntas y cuántas de cada una.
          </p>
        </HelpButton>
      }
    >
      <div className="flex flex-col gap-6">
        {/* Materia + árbol de categorías, en la misma card */}
        <Card className="!p-md">
          <div className="flex items-end justify-between gap-3 mb-3">
            <label className="flex-1 max-w-sm">
              <span className="text-label-md font-medium block mb-2">Materia</span>
              <select
                className="border rounded-xl px-3 py-2 text-body-md w-full focus:outline-none focus:ring-2 focus:ring-primary"
                value={materiaId}
                onChange={(e) => setMateriaId(e.target.value)}
              >
                <option value="">Seleccionar materia</option>
                {materias.map((m) => (
                  <option key={m.id} value={m.id}>{m.nombre}</option>
                ))}
              </select>
            </label>
            <Button
              variant="outline"
              icon="upload_file"
              disabled={!materiaId}
              onClick={() => setDialogoImportar(true)}
            >
              Importar XML
            </Button>
          </div>

          {materiaId && (
            <div className="pt-3 border-t border-outline-variant/30">
              <p className="text-label-md font-medium mb-3">Categorías</p>
              {cargandoCats ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="sm" label="Cargando…" />
                </div>
              ) : (
                <CategoriasTree
                  categorias={categorias}
                  seleccionada={catSeleccionada}
                  sinClasificarCount={sinClasificarCount}
                  onSeleccionar={setCatSeleccionada}
                  onCrear={(padreId) => setDialogoCrear({ padreId })}
                  onRenombrar={setDialogoRenombrar}
                  onBorrar={setDialogoBorrar}
                  onMoverCategoria={handleMoverCategoria}
                  onMoverPregunta={handleMoverPregunta}
                />
              )}

              {/* La papelera de categorías. Va fuera del árbol a propósito: son
                  categorías que ya no clasifican nada nuevo, y mezclarlas arriba
                  volvería a ensuciar justamente lo que la baja vino a ordenar.
                  Sin esta lista, dar de baja sería indistinguible de borrar. */}
              {categoriasDeBaja.length > 0 && (
                <details className="mt-3 rounded-lg border border-outline-variant/40">
                  <summary className="cursor-pointer px-3 py-2 text-label-sm text-on-surface-variant">
                    <Icon name="delete_outline" className="text-[15px] align-middle mr-1" />
                    {categoriasDeBaja.length}{' '}
                    {categoriasDeBaja.length === 1
                      ? 'categoría dada de baja'
                      : 'categorías dadas de baja'}
                  </summary>
                  <ul className="px-3 pb-2 space-y-1">
                    {categoriasDeBaja.map((c) => (
                      <li
                        key={c.id}
                        className="flex items-center justify-between gap-2 text-label-sm"
                      >
                        <span className="truncate text-on-surface-variant">{c.nombre}</span>
                        <button
                          type="button"
                          className="shrink-0 p-1 rounded hover:bg-success-container text-success"
                          title="Devolver esta categoría al banco"
                          onClick={() => void handleReactivarCategoria(c.id)}
                        >
                          <Icon name="restore_from_trash" className="text-[16px]" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </Card>

        {materiaId && (
          <div className="flex flex-col gap-4">
            {/* Preguntas de la categoría seleccionada */}
            <Card className="!p-md">
              <div className="flex items-center justify-between mb-3">
                <p className="text-label-md font-medium">
                  {tituloCategoria}
                  <span className="ml-2 text-on-surface-variant font-normal">
                    ({preguntas.length} pregunta{preguntas.length !== 1 ? 's' : ''})
                  </span>
                </p>
                <div className="flex items-center gap-3">
                  {/* La papelera del banco. Sin esto, dar de baja una pregunta
                      sería indistinguible de borrarla. */}
                  <select
                    aria-label="Filtrar preguntas por estado"
                    value={estadoPreguntas}
                    onChange={(e) => setEstadoPreguntas(e.target.value as EstadoPregunta)}
                    className="text-label-md border border-outline-variant rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="activa">En el banco</option>
                    <option value="eliminada">Dadas de baja</option>
                    <option value="todas">Todas</option>
                  </select>
                  {preguntas.length > 0 && (
                    <PageSizeSelect value={pageSize} onChange={setPageSize} />
                  )}
                </div>
              </div>
              {estadoPreguntas === 'eliminada' && (
                <p className="mb-3 text-label-sm text-on-surface-variant flex items-start gap-1.5">
                  <Icon name="info" className="text-[15px] shrink-0 mt-0.5" />
                  Estas preguntas no se usan para armar exámenes. Nada se borró: se
                  pueden devolver al banco cuando quieras.
                </p>
              )}
              <ListaPreguntas
                key={catSeleccionada ?? '__sin_clasificar__'}
                preguntas={preguntas}
                categorias={categorias}
                categoriaActualId={catSeleccionada}
                cargando={cargandoPregs}
                pageSize={pageSize}
                onMover={handleMoverPregunta}
                onDarDeBaja={handleDarDeBaja}
                onReactivar={handleReactivarPregunta}
              />
            </Card>
          </div>
        )}

        {!materiaId && (
          <div className="flex flex-col items-center justify-center py-20 text-on-surface-variant gap-3">
            <Icon name="category" className="text-[48px]" />
            <p className="text-body-lg">Seleccioná una materia para ver su banco de preguntas.</p>
          </div>
        )}
      </div>

      {/* Diálogos */}
      {dialogoCrear && (
        <DialogoCategoria
          titulo={
            dialogoCrear.padreId
              ? `Nueva subcategoría en "${categorias.find((c) => c.id === dialogoCrear.padreId)?.nombre ?? ''}"`
              : 'Nueva categoría raíz'
          }
          valorInicial=""
          placeholder={dialogoCrear.padreId ? 'Nombre de la subcategoría' : 'Nombre de la categoría'}
          onConfirmar={handleCrear}
          onCancelar={() => setDialogoCrear(null)}
        />
      )}
      {dialogoRenombrar && (
        <DialogoCategoria
          titulo="Renombrar categoría"
          valorInicial={dialogoRenombrar.nombre}
          aviso={
            <AvisoUsoCategoria uso={uso} cargando={usoCargando} error={usoError} />
          }
          onConfirmar={handleRenombrar}
          onCancelar={() => setDialogoRenombrar(null)}
        />
      )}
      {dialogoBorrar && (
        <DialogoBorrar
          categoria={dialogoBorrar}
          aviso={
            <AvisoUsoCategoria uso={uso} cargando={usoCargando} error={usoError} />
          }
          onConfirmar={handleBorrar}
          onCancelar={() => setDialogoBorrar(null)}
        />
      )}
      {materiaId && (
        <ImportarBancoModal
          abierto={dialogoImportar}
          materiaId={materiaId}
          onCerrar={() => setDialogoImportar(false)}
          onImportado={handleImportado}
        />
      )}
    </StaffShell>
  );
}
