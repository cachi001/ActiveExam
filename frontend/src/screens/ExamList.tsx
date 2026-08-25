import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { API_BASE, api } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { type TableQuery } from '../ui/TableToolbar';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { RefreshBar } from '../ui/RefreshBar';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { ActionMenu } from '../ui/ActionMenu';
import { AdminTable, type AdminColumn } from '../ui/AdminTable';
import {
  listarExamenesContenidoPaginadoFn,
  darDeBajaExamenFn,
  duplicarExamenFn,
  reactivarExamenFn,
  type EstadoCatalogoExamen,
} from '../lib/examContentCatalog';
import { CrearExamenModal } from '../admin/ExamImport/CrearExamenModal';
import { ConfirmModal } from '../ui/ConfirmModal';
import { useToast } from '../ui/toast';
import type { ExamenContenidoResumen, Materia, Comision } from '../lib/types';

const PAGE_SIZE_DEFAULT = 5;
const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 50];

/** Opciones del filtro de baja lógica (c-78). El default es solo los vigentes. */
const ESTADOS_CATALOGO: { valor: EstadoCatalogoExamen; label: string }[] = [
  { valor: 'activo', label: 'Activos' },
  { valor: 'inactivo', label: 'Dados de baja' },
  { valor: 'todos', label: 'Todos' },
];

/** true si el examen está dado de baja (c-78: `eliminado_en` con timestamp). */
const estaDeBaja = (e: ExamenContenidoResumen) => Boolean(e.eliminado_en);

export default function ExamList() {
  const navigate = useNavigate();
  const toast = useToast();

  // Modal de importación (reemplaza la navegación a /admin/examenes/importar).
  const [importOpen, setImportOpen] = useState(false);

  // ── Filtros de materia/comisión ───────────────────────────────────────────
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [borradorMateria, setBorradorMateria] = useState('');
  const [borradorComision, setBorradorComision] = useState('');
  const [borradorEstado, setBorradorEstado] = useState<EstadoCatalogoExamen>('activo');

  // Baja/reactivación pendiente de confirmación (c-78). null = sin diálogo abierto.
  const [pendienteBaja, setPendienteBaja] = useState<ExamenContenidoResumen | null>(null);
  const [pendienteReactivar, setPendienteReactivar] = useState<ExamenContenidoResumen | null>(null);
  // Duplicación pendiente (c-78 §14.2) + el título que va a llevar la copia.
  const [pendienteDuplicar, setPendienteDuplicar] = useState<ExamenContenidoResumen | null>(null);
  const [tituloCopia, setTituloCopia] = useState('');

  useEffect(() => {
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, []);

  useEffect(() => {
    if (!borradorMateria) { setComisiones([]); setBorradorComision(''); return; }
    api.comisionesDeMateria(borradorMateria).then(setComisiones).catch(() => setComisiones([]));
    setBorradorComision('');
  }, [borradorMateria]);

  // ── Exámenes paginados serverside ────────────────────────────────────────
  const [query, setQuery] = useState<TableQuery>({
    q: '',
    filters: {},
    page: 1,
    page_size: PAGE_SIZE_DEFAULT,
  });
  const [importados, setImportados] = useState<ExamenContenidoResumen[]>([]);
  const [totalImportados, setTotalImportados] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  // Borrador de búsqueda: se edita libre y recién se aplica con "Aplicar filtros".
  const [borradorQ, setBorradorQ] = useState('');

  const fetchImportados = useCallback(async (q: TableQuery) => {
    setCargando(true);
    try {
      const result = await listarExamenesContenidoPaginadoFn(API_BASE, authProvider.getToken(), {
        q: q.q || undefined,
        page: q.page,
        page_size: q.page_size,
        materia_id: q.filters['materia_id'] || undefined,
        comision_id: q.filters['comision_id'] || undefined,
        estado: (q.filters['estado'] as EstadoCatalogoExamen) || undefined,
      });
      setImportados(result.items);
      setTotalImportados(result.total);
      setLastUpdatedAt(Date.now());
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    fetchImportados(query);
  }, [query, fetchImportados]);

  // Auto-refresh cada 5 min conservando la búsqueda/paginación actual.
  useAutoRefresh(() => fetchImportados(query), undefined, !cargando);

  // F-05 (c-78 §7.1): "Configurar / vincular" se RETIRÓ del menú de fila. Nunca
  // navegaba al examen de la fila: llevaba a la página genérica de importación
  // (`/admin/examenes/importar`), o sea que desde la fila del examen A se terminaba
  // importando cualquier cosa. No se la reapuntó al detalle porque "Detalle del
  // examen" YA va a `/admin/examenes/{id}`, que es donde vive la configuración y el
  // destino Moodle por examen: reapuntarla dejaba dos entradas al mismo lugar con
  // nombres distintos. La importación queda como acción de PANTALLA ("Crear examen",
  // arriba a la derecha), que es su alcance real.

  const recargar = useCallback(() => fetchImportados(query), [fetchImportados, query]);

  // c-78 §2: baja lógica. El examen sale del catálogo pero su evidencia queda —
  // por eso el diálogo lo dice explícitamente antes de confirmar.
  const confirmarBaja = async () => {
    const examen = pendienteBaja;
    if (!examen) return;
    setPendienteBaja(null);
    try {
      await darDeBajaExamenFn(API_BASE, authProvider.getToken(), examen.id);
      toast.success(`Se dio de baja «${examen.titulo}».`);
      await recargar();
    } catch {
      toast.error('No se pudo dar de baja el examen. Probá de nuevo.');
    }
  };

  const confirmarReactivar = async () => {
    const examen = pendienteReactivar;
    if (!examen) return;
    setPendienteReactivar(null);
    try {
      await reactivarExamenFn(API_BASE, authProvider.getToken(), examen.id);
      toast.success(`Se reactivó «${examen.titulo}».`);
      await recargar();
    } catch {
      toast.error('No se pudo reactivar el examen. Probá de nuevo.');
    }
  };

  // c-78 §14.2: duplicar. El título de la copia se decide ACÁ porque después no
  // se puede cambiar: no hay edición de título en el detalle del examen.
  const confirmarDuplicar = async () => {
    const examen = pendienteDuplicar;
    if (!examen) return;
    const titulo = tituloCopia.trim();
    if (!titulo) return;
    setPendienteDuplicar(null);
    try {
      const copia = await duplicarExamenFn(
        API_BASE,
        authProvider.getToken(),
        examen.id,
        titulo,
      );
      toast.success(`Se creó «${copia.titulo}» con ${copia.total_preguntas} preguntas.`);
      await recargar();
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'No se pudo duplicar el examen. Probá de nuevo.',
      );
    }
  };

  const onCreado = (_examenId: string, totalPreguntas: number, examenesCreados = 1) => {
    setImportOpen(false);
    setQuery((q) => ({ ...q, page: 1 }));
    const preguntas = `${totalPreguntas} ${totalPreguntas === 1 ? 'pregunta' : 'preguntas'}`;
    toast.success(
      examenesCreados > 1
        ? `${examenesCreados} exámenes creados, uno por comisión, con las mismas ${preguntas}.`
        : `Examen creado con ${preguntas}.`,
    );
  };

  const hayResultados = importados.length > 0;
  const aplicarBusqueda = () =>
    setQuery((q) => ({
      ...q,
      q: borradorQ.trim(),
      filters: {
        materia_id: borradorMateria,
        comision_id: borradorComision,
        estado: borradorEstado,
      },
      page: 1,
    }));
  const limpiarBusqueda = () => {
    setBorradorQ('');
    setBorradorMateria('');
    setBorradorComision('');
    setBorradorEstado('activo');
    setComisiones([]);
    setQuery((q) => ({ ...q, q: '', filters: {}, page: 1 }));
  };
  const hayCambiosBusqueda =
    borradorQ.trim() !== query.q ||
    borradorMateria !== (query.filters['materia_id'] ?? '') ||
    borradorComision !== (query.filters['comision_id'] ?? '') ||
    borradorEstado !== ((query.filters['estado'] as EstadoCatalogoExamen) ?? 'activo');
  // F-05: la comisión y el estado son filtros como cualquier otro. Faltaban acá, así
  // que aplicar SOLO comisión dejaba "Limpiar filtros" apagado y la pantalla decía
  // "todavía no hay datos" cuando en realidad el filtro no matcheaba nada.
  const hayFiltrosActivos = Boolean(
    borradorQ ||
      borradorMateria ||
      borradorComision ||
      (borradorEstado && borradorEstado !== 'activo') ||
      query.q ||
      query.filters['materia_id'] ||
      query.filters['comision_id'] ||
      (query.filters['estado'] && query.filters['estado'] !== 'activo'),
  );
  // Los filtros YA APLICADOS (no los borradores): deciden si el vacío es "nada
  // coincide" o "todavía no hay nada cargado".
  const hayFiltrosAplicados = Boolean(
    query.q ||
      query.filters['materia_id'] ||
      query.filters['comision_id'] ||
      (query.filters['estado'] && query.filters['estado'] !== 'activo'),
  );
  const totalPaginas = Math.max(1, Math.ceil(totalImportados / query.page_size));

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Listado de exámenes"
      subtitle="Gestioná las evaluaciones supervisadas. Creá exámenes sorteando preguntas del banco."
      actions={
        <Button icon="add" onClick={() => setImportOpen(true)} size="sm">
          Crear examen
        </Button>
      }
      help={
        <HelpButton title="Exámenes">
          <p>
            Catálogo de evaluaciones supervisadas. Con la plataforma conectada, lista los
            exámenes importados desde Moodle con su <em>materia</em> y <em>comisión</em>.
          </p>
          <p>
            Los detectores, umbrales y pesos se configuran de forma global en
            <em> Configuración del sistema</em>. Hacé clic en un examen (o en
            "Alumnos que rindieron") para ver quiénes lo rindieron y sincronizar
            notas con Moodle.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Exámenes"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargando}
          onActualizar={() => fetchImportados(query)}
        />
        {/* Filtros FUERA de la card. */}
        <FiltrosPanel
          onAplicar={aplicarBusqueda}
          onLimpiar={limpiarBusqueda}
          hayFiltros={hayFiltrosActivos}
          hayCambios={hayCambiosBusqueda}
          aplicarDeshabilitado={cargando}
        >
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Buscar
            <input
              type="text"
              value={borradorQ}
              placeholder="Nombre, materia o comisión…"
              onChange={(e) => setBorradorQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') aplicarBusqueda();
              }}
              className="min-w-[220px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Materia
            <select
              value={borradorMateria}
              onChange={(e) => setBorradorMateria(e.target.value)}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todas las materias</option>
              {materias.map((m) => (
                <option key={m.id} value={m.id}>{m.nombre}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Comisión
            <select
              value={borradorComision}
              onChange={(e) => setBorradorComision(e.target.value)}
              disabled={!borradorMateria || comisiones.length === 0}
              className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:opacity-50"
            >
              <option value="">Todas las comisiones</option>
              {comisiones.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Estado
            <select
              value={borradorEstado}
              onChange={(e) => setBorradorEstado(e.target.value as EstadoCatalogoExamen)}
              className="min-w-[150px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              {ESTADOS_CATALOGO.map((op) => (
                <option key={op.valor} value={op.valor}>{op.label}</option>
              ))}
            </select>
          </label>
        </FiltrosPanel>

        <Card>
          <div className="flex items-center gap-2 pb-3 mb-3 border-b border-surface-100">
            <Icon name="fact_check" className="text-[16px] text-gray-400 shrink-0" />
            <h2 className="text-base font-semibold text-surface-800">
              Exámenes <span className="text-surface-400 font-normal text-sm">({totalImportados})</span>
            </h2>
            <PageSizeSelect
              className="ml-auto"
              value={query.page_size}
              onChange={(ps) => setQuery((q) => ({ ...q, page_size: ps, page: 1 }))}
              options={PAGE_SIZE_OPTIONS}
            />
          </div>

          {/* ── Loading skeleton ── */}
          {cargando && !hayResultados && (
            <LoadingSpinner size="sm" label="Cargando exámenes…" />
          )}

          {/* ── Estado vacío ── */}
          {!cargando && !hayResultados && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {hayFiltrosAplicados
                  ? 'Ningún examen coincide con los filtros.'
                  : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {/* ── Tabla exámenes ── */}
          {hayResultados && (() => {
            // Acciones de fila. Se comparten entre escritorio y la vista compacta
            // para que no vuelvan a divergir (a la compacta le faltaba "Alumnos que
            // rindieron"). La baja y la reactivación son excluyentes: cuál se ofrece
            // lo decide `eliminado_en`, no el filtro activo.
            const accionesDe = (e: ExamenContenidoResumen) => [
              { label: 'Alumnos que rindieron', icon: 'groups', onClick: () => navigate(`/admin/examenes/${e.id}/resultados`) },
              { label: 'Detalle del examen', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
              // Duplicar solo tiene sentido sobre un examen vigente: uno dado de
              // baja se reactiva primero (el backend devuelve 404 igual).
              ...(estaDeBaja(e)
                ? []
                : [
                    {
                      label: 'Duplicar',
                      icon: 'content_copy',
                      onClick: () => {
                        setTituloCopia(`${e.titulo} (copia)`);
                        setPendienteDuplicar(e);
                      },
                    },
                  ]),
              estaDeBaja(e)
                ? { label: 'Reactivar', icon: 'restore_from_trash', onClick: () => setPendienteReactivar(e) }
                : { label: 'Dar de baja', icon: 'delete', onClick: () => setPendienteBaja(e) },
            ];

            const cols: AdminColumn<ExamenContenidoResumen>[] = [
              {
                key: 'titulo',
                header: 'Examen',
                width: '35%',
                cell: (e) => (
                  <span className="flex items-center gap-2 min-w-0">
                    <span className={`font-semibold truncate ${estaDeBaja(e) ? 'text-gray-500 line-through' : 'text-gray-900'}`}>
                      {e.titulo}
                    </span>
                    {estaDeBaja(e) && (
                      <span className="shrink-0 rounded-full bg-surface-200 px-2 py-0.5 text-[11px] font-medium text-on-surface-variant">
                        Dado de baja
                      </span>
                    )}
                    {/* c-78 E-07: sin habilitar es lo más importante que hay que
                        ver de un vistazo — el alumno no lo puede rendir. */}
                    {e.borrador && !estaDeBaja(e) && (
                      <span className="shrink-0 rounded-full bg-warning-container px-2 py-0.5 text-[11px] font-medium text-warning">
                        Sin habilitar
                      </span>
                    )}
                    {e.modo_preguntas === 'sorteo_por_intento' && (
                      <span
                        className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
                        title="Cada alumno recibe preguntas distintas, sorteadas al entrar."
                      >
                        Sorteado
                      </span>
                    )}
                  </span>
                ),
              },
              {
                key: 'materia',
                header: 'Materia',
                width: '25%',
                cell: (e) => e.materia_nombre
                  ? (
                    <div className="leading-tight">
                      <div className="font-semibold text-gray-900">{e.materia_codigo}</div>
                      <div className="text-gray-500 text-sm">{e.materia_nombre}</div>
                    </div>
                  )
                  : <span className="text-gray-400 italic">Sin materia</span>,
              },
              {
                key: 'comision',
                header: 'Comisión',
                width: '20%',
                cell: (e) => e.comision_nombre
                  ? (
                    <div className="leading-tight">
                      <div className="font-semibold text-gray-900">{e.comision_codigo}</div>
                      <div className="text-gray-500 text-sm">{e.comision_nombre}</div>
                    </div>
                  )
                  : <span className="text-gray-400 italic">Sin comisión</span>,
              },
              {
                key: 'preguntas',
                header: 'Preguntas',
                width: '10%',
                align: 'center',
                cell: (e) => <span className="tabular-nums font-medium text-gray-700">{e.cantidad_preguntas}</span>,
              },
              {
                key: 'acciones',
                header: 'Acciones',
                width: '10%',
                align: 'center',
                cell: (e) => (
                  <div onClick={(ev) => ev.stopPropagation()}>
                    <ActionMenu ariaLabel={`Acciones de ${e.titulo}`} items={accionesDe(e)} />
                  </div>
                ),
              },
            ];
            return (
              <>
                <div className="hidden md:block -mx-lg">
                  <AdminTable
                    columns={cols}
                    data={importados}
                    keyExtractor={(e) => e.id}
                    isLoading={cargando}
                    onRowClick={!cargando ? (e) => navigate(`/admin/examenes/${e.id}/resultados`) : undefined}
                  />
                </div>
                {/* Mobile */}
                <div className="md:hidden divide-y divide-gray-200">
                  {importados.map((e) => (
                    <div key={e.id} className={`flex items-start gap-3 px-4 py-4 transition-colors ${cargando ? 'opacity-50' : 'hover:bg-gray-50'} ${estaDeBaja(e) ? 'bg-surface-100/60' : ''}`}>
                      <button type="button" onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}/resultados`) : undefined} className="flex-1 min-w-0 text-left">
                        <p className={`text-sm font-semibold truncate ${estaDeBaja(e) ? 'text-gray-500 line-through' : 'text-gray-900'}`}>{e.titulo}</p>
                        {estaDeBaja(e) && <p className="text-xs font-medium text-on-surface-variant mt-0.5">Dado de baja</p>}
                        <p className="text-sm text-gray-500 mt-1">{e.materia_nombre ?? 'sin materia'}{e.comision_nombre && ` · ${e.comision_nombre}`}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{e.cantidad_preguntas} preguntas</p>
                      </button>
                      <ActionMenu ariaLabel={`Acciones de ${e.titulo}`} items={accionesDe(e)} />
                    </div>
                  ))}
                </div>
              </>
            );
          })()}

        </Card>

        {/* Paginación server-side FUERA de la card — siempre visible */}
        <Pagination
          currentPage={query.page}
          totalPages={totalPaginas}
          totalElements={totalImportados}
          pageSize={query.page_size}
          onPageChange={(p) => setQuery((q) => ({ ...q, page: p }))}
        />
      </div>

      <CrearExamenModal
        abierto={importOpen}
        onCerrar={() => setImportOpen(false)}
        onCreado={onCreado}
      />

      <ConfirmModal
        abierto={pendienteBaja !== null}
        titulo="Dar de baja el examen"
        variante="danger"
        textoConfirmar="Dar de baja"
        mensaje={
          <>
            <p>
              «{pendienteBaja?.titulo}» deja de aparecer en el catálogo, en el panel y
              en el selector de Notas. No se podrá elegir para cargar notas nuevas.
            </p>
            <p className="mt-2">
              <strong>No se borra nada.</strong> Las sesiones que ya se rindieron, sus
              eventos y su evidencia se conservan igual y siguen consultables. Podés
              reactivarlo cuando quieras desde el filtro "Dados de baja".
            </p>
          </>
        }
        onConfirmar={confirmarBaja}
        onCancelar={() => setPendienteBaja(null)}
      />

      <ConfirmModal
        abierto={pendienteReactivar !== null}
        titulo="Reactivar el examen"
        textoConfirmar="Reactivar"
        mensaje={
          <p>
            «{pendienteReactivar?.titulo}» vuelve al catálogo y al selector de Notas,
            tal como estaba antes de la baja.
          </p>
        }
        onConfirmar={confirmarReactivar}
        onCancelar={() => setPendienteReactivar(null)}
      />

      <ConfirmModal
        abierto={pendienteDuplicar !== null}
        titulo="Duplicar el examen"
        textoConfirmar="Duplicar"
        mensaje={
          <>
            <p>
              Se crea un examen nuevo con las mismas preguntas de «
              {pendienteDuplicar?.titulo}», en la misma comisión.
            </p>
            <label className="flex flex-col gap-1 mt-3">
              <span className="text-label-sm font-medium text-on-surface-variant">
                Título de la copia
              </span>
              <input
                type="text"
                value={tituloCopia}
                onChange={(ev) => setTituloCopia(ev.target.value)}
                className="rounded-lg border border-surface-300 px-3 py-2 text-label-md text-on-surface focus:border-primary focus:outline-none"
              />
            </label>
            <p className="mt-3 text-label-sm text-on-surface-variant">
              La copia nace limpia: <strong>no</strong> arrastra los intentos ya
              rendidos, ni las notas publicadas, ni el destino de Moodle. Esos siguen
              siendo del examen original.
            </p>
          </>
        }
        onConfirmar={confirmarDuplicar}
        onCancelar={() => setPendienteDuplicar(null)}
      />
    </StaffShell>
  );
}
