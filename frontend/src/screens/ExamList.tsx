import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ADMIN_NAV } from './AdminDashboard';
import { useNavigate } from '../lib/router';
import { api } from '../lib/api';
import type { Examen } from '../lib/types';

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

export default function ExamList() {
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [q, setQ] = useState('');
  const navigate = useNavigate();

  useEffect(() => { api.listExams().then(setExamenes); }, []);
  const filtrados = examenes.filter((e) => e.nombre.toLowerCase().includes(q.toLowerCase()) || e.catedra.toLowerCase().includes(q.toLowerCase()));

  const configurar = () => navigate('/admin/configuracion');

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Listado de exámenes"
      subtitle="Gestioná las evaluaciones supervisadas: estado, umbral de revisión e inscriptos."
      help={
        <HelpButton title="Exámenes">
          <p>
            Catálogo de evaluaciones supervisadas con su estado (borrador, programado, en
            curso, finalizado), inscriptos y umbral de revisión.
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
          <SectionTitle sub={`${examenes.length} examen${examenes.length !== 1 ? 'es' : ''}`}>
            Listado
          </SectionTitle>

          <div className="flex items-center gap-base bg-white border border-outline-variant rounded-xl px-sm py-base mb-md
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
