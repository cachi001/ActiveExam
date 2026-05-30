import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Stat, SectionTitle, SeverityBadge } from '../ui/components';
import { ADMIN_NAV } from './AdminDashboard';
import { api } from '../lib/api';
import type { ResumenReportes } from '../lib/types';

export default function Reports() {
  const [r, setR] = useState<ResumenReportes | null>(null);
  useEffect(() => { api.reportes().then(setR); }, []);

  if (!r) return <StaffShell nav={ADMIN_NAV} title="Reportes y analítica"><Card>Cargando…</Card></StaffShell>;

  const maxSev = Math.max(...r.distribucion_severidad.map((d) => d.cantidad));
  const maxTend = Math.max(...r.tendencia_semanal.map((t) => Math.max(t.flaggeadas, t.revisadas)));

  return (
    <StaffShell nav={ADMIN_NAV} title="Reportes y analítica">
      <div className="space-y-lg">
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-lg">
          <Stat icon="quiz" label="Exámenes" value={r.examenes_totales} />
          <Stat icon="groups" label="Sesiones" value={r.sesiones_totales} />
          <Stat icon="flag" label="Tasa de flag" value={`${r.tasa_flag}%`} sub="entran a revisión" />
          <Stat icon="rule" label="Falsos positivos" value={`${r.falsos_positivos}%`} sub="descartados en revisión" />
        </div>

        <div className="grid lg:grid-cols-2 gap-lg">
          <Card>
            <SectionTitle sub="Eventos por nivel de severidad">Distribución de severidad</SectionTitle>
            <div className="space-y-sm">
              {r.distribucion_severidad.map((d) => (
                <div key={d.severidad} className="flex items-center gap-sm">
                  <div className="w-20 shrink-0"><SeverityBadge severidad={d.severidad} /></div>
                  <div className="flex-1 h-6 rounded-full bg-surface-container-high overflow-hidden">
                    <div className="h-full bg-primary-container rounded-full flex items-center justify-end pr-base text-on-primary text-label-sm font-semibold"
                      style={{ width: `${Math.max(8, (d.cantidad / maxSev) * 100)}%` }}>{d.cantidad}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <SectionTitle sub="Flaggeadas vs. revisadas">Tendencia semanal</SectionTitle>
            <div className="flex items-end justify-around gap-md h-48 pt-md">
              {r.tendencia_semanal.map((t) => (
                <div key={t.semana} className="flex flex-col items-center gap-base flex-1">
                  <div className="flex items-end gap-base h-40">
                    <div className="w-5 rounded-t-md bg-primary" style={{ height: `${(t.flaggeadas / maxTend) * 100}%` }} title={`${t.flaggeadas} flaggeadas`} />
                    <div className="w-5 rounded-t-md bg-primary-fixed-dim" style={{ height: `${(t.revisadas / maxTend) * 100}%` }} title={`${t.revisadas} revisadas`} />
                  </div>
                  <span className="text-label-sm text-on-surface-variant">{t.semana}</span>
                </div>
              ))}
            </div>
            <div className="flex justify-center gap-md mt-sm text-label-sm text-on-surface-variant">
              <span className="inline-flex items-center gap-base"><span className="w-3 h-3 rounded-sm bg-primary" /> Flaggeadas</span>
              <span className="inline-flex items-center gap-base"><span className="w-3 h-3 rounded-sm bg-primary-fixed-dim" /> Revisadas</span>
            </div>
          </Card>
        </div>

        <Card className="bg-primary-fixed/40 border-primary-fixed-dim/50">
          <div className="flex items-start gap-sm">
            <Icon name="insights" className="text-primary" fill />
            <p className="text-label-md text-on-primary-fixed-variant">
              Tiempo medio de revisión humana: <strong>{r.tiempo_medio_revision}</strong>. La alta tasa de falsos positivos ({r.falsos_positivos}%)
              confirma el enfoque L2.5: el sistema prioriza, pero la decisión final siempre es de un revisor.
            </p>
          </div>
        </Card>
      </div>
    </StaffShell>
  );
}
