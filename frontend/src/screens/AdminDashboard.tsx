// Panel de administración (admin_sistema) — KPIs del cuatrimestre + accesos.
//
// Layout dashboard moderno: 4 stat cards arriba, dos columnas debajo (lista de
// exámenes + columna lateral con "Acciones rápidas"). Cards Card padded={false}
// con header separado por border, hover sobre filas en bg-surface-50.
import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StatCard } from './proctoring/StatCard';
import { Link } from '../lib/router';
import { api } from '../lib/api';
import { STAFF_NAV } from '../ui/nav';
import type { Examen, ResumenReportes } from '../lib/types';

// alias para mantener compatibilidad con las pantallas que ya lo importan
export const ADMIN_NAV = STAFF_NAV;

const ESTADO_TONE = { borrador: 'neutral', programado: 'neutral', en_curso: 'success', finalizado: 'neutral' } as const;
const ESTADO_LABEL = { borrador: 'Borrador', programado: 'Programado', en_curso: 'En curso', finalizado: 'Finalizado' } as const;

export default function AdminDashboard() {
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [rep, setRep] = useState<ResumenReportes | null>(null);
  useEffect(() => { api.listExams().then(setExamenes); api.reportes().then(setRep); }, []);

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Panel de administración"
      subtitle="Estado de exámenes, sesiones supervisadas y cola de revisión del cuatrimestre."
      help={
        <HelpButton title="Panel de administración">
          <p>
            Vista agregada de la actividad del cuatrimestre: exámenes, sesiones supervisadas,
            tasa de flag y tiempo medio de revisión.
          </p>
          <p>
            Desde acá llegás a configurar exámenes, ver reportes, auditoría y gestión de
            usuarios. La supervisión en vivo y la cola de revisión están en el menú lateral.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* Stat cards — paleta clara (primary/info/warning/success), nada de slate oscuro */}
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-md">
          <StatCard icon="quiz" label="Exámenes" value={rep?.examenes_totales ?? '—'} sub="este cuatrimestre" tono="primary" />
          <StatCard icon="groups" label="Sesiones" value={rep?.sesiones_totales ?? '—'} sub="supervisadas" tono="info" />
          <StatCard icon="flag" label="Tasa de flag" value={`${rep?.tasa_flag ?? 0}%`} sub="entran a revisión" tono="warning" />
          <StatCard icon="schedule" label="Revisión media" value={rep?.tiempo_medio_revision ?? '—'} sub="por sesión" tono="success" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          {/* Lista de exámenes — col-span-2 en desktop. Paleta morada para el
              tile + badge (identidad del producto), sin exagerar el tamaño. */}
          <div className="lg:col-span-2">
            <Card padded={false}>
              <div className="px-lg py-md border-b border-surface-200 flex items-center justify-between">
                <div>
                  <h2 className="text-[16px] font-semibold text-on-surface leading-tight">Exámenes</h2>
                  <p className="text-[12.5px] text-on-surface-variant mt-0.5">Estado de los exámenes recientes</p>
                </div>
                <Link to="/admin/examenes" className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">
                  Ver todos
                  <Icon name="arrow_forward" className="text-[16px]" />
                </Link>
              </div>
              <div className="divide-y divide-surface-200">
                {examenes.length === 0 ? (
                  <div className="px-lg py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
                    <Icon name="quiz" className="text-[36px]" />
                    <p className="text-[14px]">Todavía no hay exámenes cargados.</p>
                  </div>
                ) : (
                  examenes.map((e) => (
                    <Link
                      key={e.id}
                      to="/admin/examenes"
                      className="flex items-center justify-between gap-3 px-lg py-3 hover:bg-surface-50 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-md bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
                          <Icon name="description" className="text-[20px]" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[14px] font-semibold text-on-surface truncate leading-tight">{e.nombre}</p>
                          <p className="text-[12.5px] text-on-surface-variant truncate leading-tight mt-0.5">{e.catedra} · {e.inscriptos} inscriptos</p>
                        </div>
                      </div>
                      <Badge tone={ESTADO_TONE[e.estado]}>{ESTADO_LABEL[e.estado]}</Badge>
                    </Link>
                  ))
                )}
              </div>
            </Card>
          </div>

          {/* Acciones rápidas — estilo "outline buttons full-width left-aligned" */}
          <Card padded={false}>
            <div className="px-lg py-md border-b border-surface-200">
              <h2 className="text-[16px] font-semibold text-on-surface leading-tight">Acciones rápidas</h2>
            </div>
            <div className="p-md flex flex-col gap-2">
              <AccionRapida to="/admin/reportes" icon="analytics" label="Ver reportes" />
              <AccionRapida to="/admin/auditoria" icon="policy" label="Auditoría" />
              <AccionRapida to="/admin/usuarios" icon="manage_accounts" label="Usuarios" />
            </div>
          </Card>
        </div>
      </div>
    </StaffShell>
  );
}

function AccionRapida({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <Link
      to={to}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md border border-surface-200 bg-white text-on-surface text-[14px] font-medium hover:bg-surface-50 hover:border-primary/40 transition-colors"
    >
      <Icon name={icon} className="text-[18px] text-on-surface-variant" />
      {label}
      <Icon name="chevron_right" className="text-[18px] text-on-surface-variant ml-auto" />
    </Link>
  );
}
