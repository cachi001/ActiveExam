import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, SectionTitle, SeverityBadge } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StatCard } from './proctoring/StatCard';
import { ADMIN_NAV } from './AdminDashboard';
import { api } from '../lib/api';
import type { ResumenReportes } from '../lib/types';

const SEV_TONE: Record<string, 'primary' | 'success' | 'warning' | 'error'> = {
  baseline: 'primary',
  baja: 'success',
  media: 'warning',
  alta: 'error',
  critica: 'error',
};

const REPORTES_SUBTITULO =
  'Métricas agregadas de exámenes, severidad de eventos y desempeño de la revisión humana.';

const REPORTES_AYUDA = (
  <HelpButton title="Analítica de integridad">
    <p>
      Vista agregada de métricas para auditar el funcionamiento del proctoring: cantidad de
      exámenes, distribución de severidad de eventos y desempeño de la revisión humana
      (tasa de flag, tiempo medio).
    </p>
    <p>
      Estas métricas <strong>no individualizan</strong> a estudiantes — son agregados de
      integridad del sistema. La decisión disciplinaria por persona se hace siempre en la
      cola de revisión.
    </p>
  </HelpButton>
);

export default function Reports() {
  const [r, setR] = useState<ResumenReportes | null>(null);
  const [cargando, setCargando] = useState(!api.modoDemo);

  useEffect(() => {
    // En modo demo NO hay backend de analítica: mostramos estado vacío honesto.
    if (api.modoDemo) return;
    api.reportes().then(setR).finally(() => setCargando(false));
  }, []);

  // Estado vacío: la analítica agregada requiere el backend de reportes conectado.
  if (api.modoDemo || (!cargando && !r)) {
    return (
      <StaffShell nav={ADMIN_NAV} title="Reportes y analítica" subtitle={REPORTES_SUBTITULO} help={REPORTES_AYUDA}>
        <div className="space-y-lg animate-in fade-in duration-500">
          <Card className="flex flex-col items-center justify-center text-center gap-md py-xxl">
            <div className="w-16 h-16 rounded-2xl bg-surface-container-high text-on-surface-variant flex items-center justify-center">
              <Icon name="bar_chart" className="text-[32px]" />
            </div>
            <div className="max-w-md">
              <h2 className="font-headline text-title-lg text-on-surface">Todavía no hay datos de analítica</h2>
              <p className="text-body-md text-on-surface-variant mt-base">
                Cuando se completen exámenes supervisados se generarán las métricas de integridad,
                la distribución de severidad de eventos y el desempeño de la revisión humana.
              </p>
            </div>
          </Card>
        </div>
      </StaffShell>
    );
  }

  if (cargando || !r) {
    return (
      <StaffShell nav={ADMIN_NAV} title="Reportes y analítica" subtitle={REPORTES_SUBTITULO} help={REPORTES_AYUDA}>
        <Card className="flex items-center justify-center gap-sm py-xl text-on-surface-variant">
          <Icon name="progress_activity" className="ae-spin text-[22px]" />
          <span className="text-label-md">Cargando reportes…</span>
        </Card>
      </StaffShell>
    );
  }

  const maxSev = Math.max(...r.distribucion_severidad.map((d) => d.cantidad));
  const maxTend = Math.max(...r.tendencia_semanal.map((t) => Math.max(t.flaggeadas, t.revisadas)));

  return (
    <StaffShell nav={ADMIN_NAV} title="Reportes y analítica" subtitle={REPORTES_SUBTITULO} help={REPORTES_AYUDA}>
      <div className="space-y-lg animate-in fade-in duration-500">
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-md">
          <StatCard icon="quiz" label="Exámenes" value={r.examenes_totales} tono="primary" />
          <StatCard icon="groups" label="Sesiones" value={r.sesiones_totales} tono="info" />
          <StatCard icon="flag" label="Tasa de flag" value={`${r.tasa_flag}%`} sub="entran a revisión" tono="warning" />
          <StatCard icon="rule" label="Falsos positivos" value={`${r.falsos_positivos}%`} sub="descartados en revisión" tono="success" />
        </div>

        <div className="grid lg:grid-cols-2 gap-lg">
          <Card>
            <SectionTitle sub="Eventos por nivel de severidad">Distribución de severidad</SectionTitle>
            <div className="space-y-sm">
              {r.distribucion_severidad.map((d) => (
                <div key={d.severidad} className="flex items-center gap-sm">
                  <div className="w-20 shrink-0"><SeverityBadge severidad={d.severidad} /></div>
                  <div className="flex-1 h-6 rounded-full bg-surface-container-high overflow-hidden">
                    <div
                      className={`h-full rounded-full flex items-center justify-end pr-base text-label-sm font-semibold ${
                        SEV_TONE[d.severidad] === 'primary' ? 'bg-primary-container text-on-primary' :
                        SEV_TONE[d.severidad] === 'success' ? 'bg-success-container text-success' :
                        SEV_TONE[d.severidad] === 'warning' ? 'bg-warning-container text-warning' :
                        'bg-error-container text-on-error-container'
                      }`}
                      style={{ width: `${Math.max(8, (d.cantidad / maxSev) * 100)}%` }}
                    >{d.cantidad}</div>
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
      </div>
    </StaffShell>
  );
}
