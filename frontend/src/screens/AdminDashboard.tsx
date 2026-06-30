// Panel de administración (admin_sistema) — KPIs del cuatrimestre + accesos.
//
// Layout dashboard moderno: stat cards arriba, dos columnas debajo (lista de
// exámenes del catálogo real + columna lateral con "Acciones rápidas").
//
// FUENTES DE DATOS:
//   • Exámenes: GET /api/v1/exam-content → ExamenContenidoResumen[] (catálogo real).
//   • Sesiones supervisadas / Tasa de flag: SIN endpoint real en slim → "—" (vacío honesto).
import { useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StatCard } from './proctoring/StatCard';
import { Link } from '../lib/router';
import { api } from '../lib/api';
import { STAFF_NAV } from '../ui/nav';
import type { ExamenContenidoResumen, SesionProctoringResumen } from '../lib/types';
import { examenContenidoSubtitulo, formatVentanaExamen, formatDuracionExamen } from './dashboards.helpers';
import { loadEffectiveConfig, getEffectiveConfig } from '../config/effectiveConfigCache';

// alias para mantener compatibilidad con las pantallas que ya lo importan
export const ADMIN_NAV = STAFF_NAV;

export default function AdminDashboard() {
  const [examenes, setExamenes] = useState<ExamenContenidoResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  // Sesiones reales (GET /proctoring/sessions) + tasa de flag derivada del umbral
  // de cola de revisión. null = todavía cargando; [] = sin sesiones → 0 / 0%.
  const [sesiones, setSesiones] = useState<SesionProctoringResumen[] | null>(null);
  const [umbral, setUmbral] = useState(70);

  useEffect(() => {
    api.listarExamenesContenido()
      .then(setExamenes)
      .finally(() => setCargando(false));

    void (async () => {
      try {
        await loadEffectiveConfig();
        setUmbral(getEffectiveConfig()?.umbral_cola_revision ?? 70);
      } catch { /* sin red: umbral por defecto */ }
      try {
        setSesiones(await api.listarSesionesProctoring());
      } catch {
        setSesiones([]);
      }
    })();
  }, []);

  const totalSesiones = sesiones?.length ?? null;
  const flagged = sesiones ? sesiones.filter((s) => (s.score ?? 0) >= umbral).length : 0;
  const tasaFlag = sesiones && sesiones.length > 0 ? Math.round((flagged / sesiones.length) * 100) : 0;

  return (
    <StaffShell
      nav={ADMIN_NAV}
      title="Panel de administración"
      subtitle="Estado de exámenes, sesiones supervisadas y cola de revisión del cuatrimestre."
      help={
        <HelpButton title="Panel de administración">
          <p>
            Vista agregada de la actividad del cuatrimestre: exámenes importados del catálogo,
            sesiones supervisadas, tasa de flag y tiempo medio de revisión.
          </p>
          <p>
            Desde acá llegás a configurar exámenes, ver reportes, auditoría y gestión de
            usuarios. La supervisión en vivo y la cola de revisión están en el menú lateral.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* Stat cards con datos reales (catálogo + sesiones de proctoring). Cuando
            no hay sesiones se muestra 0 / 0% (no "—"). */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
          <StatCard icon="assignment" label="Exámenes" value={cargando ? '…' : examenes.length} sub="importados" tono="primary" />
          <StatCard icon="groups" label="Sesiones" value={totalSesiones ?? '…'} sub="grabadas" tono="success" />
          <StatCard icon="flag" label="Cola de revisión" value={sesiones === null ? '…' : flagged} sub="sesiones en revisión" tono="warning" />
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          {/* Lista del catálogo de exámenes importados — col-span-2 en desktop. */}
          <div className="lg:col-span-2">
            <Card padded={false}>
              <div className="px-lg py-md border-b border-surface-200 flex items-center justify-between">
                <div>
                  <h2 className="text-[16px] font-semibold text-on-surface leading-tight">Exámenes</h2>
                  <p className="text-[12.5px] text-on-surface-variant mt-0.5">Catálogo de exámenes importados</p>
                </div>
                <Link to="/admin/examenes" className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">
                  Ver todos
                  <Icon name="arrow_forward" className="text-[16px]" />
                </Link>
              </div>
              <div className="divide-y divide-surface-200">
                {cargando ? (
                  <div className="px-lg py-xl flex items-center justify-center">
                    <LoadingSpinner size="sm" label="Cargando exámenes…" />
                  </div>
                ) : examenes.length === 0 ? (
                  <div className="px-lg py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
                    <Icon name="assignment" className="text-[36px]" />
                    <p className="text-[14px]">Todavía no hay exámenes importados.</p>
                  </div>
                ) : (
                  examenes.map((e) => (
                    <ExamenContenidoRow key={e.id} examen={e} />
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
              <AccionRapida to="/admin/materias" icon="school" label="Materias y comisiones" />
            </div>
          </Card>
        </div>
      </div>
    </StaffShell>
  );
}

/** Fila del catálogo de exámenes importados. Muestra titulo + materia/comisión/preguntas. */
function ExamenContenidoRow({ examen }: { examen: ExamenContenidoResumen }) {
  const subtitulo = examenContenidoSubtitulo(examen);
  return (
    <Link
      to="/admin/examenes"
      className="flex items-center justify-between gap-4 px-lg py-4 hover:bg-surface-50 transition-colors"
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="w-12 h-12 rounded-lg bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
          <Icon name="assignment" className="text-[24px]" />
        </div>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-on-surface truncate leading-snug">{examen.titulo}</p>
          <p className="text-[13px] text-on-surface-variant truncate leading-snug mt-0.5">{subtitulo}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-on-surface-variant">
            <span className="inline-flex items-center gap-1 min-w-0">
              <Icon name="event" className="text-[14px] shrink-0" />
              <span className="truncate">{formatVentanaExamen(examen.apertura, examen.cierre)}</span>
            </span>
            <span className="inline-flex items-center gap-1 shrink-0">
              <Icon name="schedule" className="text-[14px]" />
              {formatDuracionExamen(examen.tiempo_limite_min)}
            </span>
          </div>
        </div>
      </div>
      <span className="text-[12px] text-on-surface-variant shrink-0 tabular-nums self-start mt-0.5">{examen.cantidad_preguntas} preg.</span>
    </Link>
  );
}

function AccionRapida({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <Link
      to={to}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md border border-surface-200 bg-white text-on-surface text-[14px] font-medium hover:bg-primary/5 hover:border-primary/50 transition-colors"
    >
      <Icon name={icon} className="text-[18px] text-on-surface-variant" />
      {label}
      <Icon name="chevron_right" className="text-[18px] text-on-surface-variant ml-auto" />
    </Link>
  );
}
