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
import { useCallback, useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { RefreshBar } from '../ui/RefreshBar';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { Icon, Card, Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../config/effectiveConfigCache';
import { UMBRAL_REVISION_MIN } from '../config/umbralRevision';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { STAFF_NAV } from '../ui/nav';
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
const UMBRAL_FALLBACK = UMBRAL_REVISION_MIN;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/**
 * Preservación de navegación (C-72 backlog UX #5). Al ir a "Ver detalle completo"
 * el componente se desmonta; sin esto, al volver caías en el nivel raíz (Materias)
 * en vez de donde estabas. Guardamos el nivel + la persona seleccionada y los
 * restauramos UNA sola vez (restore-once): así el ida-y-vuelta al detalle preserva
 * el contexto, pero una entrada fresca desde el menú lateral arranca en la raíz.
 */
const NAV_KEY = 'revisor:nav';
/** Cola de casos del examen abierto: permite pasar al siguiente desde el detalle
 *  sin volver a la lista. Se guarda al abrir un caso y la lee SessionDetail. */
export const COLA_KEY = 'revisor:cola';

function leerNavGuardada(): { path: ColaPath; personaSelId: string | null } | null {
  try {
    const raw = sessionStorage.getItem(NAV_KEY);
    return raw ? (JSON.parse(raw) as { path: ColaPath; personaSelId: string | null }) : null;
  } catch {
    return null;
  }
}


export default function Revisor() {
  const navigate = useNavigate();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);

  const [items, setItems] = useState<SesionEnriquecida[]>([]);
  const [umbral, setUmbral] = useState(UMBRAL_FALLBACK);
  // El admin ve la cola institucional; el coordinador solo la de SUS materias.
  // Cambia qué significa que vuelva vacía.
  const esInstitucional = (useAuth((s) => s.principal?.roles) ?? []).includes(
    'admin_sistema',
  );
  const [cargando, setCargando] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  // Restauramos el nivel/persona si venimos de "Ver detalle completo" (restore-once).
  const [path, setPath] = useState<ColaPath>(() => leerNavGuardada()?.path ?? {});
  const [personaSelId, setPersonaSelId] = useState<string | null>(
    () => leerNavGuardada()?.personaSelId ?? null,
  );

  useEffect(() => {
    // Ya restauramos la navegación en los initializers; consumimos la clave para
    // que sea restore-once (una entrada fresca desde el menú arranca en la raíz).
    try { sessionStorage.removeItem(NAV_KEY); } catch { /* ignore */ }
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
        const enriched = enriquecerYFiltrar(data, u);
        setItems(enriched);
        setLastUpdatedAt(Date.now());
        // #8: entrada fresca (no venimos del detalle) → saltamos los niveles de una
        // sola opción para acortar el recorrido hasta las personas en riesgo.
        // No auto-colapsamos: el usuario siempre arranca en la raíz (Materias).
        // El auto-colapso generaba confusión al mostrar el breadcrumb completo
        // en el primer render sin que el usuario hubiera navegado nada.
      } catch {
        setItems([]);
      } finally {
        setCargando(false);
      }
    })();
  }, []);

  // Recarga liviana para el botón / auto-refresh: re-trae las sesiones y re-filtra
  // con el umbral vigente, SIN colapsar el árbol ni tocar la navegación actual.
  const recargarSesiones = useCallback(async () => {
    setRefrescando(true);
    try {
      const data = await api.listarSesionesProctoring();
      setItems(enriquecerYFiltrar(data, umbral));
      setLastUpdatedAt(Date.now());
    } catch { /* mantiene lo que había */ }
    finally { setRefrescando(false); }
  }, [umbral]);

  // Auto-refresh cada 5 min: la cola cambia a medida que se rinden exámenes.
  useAutoRefresh(recargarSesiones, undefined, !cargando);

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


  const verDetalle = (id: string) => {
    // Guardamos el nivel + la persona para restaurarlos al volver del detalle (#5).
    try {
      sessionStorage.setItem(NAV_KEY, JSON.stringify({ path, personaSelId: id }));
    } catch { /* ignore */ }
    setProctoringSessionId(id);
    setProctoringDetailBackRoute('/admin/cola-revision');
    navigate(PROCTORING_DETAIL_ROUTE + '/' + id);
  };

  /**
   * Elegir a una persona lleva DIRECTO al detalle, con la decisión ahí.
   *
   * Antes abría un panel lateral y el detalle era otro click aparte. Para anular
   * hay que mirar la evidencia — las capturas ahora dicen de qué señal son y
   * cuándo — y ese panel angosto invitaba a decidir sin abrirla. La decisión
   * además es inmutable: merece la pantalla completa, no un costado.
   *
   * Se lleva la COLA de ids del examen actual: en el detalle se recorre caso por
   * caso sin volver a la lista. Con 20 personas en riesgo, obligar a volver
   * después de cada una convierte la revisión en un trámite de clicks.
   */
  const abrirCaso = (id: string) => {
    try {
      sessionStorage.setItem(
        COLA_KEY,
        JSON.stringify({ ids: personas.map((p) => p.sesion.id), actual: id }),
      );
    } catch { /* ignore */ }
    verDetalle(id);
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
          {/* Eran tres opciones y una no existe: el modelo tiene DOS decisiones
              terminales (`DecisionSesion`: aprobado / anulado) y no hay segunda
              instancia — ver `DecisionRevisorForm`, que muestra exactamente
              "Aprobar con nota" y "Anular examen". */}
          <p>
            La cola se organiza por <em>Materia → Comisión → Examen → Persona</em>. Entrá hasta
            cada persona para revisar la evidencia y registrar tu decisión, que es una de dos:
            <strong> aprobar con nota</strong> (la nota vale y se envía al campus) o
            <strong> anular el examen</strong> (con motivo y evidencia obligatorios).
          </p>
          <p>
            El sistema <strong>nunca sanciona automáticamente</strong>: el score solo prioriza,
            la decisión disciplinaria siempre es tuya.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Cola de revisión"
          lastUpdatedAt={lastUpdatedAt}
          cargando={refrescando}
          onActualizar={recargarSesiones}
        />

        {cargando && (
          <Card className="text-center py-xl text-on-surface-variant space-y-base">
            <Icon name="progress_activity" className="text-[32px] ae-spin" />
            <p className="text-label-md">Cargando cola…</p>
          </Card>
        )}

        {/* "No hay nada que revisar" y "no ves nada" son cosas distintas, y acá
            la diferencia importa: la cola le vuelve vacía al coordinador que no
            tiene materias asignadas, y el tilde verde le afirmaba que estaba
            todo en orden mientras podía haber sesiones en riesgo que no ve. */}
        {!cargando && !hayRiesgo && (
          <Card className="text-center py-xl space-y-base">
            <Icon
              name={esInstitucional ? 'check_circle' : 'info'}
              className={esInstitucional ? 'text-success text-[44px]' : 'text-warning text-[44px]'}
              fill
            />
            <h3 className="font-headline text-title-lg text-on-surface">
              {esInstitucional ? 'Sin sesiones pendientes' : 'No hay nada en tu cola'}
            </h3>
            <p className="text-body-md text-on-surface-variant">
              {esInstitucional
                ? 'Nada que revisar por ahora.'
                : 'Se revisan las sesiones de las materias que coordinás. Si no tenés ninguna asignada, no vas a ver nada acá aunque haya exámenes en riesgo.'}
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
                // Un solo click abre el caso en el detalle: la lista es para
                // ELEGIR a quién revisar, el detalle para DECIDIR.
                onSeleccionar={abrirCaso}
              />
            )}
          </>
        )}
      </div>
    </StaffShell>
  );
}
