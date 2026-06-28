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
import type { Inscripcion, Examen, ExamenContenidoResumen } from '../lib/types';
import { InscripcionCard } from './alumno/components/InscripcionCard';

interface GatePorExamen { puede: boolean; codigo?: string; razon?: string; }

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
      const importados = await api.listarExamenesContenido();
      if (cancelado) return;
      setExamenesImportados(importados);
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
          <p className="text-[13px] text-on-surface-variant mt-1">Registro de tus inscripciones con estado y acción siguiente.</p>
        </header>

        {cargando ? (
          <div className="min-h-[60vh] flex items-center justify-center">
            <LoadingSpinner label="Cargando inscripciones…" />
          </div>
        ) : inscripciones.length === 0 ? (
          <Card className="text-center py-xl">
            <Icon name="event_busy" className="text-[40px] text-on-surface-variant mb-md" />
            <p className="text-body-md text-on-surface font-semibold">No tenés inscripciones registradas</p>
            <p className="text-label-sm text-on-surface-variant mt-xs mb-md">Explorá las materias disponibles e inscribite a un examen.</p>
            <Button variant="secondary" onClick={() => navigate('/alumno/materias')} icon="add_circle">Ver materias disponibles</Button>
          </Card>
        ) : (
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

        {/* C-69: Catálogo de exámenes importados (Moodle XML) — solo con backend real.
            Permite al alumno elegir un examen importado y rendir con preguntas reales.
            En modo demo (VITE_USE_REAL_BACKEND=0) esta sección no aparece. */}
        {USE_REAL_BACKEND && (
          <section>
            <div className="flex items-center gap-sm mb-md">
              <Icon name="quiz" className="text-[20px] text-primary" />
              <h2 className="text-[16px] font-semibold text-on-surface">
                Exámenes disponibles (contenido importado)
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
  onRendir: () => void;
}

/**
 * Card que muestra un examen importado desde Moodle XML en el catálogo del alumno.
 * PascalCase: componente React. Solo se muestra cuando USE_REAL_BACKEND=1.
 */
function ExamenImportadoCard({ contenido, rindiendo, onRendir }: ExamenImportadoCardProps) {
  return (
    <Card className="flex items-center justify-between gap-md p-md">
      <div className="flex items-start gap-sm min-w-0">
        <div className="w-9 h-9 rounded-md bg-primary-fixed text-primary flex items-center justify-center shrink-0 mt-0.5">
          <Icon name="quiz" className="text-[18px]" />
        </div>
        <div className="min-w-0">
          <p className="text-[14px] font-medium text-on-surface leading-tight truncate">
            {contenido.titulo}
          </p>
          <p className="text-[12px] text-on-surface-variant mt-0.5">
            {contenido.cantidad_preguntas} {contenido.cantidad_preguntas === 1 ? 'pregunta' : 'preguntas'}
          </p>
        </div>
      </div>
      <Button
        variant="primary"
        size="sm"
        onClick={onRendir}
        disabled={rindiendo}
        icon={rindiendo ? undefined : 'play_arrow'}
      >
        {rindiendo ? 'Verificando…' : 'Rendir'}
      </Button>
    </Card>
  );
}
