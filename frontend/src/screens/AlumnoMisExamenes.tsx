// Portal del alumno — Mis inscripciones a exámenes (C-21)
// C-22: puedeRendir usa estado tipado real (sin parseo por substring).
// C-26: gate en capas — muestra "Completar acuse del examen" cuando falta el acuse por-examen.
// C-58: setExamenActivo antes de navegar a /requisitos (fix bug examenActivo null).
// C-69: catálogo de exámenes importados (Moodle XML) visible cuando USE_REAL_BACKEND=1.
import { useEffect, useState } from 'react';
import { Icon, BackButton, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import AcuseExamen from './AcuseExamen';
import type { Inscripcion, Examen, ExamenContenidoResumen, NotaExamen, EstadoEnrollment } from '../lib/types';
import { InscripcionCard } from './alumno/components/InscripcionCard';
import { ExamenImportadoCard, type GateImportado } from './alumno/components/ExamenImportadoCard';
import { NotaCard } from './alumno/components/NotaCard';

interface GatePorExamen { puede: boolean; codigo?: string; razon?: string; }

/** Formatea un ISO 8601 a fecha+hora legible (es-AR). */
function formatFechaHora(iso: string): string {
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * Gate de "Rendir" para un examen importado (C-69 config):
 * 1. Ventana: antes de `apertura` → "Disponible desde…"; después de `cierre` → "Cerrado el…".
 * 2. Intentos: si el alumno ya rindió `intentos_permitidos` veces (contando ítems de
 *    `misNotas()` de ese examen) → bloqueado con "Ya rendiste este examen (n/intentos)".
 * Función pura (acepta `ahora` inyectable) para poder testearla sin reloj real.
 */
function gateExamenImportado(
  contenido: ExamenContenidoResumen,
  notas: NotaExamen[],
  ahora: number = Date.now(),
): GateImportado {
  if (contenido.apertura) {
    const ap = new Date(contenido.apertura).getTime();
    if (!Number.isNaN(ap) && ahora < ap) {
      return { habilitado: false, motivo: `Disponible desde ${formatFechaHora(contenido.apertura)}` };
    }
  }
  if (contenido.cierre) {
    const ci = new Date(contenido.cierre).getTime();
    if (!Number.isNaN(ci) && ahora > ci) {
      return { habilitado: false, motivo: `Cerrado el ${formatFechaHora(contenido.cierre)}` };
    }
  }
  const permitidos = contenido.intentos_permitidos ?? null;
  if (permitidos !== null && permitidos >= 1) {
    const usados = notas.filter((n) => n.examen_id === contenido.id).length;
    if (usados >= permitidos) {
      return { habilitado: false, motivo: `Ya rendiste este examen (${usados}/${permitidos})` };
    }
  }
  return { habilitado: true };
}

/** Detectores por defecto para exámenes importados (sin config de examen-config). */
const DETECTORES_SLIM = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida',
  'perdida_de_foco', 'cambio_pestana', 'salida_pantalla_completa',
] as const;

export default function AlumnoMisExamenes() {
  const navigate = useNavigate();
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const setExamenActivo = useApp((s) => s.setExamenActivo);
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
  // C-26: resultado del gate EN CAPAS por examen_id (perfil + acuse)
  const [gatesPorExamen, setGatesPorExamen] = useState<Record<string, GatePorExamen>>({});
  // C-26: examen_id para el que se está completando el acuse desde Mis Exámenes
  const [examenCompletandoAcuse, setExamenCompletandoAcuse] = useState<string | null>(null);
  // C-69: catálogo de exámenes importados (Moodle XML) — solo cuando USE_REAL_BACKEND=1
  const [examenesImportados, setExamenesImportados] = useState<ExamenContenidoResumen[]>([]);
  const [rindiendoImportadoId, setRindiendoImportadoId] = useState<string | null>(null);
  // C-69: notas académicas del alumno + estado de cola de revisión (solo modo real)
  const [notas, setNotas] = useState<NotaExamen[]>([]);

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
      const extraFetches = [api.listarExamenesContenido(), api.misNotas()] as const;
      const [insc, enrollment, ...extra] = await Promise.all([...baseFetches, ...extraFetches]);
      if (cancelado) return;
      setInscripciones(insc);
      setEnrollmentLocal(enrollment);
      setEnrollmentStatus(enrollment);
      if (extra.length === 2) {
        setExamenesImportados(extra[0] as ExamenContenidoResumen[]);
        setNotas(extra[1] as NotaExamen[]);
      }
      await evaluarGates(insc);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Inicia la rendición de un examen importado de Moodle (C-69).
   * Verifica el gate de perfil (sin examen_id para no requerir acuse por-examen en slim).
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
      // Duración real del examen (config del docente); 0 = sin límite, coherente
      // con lo que Examen.tsx va a leer server-side vía fetchExamenParaRendir.
      duracion_min: contenido.tiempo_limite_min ?? 0,
      umbral_score: 70,
      detectores: [...DETECTORES_SLIM],
      retencion_dias: 365,
      inscriptos: 0,
      rindiendo: 0,
      examen_contenido_id: contenido.id,         // KEY: permite que Examen.tsx cargue preguntas
    };
    setExamenActivo(examen);
    navigate('/pre-examen');
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
      setExamenActivo(examen);
      navigate('/pre-examen');
    } else {
      setGatesPorExamen((prev) => ({ ...prev, [inscripcion.examen_id]: gate }));
    }
  };

  const handleAcuseCompletado = async () => {
    if (!examenCompletandoAcuse) return;
    const examenId = examenCompletandoAcuse;
    setExamenCompletandoAcuse(null);
    const gate = await api.puedeRendir(examenId);
    setGatesPorExamen((prev) => ({ ...prev, [examenId]: gate }));
  };

  if (examenCompletandoAcuse) {
    return (
      <AcuseExamen
        examenId={examenCompletandoAcuse}
        onConfirmado={handleAcuseCompletado}
        onCancelar={() => setExamenCompletandoAcuse(null)}
      />
    );
  }

  return (
    <StudentShell>
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl space-y-xl">
        <BackButton onClick={() => navigate('/alumno')} />
        <header>
          <div className="flex items-center gap-sm">
            <h1 className="text-[22px] sm:text-[24px] font-semibold text-on-surface tracking-tight">Mis exámenes</h1>
            <HelpButton title="Mis exámenes">
              <p>
                Acá ves tus <strong>inscripciones</strong> a exámenes con su estado actual y la
                acción que tenés que hacer (inscribirte, confirmar tu participación, rendir, etc.).
              </p>
              <p>
                Antes de poder rendir, además del consentimiento general en <em>Mi perfil</em>,
                cada examen pide una <em>confirmación específica</em> con la información puntual de ese
                examen (modalidad, fechas, requisitos).
              </p>
              <p>
                Si el botón "Rendir" está deshabilitado, te vamos a mostrar la razón
                (perfil incompleto, fuera de horario, etc.).
              </p>
            </HelpButton>
          </div>
          <p className="text-[13px] text-on-surface-variant mt-1">Elegí un examen disponible para rendir y consultá tus notas.</p>
        </header>

        {/* Sección de inscripciones: solo se muestra si el alumno TIENE inscripciones.
            En modo real no existe el modelo de inscripción (misInscripciones() = []),
            así que esta sección queda oculta y el alumno ve solo los exámenes
            disponibles + sus notas más abajo. */}
        {cargando ? (
          <div className="min-h-[40vh] flex items-center justify-center">
            <LoadingSpinner label="Cargando tus exámenes…" />
          </div>
        ) : (
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
                    onCompletarAcuse={() => setExamenCompletandoAcuse(insc.examen_id)}
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
                  <Icon name="grade" className="text-[20px] text-primary" />
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
                    <Icon name="assignment" className="text-[20px] text-primary" />
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

