import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { type TableQuery } from '../ui/TableToolbar';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { ActionMenu } from '../ui/ActionMenu';
import { listarExamenesContenidoPaginadoFn } from '../lib/examContentCatalog';
import { ImportExamModal } from '../admin/ExamImport/ImportExamModal';
import { useToast } from '../ui/toast';
import type { ExamenContenidoResumen } from '../lib/types';

const PAGE_SIZE_DEFAULT = 5;
const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 50];

export default function ExamList() {
  const navigate = useNavigate();
  const toast = useToast();

  // Modal de importación (reemplaza la navegación a /admin/examenes/importar).
  const [importOpen, setImportOpen] = useState(false);

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
  // Borrador de búsqueda: se edita libre y recién se aplica con "Aplicar filtros".
  const [borradorQ, setBorradorQ] = useState('');

  const fetchImportados = useCallback(async (q: TableQuery) => {
    setCargando(true);
    try {
      const result = await listarExamenesContenidoPaginadoFn(API_BASE, authProvider.getToken(), {
        q: q.q || undefined,
        page: q.page,
        page_size: q.page_size,
      });
      setImportados(result.items);
      setTotalImportados(result.total);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    fetchImportados(query);
  }, [query, fetchImportados]);

  const importar = () => navigate('/admin/examenes/importar');

  // Éxito del modal: cerrar + refrescar la lista paginada (nuevo ref de query
  // → re-dispara el fetch del useEffect, volviendo a la página 1).
  const onImportado = (importadas: number) => {
    setImportOpen(false);
    setQuery((q) => ({ ...q, page: 1 }));
    toast.success(
      importadas > 0
        ? `Examen importado: ${importadas} ${importadas === 1 ? 'pregunta' : 'preguntas'}.`
        : 'Examen importado correctamente.',
    );
  };

  const hayResultados = importados.length > 0;
  const aplicarBusqueda = () => setQuery((q) => ({ ...q, q: borradorQ.trim(), page: 1 }));
  const limpiarBusqueda = () => {
    setBorradorQ('');
    setQuery((q) => ({ ...q, q: '', page: 1 }));
  };
  const hayCambiosBusqueda = borradorQ.trim() !== query.q;
  const totalPaginas = Math.max(1, Math.ceil(totalImportados / query.page_size));

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Listado de exámenes"
      subtitle="Gestioná las evaluaciones supervisadas: estado, umbral de revisión e inscriptos."
      actions={
        <Button icon="upload" onClick={() => setImportOpen(true)} size="sm">
          Importar examen
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
        {/* Filtros FUERA de la card. */}
        <FiltrosPanel
          onAplicar={aplicarBusqueda}
          onLimpiar={limpiarBusqueda}
          hayFiltros={Boolean(borradorQ || query.q)}
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
              className="min-w-[240px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-surface-500 focus:outline-none"
            />
          </label>
        </FiltrosPanel>

        <Card>
          <div className="flex items-center gap-2 mb-md pb-md border-b border-outline-variant/40">
            <Icon name="fact_check" className="text-[18px] text-on-surface-variant" fill />
            <h2 className="text-[15px] font-semibold text-on-surface">
              Exámenes <span className="text-on-surface-variant font-normal">({totalImportados})</span>
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
                {query.q
                  ? 'Ningún examen coincide con la búsqueda.'
                  : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {/* ── Tabla (C-69): exámenes importados ── */}
          {hayResultados && (
            <>
              {/* Desktop: tabla (md+) */}
              <div className="hidden md:block">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                      <th className="py-sm pl-sm pr-md font-semibold">Examen</th>
                      <th className="py-sm pr-md font-semibold">Materia</th>
                      <th className="py-sm pr-md font-semibold">Comisión</th>
                      <th className="py-sm px-md font-semibold text-center">Preguntas</th>
                      <th className="py-sm font-semibold text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importados.map((e) => (
                      <tr
                        key={e.id}
                        className={`border-b border-outline-variant/20 transition-colors
                          ${cargando ? 'opacity-50' : 'hover:bg-primary-50 cursor-pointer'}`}
                        onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}/resultados`) : undefined}
                      >
                        <td className="py-sm pl-sm pr-md">
                          <p className="text-label-md font-semibold text-on-surface">{e.titulo}</p>
                        </td>
                        <td className="py-sm pr-md text-label-md text-on-surface-variant">
                          {e.materia_nombre ?? <span className="text-outline italic text-label-sm">sin materia</span>}
                        </td>
                        <td className="py-sm pr-md text-label-md text-on-surface-variant">
                          {e.comision_nombre ?? <span className="text-outline italic text-label-sm">sin comisión</span>}
                        </td>
                        <td className="py-sm px-md text-label-md text-on-surface tabular-nums text-center">
                          {e.cantidad_preguntas}
                        </td>
                        <td className="py-sm">
                          <div className="flex items-center justify-center" onClick={(ev) => ev.stopPropagation()}>
                            <ActionMenu
                              ariaLabel={`Acciones de ${e.titulo}`}
                              items={[
                                { label: 'Alumnos que rindieron', icon: 'groups', onClick: () => navigate(`/admin/examenes/${e.id}/resultados`) },
                                { label: 'Detalle del examen', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
                                { label: 'Configurar / vincular', icon: 'settings', onClick: importar },
                              ]}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile: cards apiladas (<md) */}
              <div className="md:hidden space-y-sm">
                {importados.map((e) => (
                  <div
                    key={e.id}
                    className={`rounded-xl border border-outline-variant/40 bg-white p-base flex items-start gap-sm transition-colors
                      ${cargando ? 'opacity-50' : 'active:bg-surface-container-low'}`}
                  >
                    <button
                      type="button"
                      onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}/resultados`) : undefined}
                      className="flex-1 min-w-0 text-left"
                    >
                      <p className="text-label-md font-semibold text-on-surface truncate">{e.titulo}</p>
                      <div className="mt-2 space-y-0.5 text-label-sm text-on-surface-variant">
                        <p>
                          <span className="text-outline">Materia:</span>{' '}
                          {e.materia_nombre ?? <span className="text-outline italic">sin materia</span>}
                        </p>
                        <p>
                          <span className="text-outline">Comisión:</span>{' '}
                          {e.comision_nombre ?? <span className="text-outline italic">sin comisión</span>}
                        </p>
                        <p>
                          <span className="text-outline">Preguntas:</span>{' '}
                          <span className="text-on-surface tabular-nums">{e.cantidad_preguntas}</span>
                        </p>
                      </div>
                    </button>
                    <ActionMenu
                      ariaLabel={`Acciones de ${e.titulo}`}
                      items={[
                        { label: 'Ver detalle', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
                        { label: 'Configurar / vincular', icon: 'settings', onClick: importar },
                      ]}
                    />
                  </div>
                ))}
              </div>
            </>
          )}

        </Card>

        {/* Paginación server-side FUERA de la card (igual que Usuarios). */}
        {totalImportados > 0 && (
          <Pagination
            currentPage={query.page}
            totalPages={totalPaginas}
            totalElements={totalImportados}
            pageSize={query.page_size}
            onPageChange={(p) => setQuery((q) => ({ ...q, page: p }))}
          />
        )}
      </div>

      <ImportExamModal
        abierto={importOpen}
        onCerrar={() => setImportOpen(false)}
        onImportado={onImportado}
      />
    </StaffShell>
  );
}
