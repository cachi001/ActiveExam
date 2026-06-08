import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { Examen } from '../lib/types';

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

export default function ExamList() {
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [q, setQ] = useState('');
  const navigate = useNavigate();
  const setExamenActivo = useApp((s) => s.setExamenActivo);

  useEffect(() => { api.listExams().then(setExamenes); }, []);
  const filtrados = examenes.filter((e) => e.nombre.toLowerCase().includes(q.toLowerCase()) || e.catedra.toLowerCase().includes(q.toLowerCase()));

  const editar = (e: Examen) => { setExamenActivo(e); navigate('/admin/configurar'); };

  return (
    <StaffShell nav={ADMIN_NAV} title="Listado de exámenes">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div className="flex items-start gap-2 min-w-0">
            <p className="text-[13px] text-on-surface-variant">
              Gestioná las evaluaciones supervisadas: estado, umbral de revisión e inscriptos.
            </p>
            <HelpButton title="Exámenes">
              <p>
                Catálogo de evaluaciones supervisadas con su estado (borrador, programado, en
                curso, finalizado), inscriptos y umbral de revisión.
              </p>
              <p>
                Editá un examen para configurar detectores, umbrales y la lista de inscriptos.
                El botón "Crear examen" abre el wizard de configuración.
              </p>
            </HelpButton>
          </div>
          <Button icon="add" onClick={() => { setExamenActivo(null); navigate('/admin/configurar'); }}>Crear examen</Button>
        </div>

        <Card>
          <SectionTitle sub={`${examenes.length} examen${examenes.length !== 1 ? 'es' : ''}`}>
            Listado
          </SectionTitle>

          <div className="flex items-center gap-base bg-surface-container-low border border-outline-variant rounded-xl px-sm py-base mb-md
            focus-within:border-primary transition-colors">
            <Icon name="search" className="text-on-surface-variant" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre o cátedra…"
              className="flex-1 bg-transparent outline-none text-label-md" />
          </div>

          {filtrados.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {q ? 'Ningún examen coincide con la búsqueda.' : 'Todavía no hay exámenes cargados.'}
              </p>
            </div>
          )}

          {filtrados.length > 0 && (
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
              {filtrados.map((e) => (
                <tr key={e.id} className="border-b border-outline-variant/20 hover:bg-surface-container-low">
                  <td className="py-sm pr-md">
                    <p className="text-label-md font-semibold text-on-surface">{e.nombre}</p>
                    <p className="text-label-sm text-on-surface-variant">{e.catedra} · {e.id}</p>
                  </td>
                  <td className="py-sm pr-md"><Badge tone={ESTADO_TONE[e.estado]} dot>{ESTADO_LABEL[e.estado]}</Badge></td>
                  <td className="py-sm pr-md text-label-md text-on-surface-variant">{new Date(e.inicio).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}</td>
                  <td className="py-sm pr-md text-label-md text-on-surface">{e.umbral_score}%</td>
                  <td className="py-sm pr-md text-label-md text-on-surface">{e.inscriptos}</td>
                  <td className="py-sm text-right">
                    <Button size="sm" variant="ghost" icon="edit" onClick={() => editar(e)}>Configurar</Button>
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
