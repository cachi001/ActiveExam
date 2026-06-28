import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { api, API_BASE, USE_REAL_BACKEND } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { TableToolbar, type TableQuery } from '../ui/TableToolbar';
import { listarExamenesContenidoPaginadoFn } from '../lib/examContentCatalog';
import type { Examen, ExamenContenidoResumen } from '../lib/types';

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

const PAGE_SIZE_DEFAULT = 25;

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
            <div className="overflow-x-auto -mx-lg px-lg">
              <table className="w-full text-left min-w-[580px]">
                <thead>
                  <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                    <th className="py-sm pr-md font-semibold">Examen</th>
                    <th className="py-sm pr-md font-semibold">Materia</th>
                    <th className="py-sm pr-md font-semibold">Comisión</th>
                    <th className="py-sm pr-md font-semibold text-right">Preguntas</th>
                    <th className="py-sm font-semibold text-right">Acciones</th>
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
                      <td className="py-sm pr-md text-label-md text-on-surface tabular-nums text-right">
                        {e.cantidad_preguntas}
                      </td>
                      <td className="py-sm text-right">
                        <div className="flex items-center justify-end gap-xs">
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="open_in_new"
                            onClick={(ev) => { ev.stopPropagation(); navigate(`/admin/examenes/${e.id}`); }}
                          >
                            Detalle
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="settings"
                            onClick={(ev) => { ev.stopPropagation(); configurar(); }}
                          >
                            Config
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Tabla modo demo (C-21): exámenes en memoria ── */}
          {!USE_REAL_BACKEND && hayResultados && (
            <div className="overflow-x-auto -mx-lg px-lg">
              <table className="w-full text-left min-w-[580px]">
                <thead>
                  <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                    <th className="py-sm pr-md font-semibold">Examen</th>
                    <th className="py-sm pr-md font-semibold">Estado</th>
                    <th className="py-sm pr-md font-semibold">Inicio</th>
                    <th className="py-sm pr-md font-semibold">Umbral</th>
                    <th className="py-sm pr-md font-semibold">Inscriptos</th>
                    <th className="py-sm font-semibold text-right">Acción</th>
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
                      <td className="py-sm pr-md text-label-md text-on-surface tabular-nums">
                        Desde {e.umbral_score} <span className="text-on-surface-variant text-label-sm">pts</span>
                      </td>
                      <td className="py-sm pr-md text-label-md text-on-surface">{e.inscriptos}</td>
                      <td className="py-sm text-right">
                        <Button size="sm" variant="ghost" icon="settings" onClick={configurar}>Configurar</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
