/**
 * Revisor — Cola de revisión humana, navegación drill-down jerárquica.
 *
 * Ruta: /revisor. Toma las sesiones de proctoring REALES
 * (api.listarSesionesProctoring(), dual real/mock), las filtra por ALTO RIESGO
 * (score ≥ UMBRAL_COLA_REVISION) y las organiza por la jerarquía académica:
 * Materia → Comisión → Examen → Persona. Cada nivel muestra un contador "N en
 * riesgo"; un breadcrumb clickable permite volver a cualquier nivel.
 *
 * El sistema NUNCA sanciona automáticamente: el score solo prioriza/ordena. La
 * decisión disciplinaria es siempre del revisor humano (registrada en el store).
 * Ley 25.326: ningún nivel lista screenshots; el dato sensible vive solo en
 * ProctoringSessionDetail.
 */
import { useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button } from '../ui/components';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import type { DecisionRevisor } from '../lib/types';
import { ColaBreadcrumb, type ColaPath, type ColaNivel } from './proctoring/ColaBreadcrumb';
import { ColaNivelGrid } from './proctoring/ColaNivelGrid';
import { ColaNivelPersonas } from './proctoring/ColaNivelPersonas';
import {
  enriquecerYFiltrar,
  materiasEnRiesgo,
  comisionesEnRiesgo,
  examenesEnRiesgo,
  personasEnRiesgo,
  type SesionEnriquecida,
} from './proctoring/colaAgregacion';

export const REVISOR_NAV = STAFF_NAV;

/** Score mínimo para que una sesión aparezca en la cola de revisión priorizada. */
const UMBRAL_COLA_REVISION = 60;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/** Etiqueta legible de cada decisión (para el toast de confirmación). */
const DECISION_LABEL: Record<DecisionRevisor, string> = {
  sin_hallazgos: 'Sin observaciones',
  aprobado: 'Aprobada con nota',
  flaggeado_para_sumario: 'Enviada a revisión formal',
  pendiente: 'Pendiente',
};

export default function Revisor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setDecisionRevisor = useApp((s) => s.setDecisionRevisor);

  const [items, setItems] = useState<SesionEnriquecida[]>([]);
  const [cargando, setCargando] = useState(true);
  const [path, setPath] = useState<ColaPath>({});
  const [personaSelId, setPersonaSelId] = useState<string | null>(null);

  useEffect(() => {
    setCargando(true);
    api
      .listarSesionesProctoring()
      .then((data) => setItems(enriquecerYFiltrar(data, UMBRAL_COLA_REVISION)))
      .catch(() => setItems([]))
      .finally(() => setCargando(false));
  }, []);

  // Navegación del breadcrumb: recorta el path al nivel pedido.
  const irA = (nivel: ColaNivel) => {
    setPersonaSelId(null);
    if (nivel === 'raiz') setPath({});
    else if (nivel === 'materia') setPath((p) => ({ materia: p.materia }));
    else setPath((p) => ({ materia: p.materia, comision: p.comision }));
  };

  // Botón "Volver": sube un nivel del path.
  const volver = () => {
    setPersonaSelId(null);
    setPath((p) => {
      if (p.examen) return { materia: p.materia, comision: p.comision };
      if (p.comision) return { materia: p.materia };
      if (p.materia) return {};
      return {};
    });
  };

  const resolver = (id: string, decision: DecisionRevisor) => {
    setDecisionRevisor(id, decision);
    toast.success(
      `Decisión registrada: ${DECISION_LABEL[decision]}. El score prioriza; el revisor decide.`,
    );
    setItems((prev) => prev.filter((i) => i.sesion.id !== id));
    setPersonaSelId(null);
  };

  const verDetalle = (id: string) => {
    setProctoringSessionId(id);
    navigate(PROCTORING_DETAIL_ROUTE);
  };

  const personas = useMemo(
    () =>
      path.materia && path.comision && path.examen
        ? personasEnRiesgo(items, path.materia, path.comision, path.examen)
        : [],
    [items, path],
  );

  const hayRiesgo = items.length > 0;
  const enRaiz = !path.materia;

  return (
    <StaffShell nav={REVISOR_NAV} title="Cola de revisión">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Cola de revisión
            </h1>
            <p className="text-body-md text-on-surface-variant mt-base max-w-2xl">
              Sesiones de alto riesgo (score ≥ {UMBRAL_COLA_REVISION}) organizadas por materia,
              comisión y examen. Entrá hasta cada persona para revisar y decidir. El sistema
              nunca sanciona: la decisión es siempre tuya.
            </p>
          </div>
          <div className="flex items-center gap-base px-sm py-base rounded-lg bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant shrink-0">
            <Icon name="shield" className="text-[16px] shrink-0" fill />
            <span>Decisión humana</span>
          </div>
        </div>

        {cargando && (
          <Card className="text-center py-xl text-on-surface-variant space-y-base">
            <Icon name="hourglass_empty" className="text-[32px] animate-pulse" />
            <p className="text-label-md">Cargando cola…</p>
          </Card>
        )}

        {!cargando && !hayRiesgo && (
          <Card className="text-center py-xl space-y-base">
            <Icon name="task_alt" className="text-success text-[48px]" fill />
            <h3 className="font-headline text-title-lg text-on-surface">¡Cola limpia!</h3>
            <p className="text-body-md text-on-surface-variant">
              No hay sesiones con score ≥ {UMBRAL_COLA_REVISION} pendientes de revisión.
            </p>
          </Card>
        )}

        {!cargando && hayRiesgo && (
          <>
            {/* Breadcrumb + volver, en su propia fila */}
            <div className="flex items-center gap-md flex-wrap">
              {!enRaiz && (
                <Button variant="ghost" size="sm" icon="arrow_back" onClick={volver}>
                  Volver
                </Button>
              )}
              <div className="flex-1 min-w-0">
                <ColaBreadcrumb path={path} onNavigate={irA} />
              </div>
            </div>

            {/* Nivel 1 — Materias */}
            {enRaiz && (
              <ColaNivelGrid
                titulo="Materias con sesiones en riesgo"
                sub="Elegí una materia para ver sus comisiones."
                icono="menu_book"
                nodos={materiasEnRiesgo(items)}
                onSelect={(materia) => {
                  setPersonaSelId(null);
                  setPath({ materia });
                }}
              />
            )}

            {/* Nivel 2 — Comisiones */}
            {path.materia && !path.comision && (
              <ColaNivelGrid
                titulo="Comisiones con sesiones en riesgo"
                sub={`Comisiones de ${path.materia}. Elegí una para ver sus exámenes.`}
                icono="groups"
                nodos={comisionesEnRiesgo(items, path.materia)}
                onSelect={(comision) => {
                  setPersonaSelId(null);
                  setPath((p) => ({ ...p, comision }));
                }}
              />
            )}

            {/* Nivel 3 — Exámenes */}
            {path.materia && path.comision && !path.examen && (
              <ColaNivelGrid
                titulo="Exámenes con sesiones en riesgo"
                sub={`Exámenes de ${path.comision}. Elegí uno para ver a las personas.`}
                icono="assignment"
                nodos={examenesEnRiesgo(items, path.materia, path.comision)}
                onSelect={(examen) => {
                  setPersonaSelId(null);
                  setPath((p) => ({ ...p, examen }));
                }}
              />
            )}

            {/* Nivel 4 — Personas en riesgo */}
            {path.materia && path.comision && path.examen && (
              <ColaNivelPersonas
                personas={personas}
                selId={personaSelId}
                onSeleccionar={setPersonaSelId}
                onResolver={resolver}
                onVerDetalle={verDetalle}
              />
            )}
          </>
        )}
      </div>
    </StaffShell>
  );
}
