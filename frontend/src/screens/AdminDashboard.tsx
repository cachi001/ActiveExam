// Panel de administración (admin_sistema) — KPIs del cuatrimestre + accesos.
//
// Layout dashboard moderno: stat cards arriba, dos columnas debajo (lista de
// exámenes del catálogo real + columna lateral con "Acciones rápidas").
//
// FUENTES DE DATOS:
//   • Exámenes: GET /api/v1/exam-content → ExamenContenidoResumen[] (catálogo real).
//   • Sesiones supervisadas / Tasa de flag: SIN endpoint real en activeexam → "—" (vacío honesto).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { RefreshBar } from '../ui/RefreshBar';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { Icon, Card, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StatCard } from './proctoring/StatCard';
import { statProps } from './proctoring/statCatalog';
import { entraACola } from './proctoring/colaAgregacion';
import { Link } from '../lib/router';
import { api } from '../lib/api';
import { useAuth } from '../lib/authStore';
import { useCachedData } from '../lib/useCachedData';
import { STAFF_NAV, navItemsParaRoles } from '../ui/nav';
import type { ExamenContenidoResumen, SesionProctoringResumen } from '../lib/types';
import { examenContenidoSubtitulo, formatVentanaExamen, formatDuracionExamen, statExamenesValue } from './dashboards.helpers';
import { loadEffectiveConfig, getEffectiveConfig } from '../config/effectiveConfigCache';
import { UMBRAL_REVISION_MIN } from '../config/umbralRevision';

// alias para mantener compatibilidad con las pantallas que ya lo importan
export const ADMIN_NAV = STAFF_NAV;

export default function AdminDashboard() {
  // Contrato de carga resiliente (C-73): si el fetch del catálogo FALLA, se
  // muestra estado de error con reintentar — NUNCA "0 exámenes" fantasma.
  // Cache stale-while-revalidate (sección 5): volver al dashboard sirve la lista
  // al instante y revalida en background. La clave 'examenes-contenido' la
  // invalida el import de exámenes (MoodleImportPage) tras una alta.
  // Acciones rápidas: se DERIVAN de la navegación (STAFF_NAV) filtrada por los
  // roles del usuario. Antes eran dos <AccionRapida> hardcodeadas, así que cada
  // pantalla nueva que se sumaba al sistema quedaba afuera del panel y encima
  // podía ofrecer un destino sin permiso. Se excluye el propio dashboard.
  const roles = useAuth((s) => s.principal?.roles);
  // El admin ve TODO el catálogo; el resto solo lo suyo. Cambia qué significa
  // que la lista venga vacía.
  const esInstitucional = (roles ?? []).includes('admin_sistema');
  // Atajos CURADOS: lo que el admin toca todos los días, no el mapa entero del
  // sistema (para eso está la barra lateral, que ya los lista todos). El orden es
  // el de uso real: cargar/configurar exámenes → armar materias y comisiones →
  // dar de alta gente. Se cruza con los roles para no ofrecer un destino que el
  // usuario no puede abrir.
  const ATAJOS = ['/admin/examenes', '/admin/materias', '/admin/usuarios'];
  const accionesRapidas = useMemo(() => {
    const permitidos = navItemsParaRoles(roles);
    return ATAJOS.map((ruta) => permitidos.find((i) => i.to === ruta)).filter(
      (i): i is NonNullable<typeof i> => Boolean(i),
    );
  }, [roles]);

  // `strict`: sin esto un fallo de red devolvía [] y la tarjeta mostraba "0
  // exámenes importados" con la base llena. El hook necesita VER el error para
  // poder pintar '—' en vez de un cero que parece un dato.
  const examenesState = useCachedData('examenes-contenido', () => api.listarExamenesContenido(true), []);
  const examenes = examenesState.data ?? [];
  // Sesiones reales (GET /proctoring/sessions) + tasa de flag derivada del umbral
  // de cola de revisión. null = todavía cargando; [] = sin sesiones → 0 / 0%.
  const [sesiones, setSesiones] = useState<SesionProctoringResumen[] | null>(null);
  // Falló la carga de sesiones. Distinto de `[]` (sin sesiones): un cero real y un
  // cero por caída se veían igual, y el admin no tenía cómo notar la diferencia.
  const [sesionesError, setSesionesError] = useState(false);
  const [umbral, setUmbral] = useState(UMBRAL_REVISION_MIN);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  const [refrescando, setRefrescando] = useState(false);

  const cargarSesiones = useCallback(async () => {
    try {
      await loadEffectiveConfig();
      setUmbral(getEffectiveConfig()?.umbral_cola_revision ?? UMBRAL_REVISION_MIN);
    } catch { /* sin red: umbral por defecto */ }
    try {
      setSesiones(await api.listarSesionesProctoring(true));
      setSesionesError(false);
    } catch {
      // NO se degrada a []: eso pintaba "0 sesiones registradas" con el backend caído.
      setSesionesError(true);
    }
    setLastUpdatedAt(Date.now());
  }, []);

  useEffect(() => { void cargarSesiones(); }, [cargarSesiones]);

  // Recarga completa (catálogo + sesiones) para el botón / auto-refresh cada 5 min.
  const recargar = useCallback(async () => {
    setRefrescando(true);
    examenesState.retry();
    await cargarSesiones();
    setRefrescando(false);
  }, [cargarSesiones, examenesState]);

  useAutoRefresh(recargar, undefined, !refrescando);

  const totalSesiones = sesiones?.length ?? null;
  // F-01 (c-78 D3): se cuenta con el MISMO predicado que usa la Cola de revisión
  // (`entraACola`), no con una condición propia. Antes acá solo se miraba el score,
  // así que las sesiones de diagnóstico sobre el umbral inflaban el número y el
  // Panel mostraba más "en cola" que la propia Cola de revisión para el mismo dato.
  const flagged = sesiones ? sesiones.filter((s) => entraACola(s, umbral)).length : 0;

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
            Desde acá llegás a configurar exámenes y gestión de usuarios. La supervisión
            en vivo y la cola de revisión están en el menú lateral.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          lastUpdatedAt={lastUpdatedAt}
          cargando={refrescando}
          onActualizar={recargar}
        />

        {/* Stat cards con datos reales (catálogo + sesiones de proctoring). Cuando
            no hay sesiones se muestra 0 / 0% (no "—"). */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
          {/* D4: las tres salen del catálogo de métricas (statProps). Un label,
              icono o tono hardcodeado acá es lo que hacía que "Sesiones" y "Cola de
              revisión" significaran cosas distintas según la pantalla. */}
          <StatCard
            {...statProps('examenes', statExamenesValue(examenesState.status, examenes.length))}
          />
          {/* '—' cuando la carga falló: un cero por caída no puede verse igual que
              un cero real. El `sub` DECLARA el alcance (F-02): este panel cuenta
              actividad de CUALQUIER estado, a diferencia de Registro de sesiones,
              que cuenta solo las finalizadas. */}
          <StatCard
            {...statProps(
              'sesiones',
              sesionesError ? '—' : (totalSesiones ?? '…'),
              'registradas, en cualquier estado',
            )}
          />
          <StatCard
            {...statProps(
              'enColaRevision',
              sesionesError ? '—' : sesiones === null ? '…' : flagged,
              'con examen vinculado, sobre el umbral',
            )}
          />
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
                <Link to="/admin/examenes" className="inline-flex items-center gap-1 text-[13px] font-medium text-primary group">
                  <span className="group-hover:underline">Ver todos</span>
                  <Icon name="arrow_forward" className="text-[16px]" />
                </Link>
              </div>
              <div className="divide-y divide-surface-200">
                {examenesState.status === 'loading' ? (
                  <div className="px-lg py-xl flex items-center justify-center">
                    <LoadingSpinner size="sm" label="Cargando exámenes…" />
                  </div>
                ) : examenesState.status === 'error' ? (
                  <div className="px-lg py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
                    <Icon name="error" className="text-[36px] text-error" fill />
                    <p className="text-[14px]">No se pudo cargar el catálogo de exámenes.</p>
                    <button
                      type="button"
                      onClick={examenesState.retry}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-surface-200 bg-white text-[14px] font-medium hover:bg-primary-50"
                    >
                      <Icon name="refresh" className="text-[16px]" /> Reintentar
                    </button>
                  </div>
                ) : examenes.length === 0 ? (
                  <div className="px-lg py-xl flex flex-col items-center text-center gap-md text-on-surface-variant">
                    <Icon name="assignment" className="text-[36px]" />
                    {/* "No hay exámenes" y "no ves ninguno" son cosas distintas.
                        Al docente sin materias/comisiones a cargo el catálogo le
                        vuelve vacío por scoping, y el mensaje genérico lo mandaba
                        a pensar que el sistema estaba sin cargar. */}
                    <p className="text-[14px]">
                      {esInstitucional
                        ? 'Todavía no hay exámenes importados.'
                        : 'No tenés exámenes a cargo. Se ven los de las materias y comisiones que tengas asignadas: si esperabas ver alguno, pedí que te asignen.'}
                    </p>
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
              {accionesRapidas.map((item) => (
                <AccionRapida key={item.to} to={item.to} icon={item.icon} label={item.label} />
              ))}
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
      className="group flex items-center justify-between gap-4 px-lg py-5 hover:bg-primary-50 transition-colors"
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="w-12 h-12 rounded-lg bg-primary-fixed text-primary-700 flex items-center justify-center shrink-0 transition-colors group-hover:bg-primary group-hover:text-on-primary">
          <Icon name="assignment" className="text-[24px]" />
        </div>
        <div className="min-w-0">
          <p className="text-[17px] font-semibold text-on-surface truncate leading-snug">{examen.titulo}</p>
          <p className="text-[14px] text-on-surface-variant truncate leading-snug mt-1">{subtitulo}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-[13px] text-on-surface-variant">
            <span className="inline-flex items-center gap-1 min-w-0">
              <Icon name="event" className="text-[16px] shrink-0" />
              <span className="truncate">{formatVentanaExamen(examen.apertura, examen.cierre)}</span>
            </span>
            <span className="inline-flex items-center gap-1 shrink-0">
              <Icon name="schedule" className="text-[16px]" />
              {formatDuracionExamen(examen.tiempo_limite_min)}
            </span>
          </div>
        </div>
      </div>
      <span className="shrink-0 self-start rounded-full bg-surface-100 px-3 py-1 text-[13px] font-medium text-on-surface-variant tabular-nums">
        {examen.cantidad_preguntas} preguntas
      </span>
    </Link>
  );
}

function AccionRapida({ to, icon, label }: { to: string; icon: string; label: string }) {
  // El ícono va en un chip azul claro en vez de gris suelto: da un punto de color
  // por fila y hace que la columna se lea como accionable y no como texto muerto.
  // El chevron recién se tiñe en hover, para que no compita con el ícono.
  return (
    <Link
      to={to}
      className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-md border border-surface-200 bg-white text-on-surface text-[14px] font-medium hover:bg-primary-50 hover:border-primary-200 transition-colors"
    >
      <span className="w-7 h-7 rounded-md bg-primary-fixed text-primary-700 flex items-center justify-center shrink-0 transition-colors group-hover:bg-primary group-hover:text-on-primary">
        <Icon name={icon} className="text-[16px]" />
      </span>
      <span className="truncate">{label}</span>
      <Icon
        name="chevron_right"
        className="text-[16px] text-on-surface-variant ml-auto shrink-0 transition-colors group-hover:text-primary"
      />
    </Link>
  );
}
