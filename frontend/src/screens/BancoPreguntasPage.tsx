import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Card, Icon, LoadingSpinner } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { api } from '../lib/api';
import { useToast } from '../ui/toast';
import type { Materia } from '../lib/types';
import type { CategoriaPregunta, PreguntaBanco } from '../lib/apiAdmin/bancoPreguntasApi';
import {
  listarCategorias,
  crearCategoria,
  renombrarCategoria,
  borrarCategoria,
  listarPreguntasBanco,
  moverPreguntaCategoria,
  sincronizarBancoMoodle,
  type SyncBancoResult,
} from '../lib/apiAdmin/bancoPreguntasApi';
import { CategoriasTree } from './banco-preguntas/CategoriasTree';

// ---------------------------------------------------------------------------
// Diálogo inline (crear / renombrar categoría)
// ---------------------------------------------------------------------------

function DialogoCategoria({
  titulo,
  valorInicial,
  onConfirmar,
  onCancelar,
}: {
  titulo: string;
  valorInicial: string;
  onConfirmar: (nombre: string) => void;
  onCancelar: () => void;
}) {
  const [nombre, setNombre] = useState(valorInicial);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-surface rounded-2xl shadow-xl p-6 w-full max-w-sm flex flex-col gap-4">
        <h3 className="text-title-md font-semibold">{titulo}</h3>
        <input
          className="border rounded-lg px-3 py-2 text-body-md w-full focus:outline-none focus:ring-2 focus:ring-primary"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && nombre.trim() && onConfirmar(nombre.trim())}
          autoFocus
          placeholder="Nombre de la categoría"
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diálogo de confirmación para borrar
// ---------------------------------------------------------------------------

function DialogoBorrar({
  categoria,
  onConfirmar,
  onCancelar,
}: {
  categoria: CategoriaPregunta;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-surface rounded-2xl shadow-xl p-6 w-full max-w-sm flex flex-col gap-4">
        <h3 className="text-title-md font-semibold">Borrar categoría</h3>
        <p className="text-body-md text-on-surface-variant">
          ¿Borrar <strong>{categoria.nombre}</strong>? Las preguntas asociadas quedarán sin
          clasificar. Las subcategorías se borrarán en cascada.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancelar}>Cancelar</Button>
          <Button variant="danger" onClick={onConfirmar}>
            Borrar
          </Button>
        </div>
      </div>
    </div>
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
  onMover,
}: {
  preguntas: PreguntaBanco[];
  categorias: CategoriaPregunta[];
  categoriaActualId: string | null;
  cargando: boolean;
  onMover: (preguntaId: string, nuevaCatId: string | null) => void;
}) {
  const [moviendoId, setMoviendoId] = useState<string | null>(null);

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
    <div className="flex flex-col gap-2">
      {preguntas.map((p) => (
        <div
          key={p.id}
          className="flex items-start gap-3 p-3 rounded-xl border border-outline-variant bg-surface hover:bg-surface-100 transition-colors"
        >
          <div className="mt-0.5 w-8 h-8 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center shrink-0">
            <Icon
              name={p.tipo === 'truefalse' ? 'toggle_on' : 'quiz'}
              className="text-[16px]"
            />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-body-sm line-clamp-2">{p.enunciado || '(sin enunciado)'}</p>
            <p className="text-label-sm text-on-surface-variant mt-0.5">{p.tipo}</p>
          </div>
          {/* Selector de mover a categoría */}
          {moviendoId === p.id ? (
            <div className="flex items-center gap-2">
              <select
                className="text-body-sm border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary"
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
            <button
              className="p-1.5 rounded-lg hover:bg-surface-200 text-on-surface-variant"
              title="Mover a categoría"
              onClick={() => setMoviendoId(p.id)}
            >
              <Icon name="drive_file_move" className="text-[16px]" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diálogo de sincronización desde Moodle
// ---------------------------------------------------------------------------

function DialogoSyncMoodle({
  materiaId,
  onCerrar,
  onSincronizado,
}: {
  materiaId: string;
  onCerrar: () => void;
  onSincronizado: () => void;
}) {
  const [courseid, setCourseid] = useState('');
  const [sincronizando, setSincronizando] = useState(false);
  const [resultado, setResultado] = useState<SyncBancoResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSincronizar() {
    const id = parseInt(courseid.trim(), 10);
    if (isNaN(id) || id <= 0) { setError('Ingresá un ID de curso válido.'); return; }
    setSincronizando(true);
    setError(null);
    setResultado(null);
    try {
      const res = await sincronizarBancoMoodle(materiaId, id);
      setResultado(res);
      onSincronizado();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al sincronizar.');
    } finally {
      setSincronizando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-surface rounded-2xl shadow-xl p-6 w-full max-w-sm flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Icon name="sync" className="text-[22px] text-primary" />
          <h3 className="text-title-md font-semibold">Sincronizar desde campus</h3>
        </div>

        {resultado ? (
          <div className="flex flex-col gap-3">
            <div className="bg-success-container rounded-xl px-4 py-3 flex flex-col gap-1 text-label-md text-success">
              <div className="flex items-center gap-2 font-semibold">
                <Icon name="check_circle" className="text-[18px]" fill />
                Sincronización completada
              </div>
              <ul className="mt-1 space-y-0.5 text-on-surface text-label-sm">
                <li>Categorías creadas: <strong>{resultado.categorias_creadas}</strong></li>
                <li>Preguntas nuevas: <strong>{resultado.preguntas_nuevas}</strong></li>
                <li>Preguntas actualizadas: <strong>{resultado.preguntas_actualizadas}</strong></li>
              </ul>
            </div>
            <div className="flex justify-end">
              <Button variant="primary" onClick={onCerrar}>Cerrar</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              <label className="text-label-md font-medium">ID del curso en Moodle</label>
              <input
                type="number"
                min={1}
                className="border rounded-lg px-3 py-2 text-body-md w-full focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Ej: 42"
                value={courseid}
                onChange={(e) => { setCourseid(e.target.value); setError(null); }}
                onKeyDown={(e) => e.key === 'Enter' && !sincronizando && handleSincronizar()}
                autoFocus
                disabled={sincronizando}
              />
              <p className="text-label-sm text-on-surface-variant">
                Podés encontrar el ID en la URL del curso de Moodle: <code className="bg-surface-100 px-1 rounded">…/course/view.php?id=<strong>42</strong></code>
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-error bg-error-container/40 rounded-xl px-3 py-2 text-label-sm">
                <Icon name="error" className="text-[16px] shrink-0" fill />
                {error}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onCerrar} disabled={sincronizando}>Cancelar</Button>
              <Button
                variant="primary"
                icon={sincronizando ? undefined : 'sync'}
                onClick={handleSincronizar}
                disabled={sincronizando || !courseid.trim()}
              >
                {sincronizando ? 'Sincronizando…' : 'Sincronizar'}
              </Button>
            </div>
          </>
        )}
      </div>
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

  // Diálogos
  const [dialogoCrear, setDialogoCrear] = useState<{ padreId: string | null } | null>(null);
  const [dialogoRenombrar, setDialogoRenombrar] = useState<CategoriaPregunta | null>(null);
  const [dialogoBorrar, setDialogoBorrar] = useState<CategoriaPregunta | null>(null);
  const [dialogoSync, setDialogoSync] = useState(false);

  useEffect(() => {
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, []);

  const cargarCategorias = useCallback(async (mid: string) => {
    setCargandoCats(true);
    try {
      const cats = await listarCategorias(mid);
      setCategorias(cats);
    } catch {
      toast.error('No se pudieron cargar las categorías.');
    } finally {
      setCargandoCats(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!materiaId) { setCategorias([]); setCatSeleccionada(null); setPreguntas([]); return; }
    cargarCategorias(materiaId);
    setCatSeleccionada(null);
    setPreguntas([]);
  }, [materiaId, cargarCategorias]);

  const cargarPreguntas = useCallback(async (mid: string, catId: string | null) => {
    setCargandoPregs(true);
    try {
      const preg = await listarPreguntasBanco(mid, catId);
      setPreguntas(preg);
    } catch {
      toast.error('No se pudieron cargar las preguntas.');
    } finally {
      setCargandoPregs(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!materiaId) return;
    cargarPreguntas(materiaId, catSeleccionada);
  }, [materiaId, catSeleccionada, cargarPreguntas]);

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
      toast.success('Categoría borrada. Las preguntas quedan sin clasificar.');
      if (catSeleccionada === dialogoBorrar.id) setCatSeleccionada(null);
      await cargarCategorias(materiaId);
    } catch {
      toast.error('Error al borrar la categoría.');
    } finally {
      setDialogoBorrar(null);
    }
  }

  async function handleMoverPregunta(preguntaId: string, nuevaCatId: string | null) {
    try {
      await moverPreguntaCategoria(preguntaId, nuevaCatId);
      toast.success('Pregunta movida.');
      await cargarPreguntas(materiaId, catSeleccionada);
    } catch {
      toast.error('Error al mover la pregunta.');
    }
  }

  const tituloCategoria = catSeleccionada === null
    ? 'Sin clasificar'
    : (categorias.find((c) => c.id === catSeleccionada)?.nombre ?? '');

  return (
    <StaffShell nav={STAFF_NAV} title="Banco de preguntas">
      <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col gap-6">
        {/* Encabezado */}
        <div className="flex items-center justify-between gap-md flex-wrap">
          <div>
            <h1 className="text-headline-sm font-bold">Banco de preguntas</h1>
            <p className="text-body-md text-on-surface-variant mt-0.5">
              Organizá las preguntas por categorías para armar exámenes por sorteo.
            </p>
          </div>
          {materiaId && (
            <Button
              variant="outline"
              icon="sync"
              onClick={() => setDialogoSync(true)}
            >
              Sincronizar desde campus
            </Button>
          )}
        </div>

        {/* Selector de materia */}
        <Card className="!p-md">
          <label className="text-label-md font-medium block mb-2">Materia</label>
          <select
            className="border rounded-xl px-3 py-2 text-body-md w-full max-w-sm focus:outline-none focus:ring-2 focus:ring-primary"
            value={materiaId}
            onChange={(e) => setMateriaId(e.target.value)}
          >
            <option value="">— Seleccioná una materia —</option>
            {materias.map((m) => (
              <option key={m.id} value={m.id}>{m.nombre}</option>
            ))}
          </select>
        </Card>

        {materiaId && (
          <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-4 items-start">
            {/* Panel izquierdo: árbol de categorías */}
            <Card className="!p-md">
              <p className="text-label-md font-medium mb-3">Categorías</p>
              {cargandoCats ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="sm" label="Cargando…" />
                </div>
              ) : (
                <CategoriasTree
                  categorias={categorias}
                  seleccionada={catSeleccionada}
                  onSeleccionar={setCatSeleccionada}
                  onCrear={(padreId) => setDialogoCrear({ padreId })}
                  onRenombrar={setDialogoRenombrar}
                  onBorrar={setDialogoBorrar}
                />
              )}
            </Card>

            {/* Panel derecho: preguntas de la categoría seleccionada */}
            <Card className="!p-md">
              <div className="flex items-center justify-between mb-3">
                <p className="text-label-md font-medium">
                  {tituloCategoria}
                  <span className="ml-2 text-on-surface-variant font-normal">
                    ({preguntas.length} pregunta{preguntas.length !== 1 ? 's' : ''})
                  </span>
                </p>
              </div>
              <ListaPreguntas
                preguntas={preguntas}
                categorias={categorias}
                categoriaActualId={catSeleccionada}
                cargando={cargandoPregs}
                onMover={handleMoverPregunta}
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
          titulo="Nueva categoría"
          valorInicial=""
          onConfirmar={handleCrear}
          onCancelar={() => setDialogoCrear(null)}
        />
      )}
      {dialogoRenombrar && (
        <DialogoCategoria
          titulo="Renombrar categoría"
          valorInicial={dialogoRenombrar.nombre}
          onConfirmar={handleRenombrar}
          onCancelar={() => setDialogoRenombrar(null)}
        />
      )}
      {dialogoBorrar && (
        <DialogoBorrar
          categoria={dialogoBorrar}
          onConfirmar={handleBorrar}
          onCancelar={() => setDialogoBorrar(null)}
        />
      )}
      {dialogoSync && materiaId && (
        <DialogoSyncMoodle
          materiaId={materiaId}
          onCerrar={() => setDialogoSync(false)}
          onSincronizado={() => cargarCategorias(materiaId)}
        />
      )}
    </StaffShell>
  );
}
