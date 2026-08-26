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
import { ComisionesDelExamenSection } from './exam-detail/ComisionesDelExamenSection';
import { BorradorSection } from './exam-detail/BorradorSection';
import { SorteoSection } from './exam-detail/SorteoSection';
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
    <Card className="flex items-center gap-md !p-lg">
      <div className="w-11 h-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[22px]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">{label}</p>
        {loading ? (
          <div className="mt-1.5 h-6 w-24 max-w-full rounded bg-surface-200 animate-pulse" />
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
            <p className="font-headline text-display-sm text-on-surface tabular-nums leading-tight mt-0.5">
              {examen?.cantidad_preguntas ?? 0}
            </p>
          </StatCard>
          <StatCard icon="menu_book" label="Materia" loading={cargando}>
            <p className="text-title-sm font-semibold text-on-surface truncate mt-0.5">
              {examen?.materia_nombre ?? <span className="text-outline font-normal italic">Sin materia</span>}
            </p>
          </StatCard>
          <div className="col-span-2 sm:col-span-1">
            <StatCard icon="group" label="Comisión" loading={cargando}>
              <p className="text-title-sm font-semibold text-on-surface truncate mt-0.5">
                {examen?.comision_nombre ?? <span className="text-outline font-normal italic">Sin comisión</span>}
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

        {/* c-78 E-07: va PRIMERO. Que el examen no esté habilitado es lo más
            importante que hay que saber al abrirlo. */}
        {examen?.borrador && (
          <BorradorSection
            examenId={examenId}
            titulo={examen?.titulo}
            onHabilitado={cargarHeader}
          />
        )}

        {/* c-78 E-07: si el examen sortea por intento, esta sección explica qué
            recibe cada alumno. Se pinta sola cuando no aplica. */}
        <SorteoSection examenId={examenId} />

        <PreguntasSeleccionSection
          examenId={examenId}
          materiaId={examen?.materia_id}
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

        <ComisionesDelExamenSection
          examenId={examenId}
          materiaId={examen?.materia_id}
          onCambio={cargarHeader}
        />

        <DestinoMoodleSection examenId={examenId} />

        <ConfiguracionExamenSection examenId={examenId} />
      </div>
    </StaffShell>
  );
}
