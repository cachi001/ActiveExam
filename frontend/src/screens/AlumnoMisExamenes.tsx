// Portal del alumno — Mis inscripciones a exámenes (C-21)
// C-22: puedeRendir usa estado tipado real (sin parseo por substring).
// C-26: gate en capas — muestra "Completar acuse del examen" cuando falta el acuse por-examen.
// C-58: setExamenActivo antes de navegar a /requisitos (fix bug examenActivo null).
import { useEffect, useState } from 'react';
import { Card, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import AcuseExamen from './AcuseExamen';
import type { Inscripcion, Examen } from '../lib/types';
import { InscripcionCard } from './alumno/components/InscripcionCard';

interface GatePorExamen { puede: boolean; codigo?: string; razon?: string; }

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
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mis exámenes</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">Registro de tus inscripciones con estado y acción siguiente.</p>
        </header>

        {cargando ? (
          <Card className="flex items-center gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[20px]" />
            <span className="text-body-md">Cargando inscripciones…</span>
          </Card>
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
      </div>
    </StudentShell>
  );
}
