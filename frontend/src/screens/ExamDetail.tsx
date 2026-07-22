import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Card, Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate, useRouteParam } from '../lib/router';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { getExamenHeaderFn } from '../lib/examContentResultados';
import type { ExamenContenidoResumen } from '../lib/types';

import { PreguntasSeleccionSection } from './exam-detail/PreguntasSeleccionSection';
import { ConfiguracionExamenSection } from './exam-detail/ConfiguracionExamenSection';
import { ComisionSection } from './exam-detail/ComisionSection';
import { DestinoMoodleSection } from './exam-detail/DestinoMoodleSection';

// ---------------------------------------------------------------------------
// Stat card del encabezado — mismo tratamiento visual para todas (C-72 §19):
// mismo tamaño, mismo tono de ícono. Antes "Preguntas" tenía fondo de color y las
// otras no; ahora son consistentes.
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  children,
  loading = false,
}: {
  icon: string;
  label: string;
  children: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <Card className="flex items-start gap-sm !p-md">
      <div className="w-10 h-10 rounded-xl bg-surface-container-high text-on-surface-variant flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[20px]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">{label}</p>
        {loading ? (
          // Mientras carga: skeleton, NO un guión. (pref. del owner)
          <div className="mt-1.5 h-5 w-20 max-w-full rounded bg-surface-200 animate-pulse" />
        ) : (
          children
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function ExamDetail() {
  const navigate = useNavigate();
  const examenId = useRouteParam('id');

  const [examen, setExamen] = useState<ExamenContenidoResumen | null>(null);
  const [headerError, setHeaderError] = useState<string | null>(null);

  const cargarHeader = useCallback(() => {
    if (!examenId) return;
    setHeaderError(null);
    getExamenHeaderFn(API_BASE, authProvider.getToken(), examenId)
      .then(setExamen)
      .catch((err: unknown) => setHeaderError(err instanceof Error ? err.message : String(err)));
  }, [examenId]);

  useEffect(() => {
    cargarHeader();
  }, [cargarHeader]);

  // Cargando = todavía sin datos y sin error → las stat cards muestran skeleton.
  const cargando = !examen && !headerError;

  if (!examenId) {
    return (
      <StaffShell nav={STAFF_NAV} title="Detalle de examen">
        <Card>
          <div className="flex items-center gap-sm text-error py-md">
            <Icon name="error" className="text-[20px]" fill />
            <span>No se encontró el ID del examen.</span>
          </div>
        </Card>
      </StaffShell>
    );
  }

  return (
    <StaffShell
      nav={STAFF_NAV}
      title={examen?.titulo ?? 'Detalle de examen'}
      subtitle={
        examen
          ? [examen.materia_nombre, examen.comision_nombre].filter(Boolean).join(' · ') || 'Sin materia / comisión asignada'
          : undefined
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        <Button variant="ghost" icon="arrow_back" size="sm" onClick={() => navigate('/admin/examenes')}>
          Volver a la lista
        </Button>

        {/* Header stats — tarjetas consistentes */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-md">
          <StatCard icon="quiz" label="Preguntas" loading={cargando}>
            <p className="font-headline text-title-lg text-on-surface tabular-nums">
              {examen?.cantidad_preguntas ?? 0}
            </p>
          </StatCard>
          <StatCard icon="menu_book" label="Materia" loading={cargando}>
            <p className="text-label-md text-on-surface truncate">
              {examen?.materia_nombre ?? <span className="text-outline italic">Sin materia</span>}
            </p>
          </StatCard>
          <div className="col-span-2 sm:col-span-1">
            <StatCard icon="group" label="Comisión" loading={cargando}>
              <p className="text-label-md text-on-surface truncate">
                {examen?.comision_nombre ?? <span className="text-outline italic">Sin comisión</span>}
              </p>
            </StatCard>
          </div>
        </div>

        {headerError && (
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            No se pudo cargar el encabezado del examen: {headerError}
          </div>
        )}

        <PreguntasSeleccionSection
          examenId={examenId}
          onSeleccionGuardada={(cantidad) =>
            setExamen((prev) => (prev ? { ...prev, cantidad_preguntas: cantidad } : prev))
          }
        />

        <ComisionSection
          examenId={examenId}
          materiaActual={examen?.materia_nombre}
          comisionActual={examen?.comision_nombre}
          onAsociada={cargarHeader}
        />

        <DestinoMoodleSection examenId={examenId} />

        <ConfiguracionExamenSection examenId={examenId} />

        {/* Acceso a la página dedicada de resultados (antes era una tabla al final). */}
        <Card className="flex items-center justify-between gap-md flex-wrap">
          <div className="flex items-center gap-sm min-w-0">
            <div className="w-10 h-10 rounded-xl bg-surface-container-high text-on-surface-variant flex items-center justify-center shrink-0">
              <Icon name="groups" className="text-[20px]" />
            </div>
            <div className="min-w-0">
              <p className="text-title-sm font-semibold text-on-surface">Alumnos que rindieron</p>
              <p className="text-label-sm text-on-surface-variant">
                Resultados, notas y sincronización con Moodle.
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            iconRight="arrow_forward"
            onClick={() => navigate(`/admin/examenes/${examenId}/resultados`)}
          >
            Ver alumnos que rindieron
          </Button>
        </Card>
      </div>
    </StaffShell>
  );
}
