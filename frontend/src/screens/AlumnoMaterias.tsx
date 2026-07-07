// Portal del alumno — Exploración Materia → Comisión → Examen (C-21)
// C-69: datos REALES desde el backend (materias/comisiones/exámenes importados de Moodle).
//       El leaf es un examen de contenido: el alumno lo rinde directo (sin inscripción demo).
import { useEffect, useState, type FormEvent } from 'react';
import { BackButton, LoadingSpinner, Icon } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { Materia, Comision, Examen, ExamenContenidoResumen } from '../lib/types';
import { ComisionRow } from './alumno/components/ComisionRow';

/** Detectores por defecto para exámenes importados (sin config de examen-config). */
const DETECTORES_SLIM = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida',
  'perdida_de_foco', 'cambio_pestana', 'salida_pantalla_completa',
] as const;

export default function AlumnoMaterias() {
  const navigate = useNavigate();
  const setExamenActivo = useApp((s) => s.setExamenActivo);
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [examenes, setExamenes] = useState<ExamenContenidoResumen[]>([]);
  const [materiaSeleccionada, setMateriaSeleccionada] = useState<Materia | null>(null);
  const [comisionSeleccionada, setComisionSeleccionada] = useState<Comision | null>(null);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);
  const [cargandoComisiones, setCargandoComisiones] = useState(false);
  const [cargandoExamenes, setCargandoExamenes] = useState(false);
  const [rindiendoId, setRindiendoId] = useState<string | null>(null);
  // C-70: auto-matriculación por código (enrolment key).
  const [codigoJoin, setCodigoJoin] = useState('');
  const [uniendo, setUniendo] = useState(false);
  const [joinMsg, setJoinMsg] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  // C-71: gate de perfil — sin perfil completo no se puede matricular (server-side + UX).
  const [perfilCompleto, setPerfilCompleto] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [mats, gate] = await Promise.all([
        api.materiasDisponibles(),
        api.puedeRendir().catch(() => ({ puede: false })),
      ]);
      if (cancelado) return;
      setMaterias(mats);
      setPerfilCompleto(gate.puede);
      setCargandoMaterias(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const unirmePorCodigo = async (e: FormEvent) => {
    e.preventDefault();
    const codigo = codigoJoin.trim();
    if (!codigo || uniendo) return;
    setUniendo(true);
    setJoinMsg(null);
    try {
      const r = await api.inscribirmePorCodigo(codigo);
      setJoinMsg({
        tipo: 'ok',
        texto: r.ya_inscripto
          ? `Ya estabas matriculado en ${r.materia_nombre} · ${r.comision_nombre}.`
          : `¡Listo! Te uniste a ${r.materia_nombre} · ${r.comision_nombre}.`,
      });
      setCodigoJoin('');
      // Refrescar el catálogo (y las comisiones de la materia abierta) por si aparece algo nuevo.
      const mats = await api.materiasDisponibles();
      setMaterias(mats);
      if (materiaSeleccionada) {
        const coms = await api.comisionesDeMateria(materiaSeleccionada.id);
        setComisiones(coms);
      }
    } catch (err) {
      const e2 = err as Error & { status?: number };
      if (e2.status === 403) {
        setPerfilCompleto(false);
        setJoinMsg({
          tipo: 'error',
          texto: 'Primero completá tu perfil (consentimiento y biometría) para poder matricularte.',
        });
      } else {
        setJoinMsg({
          tipo: 'error',
          texto:
            e2.status === 404 || e2.status === 422
              ? 'Ese código no es válido. Revisalo con tu docente.'
              : 'No se pudo procesar el código. Intentá de nuevo.',
        });
      }
    } finally {
      setUniendo(false);
    }
  };

  const seleccionarMateria = async (materia: Materia) => {
    if (materiaSeleccionada?.id === materia.id) return; // master-detail: seleccionar, no togglear
    setMateriaSeleccionada(materia); setComisionSeleccionada(null); setExamenes([]); setComisiones([]); setCargandoComisiones(true);
    const coms = await api.comisionesDeMateria(materia.id);
    setComisiones(coms); setCargandoComisiones(false);
  };

  // Auto-seleccionar la primera materia para que el panel derecho no quede vacío.
  useEffect(() => {
    if (!materiaSeleccionada && materias.length > 0) void seleccionarMateria(materias[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [materias]);

  const seleccionarComision = async (comision: Comision) => {
    if (comisionSeleccionada?.id === comision.id) { setComisionSeleccionada(null); setExamenes([]); return; }
    setComisionSeleccionada(comision); setCargandoExamenes(true);
    const exams = await api.examenesDeComision(comision.id);
    setExamenes(exams); setCargandoExamenes(false);
  };

  /**
   * C-69: rendir un examen de contenido importado. Verifica el gate de perfil
   * (sin examen_id → solo perfil), setea examenActivo con examen_contenido_id
   * (para que Examen.tsx cargue las preguntas reales) y navega a /requisitos.
   */
  const rendirExamen = async (examenContenidoId: string) => {
    const contenido = examenes.find((e) => e.id === examenContenidoId);
    if (!contenido) return;
    setRindiendoId(examenContenidoId);
    const gate = await api.puedeRendir();
    setRindiendoId(null);
    if (!gate.puede) {
      navigate('/alumno/perfil');
      return;
    }
    const examen: Examen = {
      id: contenido.id,
      nombre: contenido.titulo,
      catedra: contenido.materia_nombre ?? '',
      estado: 'en_curso',
      inicio: new Date().toISOString(),
      // Duración real del examen (config del docente); 0 = sin límite, coherente
      // con lo que Examen.tsx va a leer server-side vía fetchExamenParaRendir.
      duracion_min: contenido.tiempo_limite_min ?? 0,
      umbral_score: 70,
      detectores: [...DETECTORES_SLIM],
      retencion_dias: 365,
      inscriptos: 0,
      rindiendo: 0,
      examen_contenido_id: contenido.id,
    };
    setExamenActivo(examen);
    navigate('/requisitos');
  };

  return (
    <StudentShell>
      <div className="w-full space-y-lg">
        <BackButton onClick={() => navigate('/alumno')} />
        <header>
          <div className="flex items-center gap-sm">
            <h1 className="text-[22px] sm:text-[24px] font-semibold text-on-surface tracking-tight">Mis materias</h1>
            <HelpButton title="Materias">
              <p>
                Explorá el catálogo de <strong>materias y comisiones</strong>: elegí una materia
                para ver sus comisiones; entrá a una comisión para ver los exámenes disponibles.
              </p>
              <p>
                Cada examen se rinde directamente: al tocar <em>Rendir</em> verificamos tu perfil
                (consentimiento y biometría) y te llevamos a los requisitos previos.
              </p>
            </HelpButton>
          </div>
          <p className="text-[13px] text-on-surface-variant mt-1">Elegí una materia para ver sus comisiones y exámenes disponibles.</p>
        </header>

        {/* C-70: unirse a una comisión con un código de matriculación (enrolment key). */}
        <div className="rounded-2xl border border-outline-variant/50 bg-surface-container-lowest p-4">
          <div className="flex items-center gap-2 mb-2">
            <Icon name="vpn_key" className="text-[16px] text-on-surface-variant shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">Unirme con un código</h2>
            <HelpButton title="Unirme con un código">
              <p>
                Si tu docente te compartió un <strong>código de matriculación</strong> (por ejemplo
                <em> PROG1-7K2Q</em>), ingresalo acá para unirte a esa comisión.
              </p>
              <p>Unirte no habilita a rendir por sí solo: seguís necesitando tu perfil (consentimiento y biometría) al día.</p>
            </HelpButton>
          </div>
          {perfilCompleto === false && (
            <div role="alert" className="mb-2 flex items-center gap-2 rounded-md bg-error-container text-error p-2.5 text-[12px]">
              <Icon name="lock" className="text-[15px] shrink-0" fill />
              <span className="flex-1">
                Para matricularte necesitás completar tu perfil (consentimiento y biometría) primero.
              </span>
              <button
                type="button"
                onClick={() => navigate('/alumno/perfil')}
                className="font-semibold underline shrink-0"
              >
                Completar perfil
              </button>
            </div>
          )}
          <form onSubmit={unirmePorCodigo} className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={codigoJoin}
              disabled={uniendo || perfilCompleto === false}
              onChange={(e) => setCodigoJoin(e.target.value)}
              placeholder="Ej. PROG1-7K2Q"
              aria-label="Código de matriculación"
              className="flex-1 rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm font-mono text-on-surface outline-none transition-colors hover:border-outline focus:border-primary focus:ring-1 focus:ring-primary/30 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={uniendo || !codigoJoin.trim() || perfilCompleto === false}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uniendo ? (
                <>
                  <Icon name="progress_activity" className="ae-spin text-[18px]" />
                  Uniéndote…
                </>
              ) : (
                <>
                  <Icon name="add" className="text-[18px]" />
                  Unirme
                </>
              )}
            </button>
          </form>
          {joinMsg && (
            <p
              role="status"
              className={`mt-2 text-[12px] flex items-center gap-1.5 ${
                joinMsg.tipo === 'ok' ? 'text-primary' : 'text-error'
              }`}
            >
              <Icon name={joinMsg.tipo === 'ok' ? 'check_circle' : 'error'} className="text-[15px] shrink-0" fill />
              {joinMsg.texto}
            </p>
          )}
        </div>

        {cargandoMaterias ? (
          <div className="min-h-[50vh] flex items-center justify-center">
            <LoadingSpinner label="Cargando materias…" />
          </div>
        ) : materias.length === 0 ? (
          <div className="min-h-[340px] flex items-center justify-center rounded-2xl border border-outline-variant/50 bg-surface-container-lowest">
            <div className="flex flex-col items-center text-center gap-md max-w-sm">
              <div className="w-16 h-16 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center">
                <Icon name="menu_book" className="text-[32px]" />
              </div>
              <div className="space-y-1">
                <p className="text-[16px] font-semibold text-on-surface">No hay materias disponibles</p>
                <p className="text-[13px] text-on-surface-variant leading-relaxed">
                  Cuando un administrador importe exámenes y los asocie a una comisión, van a aparecer acá.
                </p>
              </div>
            </div>
          </div>
        ) : (
          // Master-detail: materias a la izquierda, comisiones/exámenes de la elegida a la derecha.
          <div className="grid lg:grid-cols-3 gap-lg items-start">
            {/* Izquierda: materias */}
            <div className="lg:col-span-1 rounded-2xl border border-outline-variant/50 bg-surface-container-lowest overflow-hidden">
              <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
                <Icon name="menu_book" className="text-[16px] text-on-surface-variant shrink-0" />
                <h2 className="text-[13px] font-semibold text-on-surface">
                  Materias <span className="text-on-surface-variant font-normal">({materias.length})</span>
                </h2>
              </div>
              <div className="divide-y divide-outline-variant/30">
                {materias.map((materia) => {
                  const sel = materiaSeleccionada?.id === materia.id;
                  return (
                    <button
                      key={materia.id}
                      onClick={() => void seleccionarMateria(materia)}
                      className={`w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors ${
                        sel ? 'bg-primary-fixed/50' : 'hover:bg-surface-container-low'
                      }`}
                    >
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${sel ? 'bg-primary text-on-primary' : 'bg-secondary-container text-on-secondary'}`}>
                        <Icon name="school" className="text-[18px]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-[14px] font-semibold leading-tight truncate ${sel ? 'text-primary' : 'text-on-surface'}`}>
                          {materia.nombre}
                        </p>
                        <p className="text-[12px] text-on-surface-variant leading-tight mt-0.5 truncate">{materia.codigo}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Derecha: comisiones + exámenes de la materia elegida */}
            <div className="lg:col-span-2 rounded-2xl border border-outline-variant/50 bg-surface-container-lowest overflow-hidden min-w-0">
              {!materiaSeleccionada ? (
                <div className="py-16 text-center text-on-surface-variant text-[13px]">
                  Elegí una materia para ver sus comisiones.
                </div>
              ) : (
                <>
                  <div className="px-4 py-3 border-b border-outline-variant/40">
                    <h2 className="text-[13px] font-semibold text-on-surface truncate">
                      Comisiones de {materiaSeleccionada.nombre}
                    </h2>
                  </div>
                  <div className="p-4 space-y-sm">
                    {cargandoComisiones ? (
                      <LoadingSpinner size="sm" label="Cargando comisiones…" />
                    ) : comisiones.length === 0 ? (
                      <p className="text-[13px] text-on-surface-variant px-1 py-2">No hay comisiones disponibles.</p>
                    ) : (
                      comisiones.map((comision) => (
                        <ComisionRow
                          key={comision.id}
                          comision={comision}
                          activa={comisionSeleccionada?.id === comision.id}
                          cargandoExamenes={cargandoExamenes}
                          examenes={examenes}
                          rindiendoId={rindiendoId}
                          onSelect={() => seleccionarComision(comision)}
                          onRendir={rendirExamen}
                        />
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </StudentShell>
  );
}
