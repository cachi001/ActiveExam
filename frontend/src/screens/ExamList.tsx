import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { api, API_BASE, USE_REAL_BACKEND } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { TableToolbar, type TableQuery } from '../ui/TableToolbar';
import { ActionMenu } from '../ui/ActionMenu';
import { listarExamenesContenidoPaginadoFn } from '../lib/examContentCatalog';
import type { Examen, ExamenContenidoResumen } from '../lib/types';

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

const PAGE_SIZE_DEFAULT = 5;
const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 50];

export default function ExamList() {
  const navigate = useNavigate();

  // ── Modo real: exámenes paginados serverside ────────────────────────────
  const [query, setQuery] = useState<TableQuery>({
    q: '',
    filters: {},
    page: 1,
    page_size: PAGE_SIZE_DEFAULT,
  });
  const [importados, setImportados] = useState<ExamenContenidoResumen[]>([]);
  const [totalImportados, setTotalImportados] = useState(0);
  const [cargando, setCargando] = useState(true);

  // ── Modo demo: exámenes en memoria (sin paginación serverside) ──────────
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [demoQ, setDemoQ] = useState('');

  const fetchImportados = useCallback(async (q: TableQuery) => {
    if (!USE_REAL_BACKEND) return;
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
    if (USE_REAL_BACKEND) {
      fetchImportados(query);
    } else {
      api.listExams()
        .then(setExamenes)
        .finally(() => setCargando(false));
    }
  }, [query, fetchImportados]);

  const configurar = () => navigate('/admin/configuracion');
  const importar = () => navigate('/admin/examenes/importar');

  // Demo: filtrado en memoria (solo modo sin backend, datos pequeños)
  const demoTerm = demoQ.toLowerCase();
  const demoFiltrados = examenes.filter(
    (e) => e.nombre.toLowerCase().includes(demoTerm) || e.catedra.toLowerCase().includes(demoTerm),
  );

  const hayResultados = USE_REAL_BACKEND ? importados.length > 0 : demoFiltrados.length > 0;

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Listado de exámenes"
      subtitle="Gestioná las evaluaciones supervisadas: estado, umbral de revisión e inscriptos."
      help={
        <HelpButton title="Exámenes">
          <p>
            Catálogo de evaluaciones supervisadas. Con la plataforma conectada, lista los
            exámenes importados desde Moodle con su <em>materia</em> y <em>comisión</em>.
          </p>
          <p>
            Los detectores, umbrales y pesos se configuran de forma global en
            <em> Configuración del sistema</em>. Hacé clic en "Detalle" para ver los
            alumnos que rindieron y sincronizar notas con Moodle.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <Card>
          <SectionTitle
            sub={USE_REAL_BACKEND
              ? `${totalImportados} ${totalImportados === 1 ? 'examen' : 'exámenes'}`
              : `${examenes.length} ${examenes.length === 1 ? 'examen' : 'exámenes'}`}
            action={
              <Button icon="upload" onClick={importar} className="shrink-0">
                Importar examen
              </Button>
            }
          >
            Listado
          </SectionTitle>

          {/* ── Modo real: TableToolbar serverside ── */}
          {USE_REAL_BACKEND && (
            <div className="mb-md">
              <TableToolbar
                query={query}
                onChange={setQuery}
                placeholder="Buscar por nombre, materia o comisión…"
                total={totalImportados}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
                loading={cargando}
              />
            </div>
          )}

          {/* ── Modo demo: buscador simple en memoria ── */}
          {!USE_REAL_BACKEND && (
            <div className="flex items-center gap-base bg-white border border-outline-variant rounded-xl px-sm py-base mb-md
              focus-within:border-primary transition-colors">
              <Icon name="search" className="text-on-surface-variant" />
              <input
                value={demoQ}
                onChange={(e) => setDemoQ(e.target.value)}
                placeholder="Buscar por nombre o cátedra…"
                className="flex-1 bg-transparent outline-none text-label-md"
              />
            </div>
          )}

          {/* ── Loading skeleton ── */}
          {cargando && !hayResultados && (
            <LoadingSpinner size="sm" label="Cargando exámenes…" />
          )}

          {/* ── Estado vacío ── */}
          {!cargando && !hayResultados && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {USE_REAL_BACKEND && (query.q)
                  ? 'Ningún examen coincide con la búsqueda.'
                  : !USE_REAL_BACKEND && demoQ
                    ? 'Ningún examen coincide con la búsqueda.'
                    : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {/* ── Tabla modo real (C-69): exámenes importados ── */}
          {USE_REAL_BACKEND && hayResultados && (
            <>
              {/* Desktop: tabla (md+) */}
              <div className="hidden md:block">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                      <th className="py-sm pr-md font-semibold">Examen</th>
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
                          ${cargando ? 'opacity-50' : 'hover:bg-surface-container-low cursor-pointer'}`}
                        onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}`) : undefined}
                      >
                        <td className="py-sm pr-md">
                          <p className="text-label-md font-semibold text-on-surface">{e.titulo}</p>
                          <p className="text-label-sm text-on-surface-variant font-mono text-[11px]">{e.id}</p>
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
                                { label: 'Ver detalle', icon: 'open_in_new', onClick: () => navigate(`/admin/examenes/${e.id}`) },
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
                      onClick={!cargando ? () => navigate(`/admin/examenes/${e.id}`) : undefined}
                      className="flex-1 min-w-0 text-left"
                    >
                      <p className="text-label-md font-semibold text-on-surface truncate">{e.titulo}</p>
                      <p className="text-label-sm text-on-surface-variant font-mono text-[11px] truncate mt-0.5">{e.id}</p>
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

          {/* ── Tabla modo demo (C-21): exámenes en memoria ── */}
          {!USE_REAL_BACKEND && hayResultados && (
            <>
              {/* Desktop: tabla (md+) */}
              <div className="hidden md:block">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                      <th className="py-sm pr-md font-semibold">Examen</th>
                      <th className="py-sm pr-md font-semibold">Estado</th>
                      <th className="py-sm pr-md font-semibold">Inicio</th>
                      <th className="py-sm px-md font-semibold text-center">Umbral</th>
                      <th className="py-sm px-md font-semibold text-center">Inscriptos</th>
                      <th className="py-sm font-semibold text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {demoFiltrados.map((e) => (
                      <tr key={e.id} className="border-b border-outline-variant/20 hover:bg-surface-container-low transition-colors">
                        <td className="py-sm pr-md">
                          <p className="text-label-md font-semibold text-on-surface">{e.nombre}</p>
                          <p className="text-label-sm text-on-surface-variant">{e.catedra} · {e.id}</p>
                        </td>
                        <td className="py-sm pr-md">
                          <Badge tone={ESTADO_TONE[e.estado]} dot>{ESTADO_LABEL[e.estado]}</Badge>
                        </td>
                        <td className="py-sm pr-md text-label-md text-on-surface-variant">
                          {new Date(e.inicio).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td className="py-sm px-md text-label-md text-on-surface tabular-nums text-center">
                          Desde {e.umbral_score} <span className="text-on-surface-variant text-label-sm">pts</span>
                        </td>
                        <td className="py-sm px-md text-label-md text-on-surface tabular-nums text-center">{e.inscriptos}</td>
                        <td className="py-sm">
                          <div className="flex items-center justify-center">
                            <ActionMenu
                              ariaLabel={`Acciones de ${e.nombre}`}
                              items={[{ label: 'Configurar', icon: 'settings', onClick: configurar }]}
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
                {demoFiltrados.map((e) => (
                  <div key={e.id} className="rounded-xl border border-outline-variant/40 bg-white p-base flex items-start gap-sm">
                    <div className="flex-1 min-w-0">
                      <p className="text-label-md font-semibold text-on-surface truncate">{e.nombre}</p>
                      <p className="text-label-sm text-on-surface-variant truncate mt-0.5">{e.catedra} · {e.id}</p>
                      <div className="mt-2">
                        <Badge tone={ESTADO_TONE[e.estado]} dot>{ESTADO_LABEL[e.estado]}</Badge>
                      </div>
                      <div className="mt-2 space-y-0.5 text-label-sm text-on-surface-variant">
                        <p>
                          <span className="text-outline">Inicio:</span>{' '}
                          {new Date(e.inicio).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
                        </p>
                        <p>
                          <span className="text-outline">Umbral:</span>{' '}
                          <span className="text-on-surface tabular-nums">desde {e.umbral_score} pts</span>
                        </p>
                        <p>
                          <span className="text-outline">Inscriptos:</span>{' '}
                          <span className="text-on-surface tabular-nums">{e.inscriptos}</span>
                        </p>
                      </div>
                    </div>
                    <ActionMenu
                      ariaLabel={`Acciones de ${e.nombre}`}
                      items={[{ label: 'Configurar', icon: 'settings', onClick: configurar }]}
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
