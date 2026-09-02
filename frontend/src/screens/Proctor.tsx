/**
 * Proctor — Supervisión EN VIVO de sesiones de proctoring (conectada al backend).
 *
 * Ruta: /proctor (nav: "Supervisión en vivo"). Sondea el backend activeexam cada
 * POLL_MS vía api.listarSesionesProctoring() (dual real/mock) y muestra las
 * sesiones ordenadas por score descendente: las de mayor riesgo, arriba.
 *
 * Tiempo real por polling: setInterval con cleanup en el unmount (sin acumular
 * timers). Degradación silenciosa: si un refresh falla, se muestra un toast pero
 * el loop sigue vivo y se mantiene la última data visible.
 *
 * L2.5: el score PRIORIZA para revisión humana, nunca sanciona. Click en una
 * sesión abre su detalle para la decisión humana asíncrona.
 * Ley 25.326: este panel solo lista metadatos agregados; no toca screenshots.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Icon, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { api } from '../lib/api';
import { loadEffectiveConfig, getEffectiveConfig } from '../config/effectiveConfigCache';
import type { SesionProctoringResumen } from '../lib/types';
import { SesionVivoCard } from './proctoring/SesionVivoCard';
import { ExamenVivoGroup } from './proctoring/ExamenVivoGroup';
import { ResumenVivo } from './proctoring/ResumenVivo';
import { ListaSkeleton, ListaVaciaVivo } from './proctoring/ListaEstados';
import { IndicadorVivo } from './proctoring/IndicadorVivo';
import { type ExamInfo } from './proctoring/helpers';
import { examInfoDeSesion } from './proctoring/colaAgregacion';
import { coincideBusqueda } from './proctoring/persona';
import { PausasPendientes } from './proctoring/PausasPendientes';

export const PROCTOR_NAV = STAFF_NAV;

/** Intervalo de polling del panel en vivo (ms). */
const POLL_MS = 4000;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/** Ordena por score desc (mayor riesgo arriba); desempata por más eventos. */
function ordenarPorRiesgo(sesiones: SesionProctoringResumen[]): SesionProctoringResumen[] {
  return [...sesiones].sort(
    (a, b) => b.score - a.score || b.total_eventos - a.total_eventos,
  );
}

export default function Proctor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringExamId = useApp((s) => s.setProctoringExamId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);
  // Identidad del proctor logueado → se registra como tutor_actor al resolver
  // una pausa (C-15). Email como subject estable; null si no hay sesión.
  const tutorActor = useAuth((s) => s.principal?.email ?? null);

  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargaInicial, setCargaInicial] = useState(true);
  // Filtros de vista (c-78 §11.3). Borrador → aplicado, igual que el resto de
  // las pantallas de listado.
  const [borrMateria, setBorrMateria] = useState('');
  const [borrComision, setBorrComision] = useState('');
  const [borrExamen, setBorrExamen] = useState('');
  const [filtros, setFiltros] = useState({ materia: '', comision: '', examen: '' });
  // Buscar a UNA persona. Separado del panel de filtros a propósito: ese panel no
  // se le muestra al tutor, y filtra por materia/comisión, que es lo que el tutor
  // ya tiene fijo. Lo que le falta es encontrar a alguien entre 40 rindiendo, y
  // eso se resuelve tipeando, sin botón de "Aplicar" en el medio.
  const [buscaPersona, setBuscaPersona] = useState('');
  // C-69 admin-sync: si el admin desactivó las pausas, no se muestra la cola de
  // solicitudes. Default `true` (degradación segura).
  const [pausasHabilitadas, setPausasHabilitadas] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const [ultimoRefresh, setUltimoRefresh] = useState<number | null>(null);

  // Evita refrescos solapados (el manual y el del intervalo) y stale closures.
  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refrescar = useCallback(async (manual: boolean) => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    if (manual) setRefrescando(true);
    try {
      const data = await api.listarSesionesProctoring();
      // Supervisión EN VIVO: solo sesiones que todavía no fueron finalizadas.
      // Las cerradas (finalizada_en != null) viven en /admin/proctoring-sessions.
      const enVivo = data.filter((s) => !s.finalizada_en);
      setSesiones(ordenarPorRiesgo(enVivo));
      setUltimoRefresh(Date.now());
    } catch {
      // Degradación silenciosa: avisamos pero NO rompemos el loop ni borramos
      // la última data visible. El próximo tick reintenta solo.
      toastRef.current.error('No se pudieron actualizar las sesiones en vivo');
    } finally {
      enVuelo.current = false;
      if (manual) setRefrescando(false);
      setCargaInicial(false);
    }
  }, []);

  // Polling con cleanup: una sola carga inicial + un único intervalo que se
  // limpia en el unmount (sin acumular timers entre renders).
  // Antes del primer refresh, sembramos la config efectiva (umbral_cola_revision)
  // para que el "Riesgo alto (≥X)" refleje lo que el admin configuró y no quede
  // hardcodeado en 70.
  useEffect(() => {
    void loadEffectiveConfig().then(() => {
      const cfg = getEffectiveConfig();
      if (cfg) setPausasHabilitadas(cfg.pausas_habilitadas);
    });
    void refrescar(false);
    const id = setInterval(() => void refrescar(false), POLL_MS);
    return () => clearInterval(id);
  }, [refrescar]);

  // Al cambiar de materia, la comisión elegida deja de tener sentido.
  useEffect(() => {
    setBorrComision('');
  }, [borrMateria]);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    // "Volver" del detalle regresa acá (supervisión en vivo), no a grabadas.
    setProctoringDetailBackRoute('/proctor');
    navigate(PROCTORING_DETAIL_ROUTE + '/' + sesion.id);
  };

  const handleAbrirExamen = (examId: string) => {
    setProctoringExamId(examId);
    navigate('/proctor/examen');
  };

  // Particiona por modo y AGRUPA los exámenes por exam_id: primero el examen
  // concreto que se está rindiendo, y dentro sus personas (arquitectura correcta).
  // Las sesiones modo='examen' sin exam_id (legacy / orfanas) se separan: no son
  // exámenes reales ni pruebas — confunden al proctor si se mezclan con cualquiera
  // de los dos.
  // Filtro de VISTA sobre lo que el backend ya acotó por pertenencia. Se aplica
  // sobre los nombres resueltos server-side (materia_nombre/comision_nombre),
  // que son los mismos que alimentan el agrupado.
  const sesionesVisibles = useMemo(() => {
    const textoExamen = filtros.examen.trim().toLowerCase();
    return sesiones.filter((s) => {
      if (filtros.materia && s.materia_nombre !== filtros.materia) return false;
      if (filtros.comision && s.comision_nombre !== filtros.comision) return false;
      if (textoExamen && !(s.examen_titulo ?? '').toLowerCase().includes(textoExamen)) {
        return false;
      }
      // Buscador de PERSONA: aplica a todos los roles.
      if (!coincideBusqueda(s, buscaPersona)) return false;
      return true;
    });
  }, [sesiones, filtros, buscaPersona]);

  // Opciones de filtro derivadas de las sesiones que la persona REALMENTE ve (el
  // backend ya las acotó por pertenencia). Antes salían de un catálogo pedido por
  // API y solo se le mostraban al coordinador/profesor/admin, con lo cual el tutor
  // con DOS comisiones no tenía forma de mirar una sola. Derivarlas de las sesiones
  // arregla las dos cosas: el tutor las tiene, y nadie ve una opción que no le
  // devolvería nada.
  const opcionesMateria = useMemo(
    () => [...new Set(sesiones.map((s) => s.materia_nombre).filter(Boolean))].sort() as string[],
    [sesiones],
  );
  const opcionesComision = useMemo(
    () =>
      [
        ...new Set(
          sesiones
            .filter((s) => !borrMateria || s.materia_nombre === borrMateria)
            .map((s) => s.comision_nombre)
            .filter(Boolean),
        ),
      ].sort() as string[],
    [sesiones, borrMateria],
  );
  // Con una sola materia y una sola comisión no hay nada que elegir: el selector
  // sería una caja con una única opción. Es el caso del tutor de una comisión.
  const hayQueElegir = opcionesMateria.length > 1 || opcionesComision.length > 1;

  const { gruposExamen, diagnostico, otras } = useMemo(() => {
    const examen: SesionProctoringResumen[] = [];
    const diagnostico: SesionProctoringResumen[] = [];
    const otras: SesionProctoringResumen[] = [];
    for (const s of sesionesVisibles) {
      if (s.modo === 'examen') {
        // Sin exam_id no podemos joinear con el catálogo académico: tratamos
        // la sesión como huérfana y la mostramos en la sección "Otras" para
        // que no se confunda con un examen real ni con una prueba.
        if (!s.exam_id) otras.push(s);
        else examen.push(s);
      } else if (s.modo === 'diagnostico') diagnostico.push(s);
      else otras.push(s);
    }

    // Agrupa las sesiones de examen por exam_id.
    const porExamen = new Map<string, { examInfo: ExamInfo | null; sesiones: SesionProctoringResumen[] }>();
    for (const s of examen) {
      const key = s.exam_id!;
      if (!porExamen.has(key)) porExamen.set(key, { examInfo: examInfoDeSesion(s), sesiones: [] });
      porExamen.get(key)!.sesiones.push(s);
    }
    // Ordena los grupos por su riesgo máximo (el examen más caliente, arriba).
    const gruposExamen = [...porExamen.entries()]
      .map(([examId, g]) => ({ examId, ...g, riesgoMax: Math.max(...g.sesiones.map((s) => s.score)) }))
      .sort((a, b) => b.riesgoMax - a.riesgoMax);

    return { gruposExamen, diagnostico, otras };
  }, [sesionesVisibles]);

  const examenesActivos = gruposExamen.length;

  return (
    <StaffShell
      nav={PROCTOR_NAV}
      title="Supervisión en vivo"
      subtitle="Los exámenes con mayor riesgo se muestran primero."
      help={
        <HelpButton title="Supervisión en vivo">
          <p>
            Acá ves las sesiones de proctoring <strong>en curso</strong> agrupadas por examen.
            Las sesiones que ya finalizaron viven en <em>Registro de sesiones</em>.
          </p>
          <p>
            Los exámenes con mayor riesgo aparecen arriba. Click en un examen para ver el grid
            de personas; click en una persona para abrir su detalle y revisar evidencia.
          </p>
        </HelpButton>
      }
      actions={
        <>
          <IndicadorVivo ultimoRefresh={ultimoRefresh} activo={!refrescando} />
          <Button
            variant="outline"
            size="sm"
            icon="refresh"
            onClick={() => void refrescar(true)}
            disabled={refrescando}
          >
            {refrescando ? 'Actualizando…' : 'Actualizar'}
          </Button>
        </>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        {/* Resumen agregado del lote actual — va PRIMERO (las métricas del panel
            arriba de todo, antes de la cola de solicitudes de pausa). */}
        {!cargaInicial && sesionesVisibles.length > 0 && <ResumenVivo sesiones={sesionesVisibles} />}

        {/* Buscador de persona: para TODOS los roles. El tutor no tiene el panel
            de filtros de abajo, así que sin esto no tenía ninguna forma de
            encontrar a alguien salvo scrollear las tarjetas a ojo. */}
        <div className="flex items-center gap-sm">
          <div className="relative flex-1 max-w-md">
            <Icon
              name="search"
              className="absolute left-sm top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant pointer-events-none"
            />
            <input
              type="search"
              value={buscaPersona}
              onChange={(e) => setBuscaPersona(e.target.value)}
              placeholder="Buscar persona por nombre o correo…"
              aria-label="Buscar persona"
              className="w-full rounded-xl border border-outline-variant/60 bg-surface-container-lowest
                pl-9 pr-md py-sm text-body-md text-on-surface
                focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            />
          </div>
          {buscaPersona.trim() !== '' && (
            <span className="text-label-sm text-on-surface-variant whitespace-nowrap">
              {sesionesVisibles.length} de {sesiones.length}
            </span>
          )}
        </div>

        {/* El filtro se muestra a CUALQUIERA que tenga más de una materia o
            comisión en pantalla, tutor incluido: con dos comisiones a cargo,
            mirar una sola es exactamente lo que hace falta. Con una sola de cada
            una no se muestra: sería una caja con una única opción.
            Es filtro de VISTA: nunca amplía el alcance, el backend ya devolvió
            solo lo que la persona puede ver. */}
        {hayQueElegir && (
          <FiltrosPanel
            onAplicar={() =>
              setFiltros({
                materia: borrMateria,
                comision: borrComision,
                examen: borrExamen.trim(),
              })
            }
            onLimpiar={() => {
              setBorrMateria('');
              setBorrComision('');
              setBorrExamen('');
              setFiltros({ materia: '', comision: '', examen: '' });
            }}
            hayFiltros={Boolean(borrMateria || borrComision || borrExamen)}
            hayCambios={
              borrMateria !== filtros.materia ||
              borrComision !== filtros.comision ||
              borrExamen.trim() !== filtros.examen
            }
          >
            {opcionesMateria.length > 1 && (
              <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
                Materia
                <select
                  value={borrMateria}
                  onChange={(e) => setBorrMateria(e.target.value)}
                  className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
                >
                  <option value="">Todas las materias</option>
                  {opcionesMateria.map((nombre) => (
                    <option key={nombre} value={nombre}>{nombre}</option>
                  ))}
                </select>
              </label>
            )}
            {opcionesComision.length > 1 && (
              <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
                Comisión
                <select
                  value={borrComision}
                  onChange={(e) => setBorrComision(e.target.value)}
                  className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
                >
                  <option value="">Todas las comisiones</option>
                  {opcionesComision.map((nombre) => (
                    <option key={nombre} value={nombre}>{nombre}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Examen
              <input
                type="text"
                value={borrExamen}
                placeholder="Nombre del examen…"
                onChange={(e) => setBorrExamen(e.target.value)}
                className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              />
            </label>
          </FiltrosPanel>
        )}

        {/* C-15: cola de solicitudes de pausa (poll propio; se oculta si no hay).
            C-69 admin-sync: se oculta del todo si el admin desactivó las pausas. */}
        {pausasHabilitadas && <PausasPendientes tutorActor={tutorActor} />}

        {/* Barra de estado del polling (sin card) */}
        <div className="flex items-center justify-between gap-md text-label-sm text-on-surface-variant">
          <span>
            {cargaInicial
              ? 'Conectando…'
              : `${sesionesVisibles.length} ${sesionesVisibles.length === 1 ? 'sesión' : 'sesiones'} en vivo`}
          </span>
          <span className="inline-flex items-center gap-base">
            <Icon name="bolt" className="text-[16px]" />
            actualiza cada {POLL_MS / 1000}s
          </span>
        </div>

        {cargaInicial && <ListaSkeleton />}

        {!cargaInicial && sesionesVisibles.length === 0 && <ListaVaciaVivo />}

        {!cargaInicial && sesionesVisibles.length > 0 && (
          <div className="space-y-xl">
            {gruposExamen.length > 0 && (
              <section className="space-y-md">
                <SectionTitle
                  sub={`${examenesActivos} ${examenesActivos === 1 ? 'examen activo' : 'exámenes activos'}`}
                >
                  Exámenes en curso
                </SectionTitle>
                <div className="space-y-md">
                  {gruposExamen.map((g) => (
                    <ExamenVivoGroup
                      key={g.examId}
                      examInfo={g.examInfo}
                      sesiones={g.sesiones}
                      onAbrir={handleAbrir}
                      onAbrirExamen={handleAbrirExamen}
                    />
                  ))}
                </div>
              </section>
            )}

            {diagnostico.length > 0 && (
              <section className="space-y-md">
                <SectionTitle sub={`${diagnostico.length} ${diagnostico.length === 1 ? 'sesión de prueba' : 'sesiones de prueba'}`}>
                  Pruebas de detección
                </SectionTitle>
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-md">
                  {diagnostico.map((s) => (
                    <SesionVivoCard key={s.id} sesion={s} onAbrir={handleAbrir} />
                  ))}
                </div>
              </section>
            )}

            {otras.length > 0 && (
              <section className="space-y-md">
                <SectionTitle
                  sub={`${otras.length} ${otras.length === 1 ? 'sesión' : 'sesiones'} sin examen vinculado o de origen desconocido`}
                >
                  Sin examen vinculado
                </SectionTitle>
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-md">
                  {otras.map((s) => (
                    <SesionVivoCard key={s.id} sesion={s} onAbrir={handleAbrir} />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </StaffShell>
  );
}
