// Portal del alumno — Mis inscripciones a exámenes (C-21)
// C-22: puedeRendir usa estado tipado real (sin parseo por substring).
// C-26: gate en capas — muestra "Completar acuse del examen" cuando falta el acuse por-examen.
// C-58: setExamenActivo antes de navegar a /requisitos (fix bug examenActivo null).
// C-69: catálogo de exámenes importados (Moodle XML) visible cuando USE_REAL_BACKEND=1.
import { useEffect, useState } from 'react';
import { Card, Button, Icon, BackButton, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, USE_REAL_BACKEND } from '../lib/api';
import AcuseExamen from './AcuseExamen';
import type { Inscripcion, Examen, ExamenContenidoResumen, NotaExamen } from '../lib/types';
import { InscripcionCard } from './alumno/components/InscripcionCard';

interface GatePorExamen { puede: boolean; codigo?: string; razon?: string; }

/** Resultado del gate de un examen importado (ventana + intentos). */
interface GateImportado { habilitado: boolean; motivo?: string; }

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
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [verificandoId, setVerificandoId] = useState<string | null>(null);
  // C-26: resultado del gate EN CAPAS por examen_id (perfil + acuse)
  const [gatesPorExamen, setGatesPorExamen] = useState<Record<string, GatePorExamen>>({});
  // C-26: examen_id para el que se está completando el acuse desde Mis Exámenes
  const [examenCompletandoAcuse, setExamenCompletandoAcuse] = useState<string | null>(null);
  // C-69: catálogo de exámenes importados (Moodle XML) — solo cuando USE_REAL_BACKEND=1
  const [examenesImportados, setExamenesImportados] = useState<ExamenContenidoResumen[]>([]);
  const [cargandoImportados, setCargandoImportados] = useState(USE_REAL_BACKEND);
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

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [insc, enrollment] = await Promise.all([api.misInscripciones(), api.getEnrollment()]);
      if (cancelado) return;
      setInscripciones(insc);
      setEnrollmentStatus(enrollment);
      await evaluarGates(insc);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // C-69: cargar exámenes importados desde Moodle (solo en modo real)
  useEffect(() => {
    if (!USE_REAL_BACKEND) return;
    let cancelado = false;
    (async () => {
      const [importados, misNotas] = await Promise.all([
        api.listarExamenesContenido(),
        api.misNotas(),
      ]);
      if (cancelado) return;
      setExamenesImportados(importados);
      setNotas(misNotas);
      setCargandoImportados(false);
    })();
    return () => { cancelado = true; };
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
      catedra: '',
      estado: 'en_curso',
      inicio: new Date().toISOString(),
      duracion_min: 60,
      umbral_score: 70,
      detectores: [...DETECTORES_SLIM],
      retencion_dias: 365,
      inscriptos: 0,
      rindiendo: 0,
      examen_contenido_id: contenido.id,         // KEY: permite que Examen.tsx cargue preguntas
    };
    setExamenActivo(examen);
    navigate('/requisitos');
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
      navigate('/requisitos');
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
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl mx-auto space-y-xl">
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
        ) : inscripciones.length > 0 ? (
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
        ) : null}

        {/* C-69: Tus notas — nota académica + estado de cola de revisión por eventos.
            Solo con backend real y solo si el alumno ya rindió algún examen. */}
        {USE_REAL_BACKEND && notas.length > 0 && (
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

        {/* C-69: Catálogo de exámenes importados (Moodle XML) — solo con backend real.
            Permite al alumno elegir un examen importado y rendir con preguntas reales.
            En modo demo (VITE_USE_REAL_BACKEND=0) esta sección no aparece. */}
        {USE_REAL_BACKEND && (
          <section>
            <div className="flex items-center gap-sm mb-md">
              <Icon name="quiz" className="text-[20px] text-primary" />
              <h2 className="text-[16px] font-semibold text-on-surface">
                Exámenes disponibles
              </h2>
            </div>

            {cargandoImportados ? (
              <LoadingSpinner size="sm" label="Cargando exámenes importados…" />
            ) : examenesImportados.length === 0 ? (
              <Card className="text-center py-lg">
                <Icon name="upload_file" className="text-[32px] text-on-surface-variant mb-sm" />
                <p className="text-[14px] text-on-surface-variant">
                  No hay exámenes importados disponibles.
                </p>
                <p className="text-[12px] text-on-surface-variant mt-xs">
                  Un administrador debe importar un examen en formato Moodle XML.
                </p>
              </Card>
            ) : (
              <div className="space-y-sm">
                {examenesImportados.map((contenido) => (
                  <ExamenImportadoCard
                    key={contenido.id}
                    contenido={contenido}
                    rindiendo={rindiendoImportadoId === contenido.id}
                    gate={gateExamenImportado(contenido, notas)}
                    onRendir={() => handleRendirImportado(contenido)}
                  />
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </StudentShell>
  );
}

// ---------------------------------------------------------------------------
// C-69: Card de examen importado (Moodle XML)
// ---------------------------------------------------------------------------

interface ExamenImportadoCardProps {
  contenido: ExamenContenidoResumen;
  rindiendo: boolean;
  gate: GateImportado;
  onRendir: () => void;
}

/**
 * Card que muestra un examen importado desde Moodle XML en el catálogo del alumno.
 * PascalCase: componente React. Solo se muestra cuando USE_REAL_BACKEND=1.
 * El gate (ventana de disponibilidad + intentos) puede deshabilitar "Rendir" y
 * mostrar el motivo en lenguaje claro.
 */
function ExamenImportadoCard({ contenido, rindiendo, gate, onRendir }: ExamenImportadoCardProps) {
  const bloqueado = !gate.habilitado;
  const tiempo = contenido.tiempo_limite_min;
  return (
    <Card className="flex items-center justify-between gap-md p-md">
      <div className="flex items-start gap-sm min-w-0">
        <div className={`w-9 h-9 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${bloqueado ? 'bg-surface-container text-on-surface-variant' : 'bg-primary-fixed text-primary'}`}>
          <Icon name="quiz" className="text-[18px]" />
        </div>
        <div className="min-w-0">
          <p className="text-[14px] font-medium text-on-surface leading-tight truncate">
            {contenido.titulo}
          </p>
          <p className="text-[12px] text-on-surface-variant mt-0.5">
            {contenido.cantidad_preguntas} {contenido.cantidad_preguntas === 1 ? 'pregunta' : 'preguntas'}
            {typeof tiempo === 'number' && tiempo > 0 && ` · ${tiempo} min`}
          </p>
          {bloqueado && gate.motivo && (
            <p className="text-[12px] text-error mt-1 flex items-center gap-1">
              <Icon name="lock" className="text-[14px]" fill /> {gate.motivo}
            </p>
          )}
        </div>
      </div>
      <Button
        variant="primary"
        size="sm"
        onClick={onRendir}
        disabled={rindiendo || bloqueado}
        icon={rindiendo ? undefined : bloqueado ? 'lock' : 'play_arrow'}
      >
        {rindiendo ? 'Verificando…' : 'Rendir'}
      </Button>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// C-69: Card de nota académica + estado de cola de revisión
// ---------------------------------------------------------------------------

/**
 * Muestra la nota de un examen rendido en lenguaje claro para el alumno.
 * Si `en_cola_revision` (el score de proctoring superó el umbral), la nota se
 * presenta como PRELIMINAR con un chip "En revisión por eventos registrados":
 * un docente revisará el examen antes de confirmar la nota. La fuente de verdad
 * es el backend (api.misNotas); el cliente solo la muestra.
 */
function NotaCard({ nota }: { nota: NotaExamen }) {
  const enRevision = nota.en_cola_revision;
  const tieneNota = nota.nota !== null && nota.nota !== undefined;
  return (
    <Card className={`flex items-start gap-md p-md ${enRevision ? 'bg-warning-container/30 border-warning-200' : ''}`}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${enRevision ? 'bg-warning-container text-warning' : 'bg-success-container text-success'}`}>
        <Icon name={enRevision ? 'hourglass_top' : 'grade'} className="text-[18px]" fill />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-on-surface leading-tight">{nota.examen_titulo}</p>
        <div className="flex items-center gap-sm flex-wrap mt-0.5">
          <p className="text-[15px] text-on-surface">
            {tieneNota ? (
              <>
                {enRevision ? 'Nota preliminar: ' : 'Nota: '}
                <strong>
                  {nota.nota}
                  {nota.nota_maxima != null ? ` / ${nota.nota_maxima}` : ''}
                </strong>
              </>
            ) : (
              <span className="text-on-surface-variant">Nota pendiente de cálculo</span>
            )}
          </p>
          {tieneNota && nota.aprobado != null && (
            <span
              className={`inline-flex items-center gap-xs text-[12px] font-medium rounded-full px-sm py-0.5 ${
                nota.aprobado
                  ? 'bg-success-container text-success'
                  : 'bg-error-container text-on-error-container'
              }`}
            >
              <Icon name={nota.aprobado ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
              {nota.aprobado ? 'Aprobado' : 'Desaprobado'}
            </span>
          )}
        </div>
        {enRevision ? (
          <div className="flex items-start gap-xs mt-xs">
            <span className="inline-flex items-center gap-xs bg-warning-container text-warning text-[12px] font-medium rounded-full px-sm py-0.5">
              <Icon name="gavel" className="text-[14px]" fill /> En revisión por eventos registrados
            </span>
          </div>
        ) : tieneNota ? (
          <p className="text-[12px] text-on-surface-variant mt-0.5">Esta es tu nota final.</p>
        ) : null}
        {enRevision && (
          <p className="text-[12px] text-on-surface-variant mt-xs">
            Tu examen quedó en cola de revisión por los eventos registrados durante la supervisión.
            Un docente la revisará y confirmará tu nota.
          </p>
        )}
      </div>
    </Card>
  );
}
