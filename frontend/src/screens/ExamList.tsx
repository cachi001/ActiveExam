import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { api, USE_REAL_BACKEND } from '../lib/api';
import type { Examen, ExamenContenidoResumen } from '../lib/types';

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

export default function ExamList() {
  // Modo real (C-69): exámenes de contenido importados de Moodle, con materia y comisión.
  // Modo demo: exámenes programados en memoria (C-21).
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [importados, setImportados] = useState<ExamenContenidoResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [q, setQ] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    let cancelado = false;
    (async () => {
      if (USE_REAL_BACKEND) {
        const reales = await api.listarExamenesContenido();
        if (cancelado) return;
        setImportados(reales);
      } else {
        const demo = await api.listExams();
        if (cancelado) return;
        setExamenes(demo);
      }
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const configurar = () => navigate('/admin/configuracion');

  const term = q.toLowerCase();
  const importadosFiltrados = importados.filter(
    (e) =>
      e.titulo.toLowerCase().includes(term) ||
      (e.materia_nombre ?? '').toLowerCase().includes(term) ||
      (e.comision_nombre ?? '').toLowerCase().includes(term),
  );
  const demoFiltrados = examenes.filter(
    (e) => e.nombre.toLowerCase().includes(term) || e.catedra.toLowerCase().includes(term),
  );

  const total = USE_REAL_BACKEND ? importados.length : examenes.length;
  const hayResultados = USE_REAL_BACKEND ? importadosFiltrados.length > 0 : demoFiltrados.length > 0;

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
            <em> Configuración del sistema</em>. El botón "Configurar" te lleva ahí.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        <Card>
          <SectionTitle sub={`${total} ${total === 1 ? 'examen' : 'exámenes'}`}>
            Listado
          </SectionTitle>

          <div className="flex items-center gap-base bg-white border border-outline-variant rounded-xl px-sm py-base mb-md
            focus-within:border-primary transition-colors">
            <Icon name="search" className="text-on-surface-variant" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, materia o comisión…"
              className="flex-1 bg-transparent outline-none text-label-md" />
          </div>

          {!cargando && !hayResultados && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {q ? 'Ningún examen coincide con la búsqueda.' : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {/* Modo real (C-69): exámenes importados con materia y comisión */}
          {USE_REAL_BACKEND && hayResultados && (
          <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                <th className="py-sm pr-md font-semibold">Examen</th>
                <th className="py-sm pr-md font-semibold">Materia</th>
                <th className="py-sm pr-md font-semibold">Comisión</th>
                <th className="py-sm pr-md font-semibold">Preguntas</th>
                <th className="py-sm font-semibold text-right">Acción</th>
              </tr>
            </thead>
            <tbody>
              {importadosFiltrados.map((e) => (
                <tr key={e.id} className="border-b border-outline-variant/20 hover:bg-surface-container-low">
                  <td className="py-sm pr-md">
                    <p className="text-label-md font-semibold text-on-surface">{e.titulo}</p>
                    <p className="text-label-sm text-on-surface-variant">{e.id}</p>
                  </td>
                  <td className="py-sm pr-md text-label-md text-on-surface-variant">
                    {e.materia_nombre ?? <span className="text-outline">— sin materia</span>}
                  </td>
                  <td className="py-sm pr-md text-label-md text-on-surface-variant">
                    {e.comision_nombre ?? <span className="text-outline">— sin comisión</span>}
                  </td>
                  <td className="py-sm pr-md text-label-md text-on-surface tabular-nums">{e.cantidad_preguntas}</td>
                  <td className="py-sm text-right">
                    <Button size="sm" variant="ghost" icon="edit" onClick={configurar}>Configurar</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          )}

          {/* Modo demo (C-21): exámenes programados en memoria */}
          {!USE_REAL_BACKEND && hayResultados && (
          <div className="overflow-x-auto">
          <table className="w-full text-left">
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
                <tr key={e.id} className="border-b border-outline-variant/20 hover:bg-surface-container-low">
                  <td className="py-sm pr-md">
                    <p className="text-label-md font-semibold text-on-surface">{e.nombre}</p>
                    <p className="text-label-sm text-on-surface-variant">{e.catedra} · {e.id}</p>
                  </td>
                  <td className="py-sm pr-md"><Badge tone={ESTADO_TONE[e.estado]} dot>{ESTADO_LABEL[e.estado]}</Badge></td>
                  <td className="py-sm pr-md text-label-md text-on-surface-variant">{new Date(e.inicio).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}</td>
                  <td className="py-sm pr-md text-label-md text-on-surface tabular-nums">Desde {e.umbral_score} <span className="text-on-surface-variant text-label-sm">pts</span></td>
                  <td className="py-sm pr-md text-label-md text-on-surface">{e.inscriptos}</td>
                  <td className="py-sm text-right">
                    <Button size="sm" variant="ghost" icon="edit" onClick={configurar}>Configurar</Button>
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
