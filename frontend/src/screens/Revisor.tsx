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
import { HelpButton } from '../ui/HelpButton';
import { api } from '../lib/api';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../config/effectiveConfigCache';
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

/** Umbral por defecto si la config efectiva del sistema no cargó. */
const UMBRAL_FALLBACK = 70;
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
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);
  const setDecisionRevisor = useApp((s) => s.setDecisionRevisor);

  const [items, setItems] = useState<SesionEnriquecida[]>([]);
  const [umbral, setUmbral] = useState(UMBRAL_FALLBACK);
  const [cargando, setCargando] = useState(true);
  const [path, setPath] = useState<ColaPath>({});
  const [personaSelId, setPersonaSelId] = useState<string | null>(null);

  useEffect(() => {
    setCargando(true);
    (async () => {
      // El umbral de la cola sale de la config del sistema (no un valor fijo).
      // Invalidamos el cache al montar para que SIEMPRE veamos el valor actual,
      // incluso si el admin cambió el umbral desde otra pestaña / sesión.
      let u = UMBRAL_FALLBACK;
      try {
        resetEffectiveConfigCache();
        await loadEffectiveConfig();
        u = getEffectiveConfig()?.umbral_cola_revision ?? UMBRAL_FALLBACK;
      } catch { /* usa el fallback */ }
      setUmbral(u);
      try {
        const data = await api.listarSesionesProctoring();
        setItems(enriquecerYFiltrar(data, u));
      } catch {
        setItems([]);
      } finally {
        setCargando(false);
      }
    })();
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
    setProctoringDetailBackRoute('/revisor');
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
    <StaffShell
      nav={REVISOR_NAV}
      title="Cola de revisión"
      subtitle={`Sesiones que superan ${umbral} pts de riesgo, por materia, comisión y examen.`}
      help={
        <HelpButton title="Cola de revisión">
          <p>
            Esta pantalla concentra las sesiones que <strong>priorizan revisión humana</strong>:
            solo las que alcanzan o superan el umbral de riesgo ({umbral} puntos).
          </p>
          <p>
            La cola se organiza por <em>Materia → Comisión → Examen → Persona</em>. Entrá hasta
            cada persona para revisar evidencia y registrar tu decisión (sin observaciones,
            aprobada con nota o enviada a revisión formal).
          </p>
          <p>
            El sistema <strong>nunca sanciona automáticamente</strong>: el score solo prioriza,
            la decisión disciplinaria siempre es tuya.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        {cargando && (
          <Card className="text-center py-xl text-on-surface-variant space-y-base">
            <Icon name="hourglass_empty" className="text-[32px] animate-pulse" />
            <p className="text-label-md">Cargando cola…</p>
          </Card>
        )}

        {!cargando && !hayRiesgo && (
          <Card className="text-center py-xl space-y-base">
            <Icon name="check_circle" className="text-success text-[44px]" fill />
            <h3 className="font-headline text-title-lg text-on-surface">Sin sesiones pendientes</h3>
            <p className="text-body-md text-on-surface-variant">
              Nada que revisar por ahora.
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
