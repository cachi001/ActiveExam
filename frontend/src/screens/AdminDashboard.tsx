import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Stat, Badge, Button, SectionTitle } from '../ui/components';
import { Link } from '../lib/router';
import { api } from '../lib/api';
import { STAFF_NAV } from '../ui/nav';
import type { Examen, ResumenReportes } from '../lib/types';

// alias para mantener compatibilidad con las pantallas que ya lo importan
export const ADMIN_NAV = STAFF_NAV;

const ESTADO_TONE = { borrador: 'neutral', programado: 'primary', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

export default function AdminDashboard() {
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [rep, setRep] = useState<ResumenReportes | null>(null);
  useEffect(() => { api.listExams().then(setExamenes); api.reportes().then(setRep); }, []);

  return (
    <StaffShell nav={ADMIN_NAV} title="Panel de administración">
      <div className="space-y-lg">
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-lg">
          <Stat icon="quiz" label="Exámenes" value={rep?.examenes_totales ?? '—'} sub="este cuatrimestre" />
          <Stat icon="groups" label="Sesiones" value={rep?.sesiones_totales ?? '—'} sub="supervisadas" />
          <Stat icon="flag" label="Tasa de flag" value={`${rep?.tasa_flag ?? 0}%`} sub="entran a revisión" />
          <Stat icon="schedule" label="Revisión media" value={rep?.tiempo_medio_revision ?? '—'} sub="por sesión" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2">
            <Card>
              <SectionTitle sub="Estado de los exámenes recientes"
                action={<Link to="/admin/examenes" className="text-label-md text-primary hover:underline">Ver todos</Link>}>
                Exámenes
              </SectionTitle>
              <div className="space-y-base">
                {examenes.map((e) => (
                  <Link key={e.id} to="/admin/examenes" className="flex items-center justify-between gap-md p-sm rounded-xl hover:bg-surface-container-low border border-outline-variant/30">
                    <div className="flex items-center gap-sm">
                      <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center"><Icon name="description" /></div>
                      <div>
                        <p className="text-label-md font-semibold text-on-surface">{e.nombre}</p>
                        <p className="text-label-sm text-on-surface-variant">{e.catedra} · {e.inscriptos} inscriptos</p>
                      </div>
                    </div>
                    <Badge tone={ESTADO_TONE[e.estado]} dot>{ESTADO_LABEL[e.estado]}</Badge>
                  </Link>
                ))}
              </div>
            </Card>
          </div>

          <Card className="space-y-md">
            <h3 className="font-headline text-title-lg text-on-surface">Acciones rápidas</h3>
            <Link to="/admin/configurar"><Button icon="add" className="w-full">Crear examen</Button></Link>
            <Link to="/admin/reportes"><Button variant="outline" icon="analytics" className="w-full">Ver reportes</Button></Link>
            <Link to="/admin/auditoria"><Button variant="outline" icon="policy" className="w-full">Auditoría</Button></Link>
            <div className="bg-primary-fixed/40 rounded-xl p-sm text-label-sm text-on-primary-fixed-variant flex items-start gap-base mt-md">
              <Icon name="shield" className="text-[18px]" fill />
              <span>Nivel L2.5: el sistema prioriza para revisión humana. Nunca sanciona automáticamente.</span>
            </div>
          </Card>
        </div>
      </div>
    </StaffShell>
  );
}
