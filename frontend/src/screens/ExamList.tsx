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
import { listarExamenesContenidoPaginadoFn } from '../lib/examContentCatalog';
import { CrearExamenModal } from '../admin/ExamImport/CrearExamenModal';
import { useToast } from '../ui/toast';
import type { ExamenContenidoResumen, Materia, Comision } from '../lib/types';

const PAGE_SIZE_DEFAULT = 5;
const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 50];

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

  const importar = () => navigate('/admin/examenes/importar');

  const onCreado = (_examenId: string, totalPreguntas: number) => {
    setImportOpen(false);
    setQuery((q) => ({ ...q, page: 1 }));
    toast.success(`Examen creado con ${totalPreguntas} ${totalPreguntas === 1 ? 'pregunta' : 'preguntas'}.`);
  };

  const hayResultados = importados.length > 0;
  const aplicarBusqueda = () =>
    setQuery((q) => ({
      ...q,
      q: borradorQ.trim(),
      filters: { materia_id: borradorMateria, comision_id: borradorComision },
      page: 1,
    }));
  const limpiarBusqueda = () => {
    setBorradorQ('');
    setBorradorMateria('');
    setBorradorComision('');
    setComisiones([]);
    setQuery((q) => ({ ...q, q: '', filters: {}, page: 1 }));
  };
  const hayCambiosBusqueda =
    borradorQ.trim() !== query.q ||
    borradorMateria !== (query.filters['materia_id'] ?? '') ||
    borradorComision !== (query.filters['comision_id'] ?? '');
  const hayFiltrosActivos = Boolean(borradorQ || borradorMateria || query.q || query.filters['materia_id']);
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
                {query.q || query.filters['materia_id'] || query.filters['comision_id']
                  ? 'Ningún examen coincide con los filtros.'
                  : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {/* ── Tabla exámenes ── */}
          {hayResultados && (() => {
            const cols: AdminColumn<ExamenContenidoResumen>[] = [
              {
                key: 'titulo',
                header: 'Examen',
                width: '35%',
                cell: (e) => <span className="font-semibold text-gray-900">{e.titulo}</span>,
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
                    <ActionMenu
                      ariaLabel={`Acciones de ${e.titulo}`}
                      items={[
                        { label: 'Alumnos que rindieron', icon: 'groups', onClick: () => navigate(`/admin/examenes/${e.id}/resultados`) },
                        { label: 'Detalle del examen', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
                        { label: 'Configurar / vincular', icon: 'settings', onClick: importar },
                      ]}
                    />
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
                    <div key={e.id} className={`flex items-start gap-3 px-4 py-4 transition-colors ${cargando ? 'opacity-50' : 'hover:bg-gray-50'}`}>
                      <button type="button" onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}/resultados`) : undefined} className="flex-1 min-w-0 text-left">
                        <p className="text-sm font-semibold text-gray-900 truncate">{e.titulo}</p>
                        <p className="text-sm text-gray-500 mt-1">{e.materia_nombre ?? 'sin materia'}{e.comision_nombre && ` · ${e.comision_nombre}`}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{e.cantidad_preguntas} preguntas</p>
                      </button>
                      <ActionMenu ariaLabel={`Acciones de ${e.titulo}`} items={[
                        { label: 'Ver detalle', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
                        { label: 'Configurar / vincular', icon: 'settings', onClick: importar },
                      ]} />
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
    </StaffShell>
  );
}
