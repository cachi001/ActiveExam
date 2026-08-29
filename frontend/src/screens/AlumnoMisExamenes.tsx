// Portal del alumno — Mis inscripciones a exámenes (C-21)
// C-22: puedeRendir usa estado tipado real (sin parseo por substring).
// C-58: setExamenActivo antes de navegar a /requisitos (fix bug examenActivo null).
// C-69: catálogo de exámenes importados (Moodle XML) visible cuando USE_REAL_BACKEND=1.
import { useEffect, useState } from 'react';
import { Icon, BackButton, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { Inscripcion, Examen, ExamenContenidoResumen, NotaExamen, EstadoEnrollment } from '../lib/types';
import type { SesionEnCurso } from '../lib/apiProctoring/sesion';
import { InscripcionCard } from './alumno/components/InscripcionCard';
import { ExamenImportadoCard } from './alumno/components/ExamenImportadoCard';
import { gateExamenImportado } from './alumno/gateExamenImportado';
import { destinoDeRendicion } from './alumno/destinoDeRendicion';
import { NotaCard } from './alumno/components/NotaCard';

interface GatePorExamen { puede: boolean; codigo?: string; razon?: string; }

/** Detectores por defecto para exámenes importados (sin config de examen-config). */
const DETECTORES_ACTIVEEXAM = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida',
  'perdida_de_foco', 'cambio_pestana', 'salida_pantalla_completa',
] as const;

export default function AlumnoMisExamenes() {
  const navigate = useNavigate();
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const setExamenActivo = useApp((s) => s.setExamenActivo);
  // Red de seguridad del bug "intento 2 muestra respuestas del intento 1": al arrancar
  // una rendición nueva limpiamos la sesión previa, así Consent crea SIEMPRE una sesión
  // nueva (crea solo `if (!proctoringSessionId)`). Cubre el caso de no pasar por el
  // "Volver al inicio" de Cierre (que llama resetSesion). Ver store.resetSesion.
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  // C-69: si el perfil (consentimiento + biometría) no está completo, la card del
  // examen muestra "Completar perfil" en vez de "Rendir".
  // Fix estado-fresco: NO derivar de la store (`enrollmentStatus`), que puede tener un
  // valor stale del usuario/carga anterior y mostrar "Rendir" antes de tiempo. Usamos
  // el enrollment recién leído del servidor en ESTA carga; default `false` (incompleto)
  // hasta confirmarlo, para nunca habilitar "Rendir" con un valor stale.
  const [enrollmentLocal, setEnrollmentLocal] = useState<EstadoEnrollment | null>(null);
  const perfilCompleto = enrollmentLocal?.perfil_completo ?? false;
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [verificandoId, setVerificandoId] = useState<string | null>(null);
  // Resultado del gate de perfil por examen_id (el perfil es el único gate de consentimiento)
  const [gatesPorExamen, setGatesPorExamen] = useState<Record<string, GatePorExamen>>({});
  // C-69: catálogo de exámenes importados (Moodle XML) — solo cuando USE_REAL_BACKEND=1
  const [examenesImportados, setExamenesImportados] = useState<ExamenContenidoResumen[]>([]);
  const [rindiendoImportadoId, setRindiendoImportadoId] = useState<string | null>(null);
  // C-69: notas académicas del alumno + estado de cola de revisión (solo modo real)
  const [notas, setNotas] = useState<NotaExamen[]>([]);
  // Exámenes empezados y sin entregar, por examen_contenido_id. Sin esto, al
  // alumno al que se le cortó la conexión la pantalla le mostraba su examen a
  // medias como si nunca lo hubiera tocado, con el cartel "Tenés un solo
  // intento" — y entendía que lo había perdido.
  const [sesionesEnCurso, setSesionesEnCurso] = useState<Map<string, SesionEnCurso>>(new Map());

  const evaluarGates = async (insc: Inscripcion[]) => {
    const resultados = await Promise.all(
      insc.filter((i) => i.estado === 'habilitado')
        .map((i) => api.puedeRendir(i.examen_id).then((g) => [i.examen_id, g] as const))
    );
    setGatesPorExamen(Object.fromEntries(resultados));
  };

  // Un único fetch que carga todo en paralelo → un solo spinner, sin doble carga.
  useEffect(() => {
    let cancelado = false;
    (async () => {
      const baseFetches: [Promise<Inscripcion[]>, Promise<EstadoEnrollment>] = [
        api.misInscripciones(),
        api.getEnrollment(),
      ];
      const extraFetches = [
        api.listarExamenesContenido(),
        api.misNotas(),
        // Degrada a [] por su cuenta: que no se pueda averiguar si hay algo en
        // curso no puede tumbar la pantalla entera.
        api.misSesionesEnCurso(),
      ] as const;
      const [insc, enrollment, ...extra] = await Promise.all([...baseFetches, ...extraFetches]);
      if (cancelado) return;
      setInscripciones(insc);
      setEnrollmentLocal(enrollment);
      setEnrollmentStatus(enrollment);
      if (extra.length === 3) {
        setExamenesImportados(extra[0] as ExamenContenidoResumen[]);
        setNotas(extra[1] as NotaExamen[]);
        setSesionesEnCurso(
          new Map((extra[2] as SesionEnCurso[]).map((s) => [s.examen_contenido_id, s])),
        );
      }
      await evaluarGates(insc);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Inicia la rendición de un examen importado de Moodle (C-69).
   * Verifica el gate de perfil (sin examen_id para no requerir acuse por-examen en activeexam).
   * Setea examenActivo con examen_contenido_id para que Examen.tsx cargue las preguntas.
   */
  const handleRendirImportado = async (contenido: ExamenContenidoResumen) => {
    // Gate de ventana/intentos: si está bloqueado, no iniciar la rendición.
    if (!gateExamenImportado(contenido, notas).habilitado) return;
    setRindiendoImportadoId(contenido.id);
    const gate = await api.puedeRendir(); // sin examenId → solo gate de perfil
    setRindiendoImportadoId(null);
    if (!gate.puede) {
      // Si el perfil no está completo, navegar al perfil para que lo complete.
      navigate('/alumno/perfil');
      return;
    }
    // Construir un Examen mínimo con examen_contenido_id seteado.
    // Examen.tsx lo usa para GET /api/v1/exam-content/{examen_contenido_id}.
    const examen: Examen = {
      id: contenido.id,                          // id del contenido como id del examen
      nombre: contenido.titulo,
      catedra: contenido.materia_nombre ?? '',
      estado: 'en_curso',
      inicio: new Date().toISOString(),
      // Duración real del examen (config del tutor); 0 = sin límite, coherente
      // con lo que Examen.tsx va a leer server-side vía fetchExamenParaRendir.
      duracion_min: contenido.tiempo_limite_min ?? 0,
      umbral_score: 70,
      detectores: [...DETECTORES_ACTIVEEXAM],
      retencion_dias: 365,
      inscriptos: 0,
      rindiendo: 0,
      examen_contenido_id: contenido.id,         // KEY: permite que Examen.tsx cargue preguntas
    };
    // Si el alumno dejó este examen empezado, retomarlo: se reusa SU sesión (mismo
    // cronómetro, respuestas ya guardadas) y se va derecho al examen. Mandarlo de
    // nuevo por el ingreso completo, con el botón final diciendo «Comenzar examen»,
    // contradecía lo que la tarjeta le había prometido — y descartar el id abría un
    // intento nuevo sobre una sesión que seguía viva.
    const destino = destinoDeRendicion(sesionesEnCurso.get(contenido.id) ?? null);
    setProctoringSessionId(destino.sessionId);
    setExamenActivo(examen);
    navigate(destino.ruta);
  };

  const handleRendir = async (inscripcion: Inscripcion) => {
    setVerificandoId(inscripcion.id);
    const gate = await api.puedeRendir(inscripcion.examen_id);
    setVerificandoId(null);
    if (gate.puede) {
      // C-58 D1: resolver el Examen y setearlo en el store ANTES de navegar.
      // Consent.tsx lee examenActivo del store; sin este seteo quedaba null y
      // aceptar() era inerte (guard if (!acepto || !examen) return).
      let examen: Examen | undefined = await api.getExam(inscripcion.examen_id);
      if (!examen) {
        // Fallback: construir un Examen mínimo desde la Inscripcion para no romper el flujo.
        // Consent solo necesita examen.id para recordConsent(examen.id).
        examen = {
          id: inscripcion.examen_id,
          nombre: inscripcion.nombre_examen,
          catedra: inscripcion.nombre_materia,
          estado: 'en_curso',
          inicio: inscripcion.fecha,
          duracion_min: 60,
          umbral_score: 50,
          detectores: [],
          retencion_dias: 365,
          inscriptos: 0,
          rindiendo: 0,
        };
      }
      setProctoringSessionId(null); // intento nuevo → sesión nueva (no reusar la finalizada)
      setExamenActivo(examen);
      navigate('/pre-examen');
    } else {
      setGatesPorExamen((prev) => ({ ...prev, [inscripcion.examen_id]: gate }));
    }
  };

  // Loading a pantalla completa: centrado en TODO el ancho del contenido (no dentro
  // de la columna max-w pegada a la izquierda, que dejaba el spinner corrido). Mismo
  // patrón que StudentProfile.
  if (cargando) {
    return (
      <StudentShell>
        <div className="min-h-[calc(100dvh-13rem)] flex items-center justify-center">
          <LoadingSpinner label="Cargando tus exámenes…" />
        </div>
      </StudentShell>
    );
  }

  return (
    <StudentShell>
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl space-y-xl">
        <BackButton onClick={() => navigate('/alumno')} />
        <header>
          <div className="flex items-center gap-sm">
            <h1 className="text-[22px] sm:text-[24px] font-semibold text-on-surface tracking-tight">Mis exámenes</h1>
            {/* El texto anterior describía un flujo de inscripciones que no
                existe: `misInscripciones()` devuelve [] siempre, así que nadie
                se inscribe ni confirma nada. Los exámenes de tu comisión
                aparecen directamente. */}
            <HelpButton title="Mis exámenes">
              <p>
                Acá ves los exámenes que podés rendir y las notas de los que ya rendiste.
                No hace falta inscribirse: si el examen es de tu comisión y está habilitado,
                te aparece en la lista.
              </p>
              <p>
                Para rendir necesitás tener el perfil completo (el consentimiento y la captura
                de tu rostro), que se hace una sola vez desde <em>Mi perfil</em>.
              </p>
              <p>
                El botón <strong>Ver examen</strong> te lleva a la ficha, donde ves las
                condiciones y desde ahí empezás cuando quieras. Si un examen no está
                disponible, la tarjeta te dice por qué: perfil incompleto, fuera de fecha o
                sin intentos disponibles.
              </p>
            </HelpButton>
          </div>
          <p className="text-[13px] text-on-surface-variant mt-1">Elegí un examen disponible para rendir y consultá tus notas.</p>
        </header>

        {/* Sección de inscripciones: solo se muestra si el alumno TIENE inscripciones.
            En modo real no existe el modelo de inscripción (misInscripciones() = []),
            así que esta sección queda oculta y el alumno ve solo los exámenes
            disponibles + sus notas más abajo. */}
        {(
          <>
            {inscripciones.length > 0 && (
              <div className="space-y-sm">
                {inscripciones.map((insc) => (
                  <InscripcionCard
                    key={insc.id}
                    inscripcion={insc}
                    gate={gatesPorExamen[insc.examen_id]}
                    verificando={verificandoId === insc.id}
                    onRendir={() => handleRendir(insc)}
                    onIrAPerfil={() => navigate('/alumno/perfil')}
                  />
                ))}
              </div>
            )}

            {/* C-69: Tus notas — nota académica + estado de cola de revisión por eventos.
                Solo con backend real y solo si el alumno ya rindió algún examen. */}
            {notas.length > 0 && (
              <section>
                <div className="flex items-center gap-sm mb-md">
                  <Icon name="school" className="text-[20px] text-on-surface-variant" />
                  <h2 className="text-[16px] font-semibold text-on-surface">Tus notas</h2>
                </div>
                <div className="space-y-sm">
                  {notas.map((n) => (
                    <NotaCard key={n.examen_id} nota={n} />
                  ))}
                </div>
              </section>
            )}

            {/* C-69: Catálogo de exámenes importados (Moodle XML). */}
            {(
              <section>
                {examenesImportados.length > 0 && (
                  <div className="flex items-center gap-sm mb-md">
                    {/* Neutro, igual que el de "Tus notas": el azul se reserva
                        para los elementos con color dentro de las tarjetas
                        (el cuadro de icono de un examen habilitado). Un
                        encabezado azul y otro negro en la misma pantalla se
                        leen como dos criterios distintos. */}
                    <Icon name="assignment" className="text-[20px] text-on-surface-variant" />
                    <h2 className="text-[16px] font-semibold text-on-surface">
                      Exámenes disponibles
                    </h2>
                  </div>
                )}

                {examenesImportados.length === 0 ? (
                  <div className="min-h-[280px] flex items-center justify-center">
                    <div className="flex flex-col items-center text-center gap-md max-w-sm">
                      <div className="w-16 h-16 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center">
                        <Icon name="assignment" className="text-[32px]" />
                      </div>
                      <div className="space-y-1">
                        <p className="text-[16px] font-semibold text-on-surface">No hay exámenes disponibles</p>
                        <p className="text-[13px] text-on-surface-variant leading-relaxed">
                          Todavía no hay exámenes programados para vos. Volvé a consultar más cerca de la fecha de tu evaluación.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-sm">
                    {examenesImportados.map((contenido) => (
                      <ExamenImportadoCard
                        key={contenido.id}
                        contenido={contenido}
                        rindiendo={rindiendoImportadoId === contenido.id}
                        gate={gateExamenImportado(contenido, notas)}
                        perfilCompleto={perfilCompleto}
                        sesionEnCurso={sesionesEnCurso.get(contenido.id) ?? null}
                        onRendir={() => handleRendirImportado(contenido)}
                        onCompletarPerfil={() => navigate('/alumno/perfil')}
                      />
                    ))}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </StudentShell>
  );
}

