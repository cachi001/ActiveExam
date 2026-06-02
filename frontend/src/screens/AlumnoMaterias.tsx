// Portal del alumno — Exploración Materia → Comisión → Examen (C-21)
// C-26: flujo de inscripción incluye paso de acuse por-examen antes de inscribir.
import { useEffect, useState } from 'react';
import { Card, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { api } from '../lib/api';
import AcuseExamen from './AcuseExamen';
import type { Materia, Comision, Examen, Inscripcion } from '../lib/types';
import { MateriaCard } from './alumno/components/MateriaCard';

export default function AlumnoMaterias() {
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [materiaSeleccionada, setMateriaSeleccionada] = useState<Materia | null>(null);
  const [comisionSeleccionada, setComisionSeleccionada] = useState<Comision | null>(null);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);
  const [cargandoComisiones, setCargandoComisiones] = useState(false);
  const [cargandoExamenes, setCargandoExamenes] = useState(false);
  const [inscribiendoId, setInscribiendoId] = useState<string | null>(null);
  // C-26: ID del examen pendiente de acuse antes de inscribir
  const [examenPendienteAcuse, setExamenPendienteAcuse] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [mats, insc] = await Promise.all([api.materiasDisponibles(), api.misInscripciones()]);
      if (cancelado) return;
      setMaterias(mats);
      setInscripciones(insc);
      setCargandoMaterias(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const seleccionarMateria = async (materia: Materia) => {
    if (materiaSeleccionada?.id === materia.id) {
      setMateriaSeleccionada(null); setComisionSeleccionada(null); setComisiones([]); setExamenes([]);
      return;
    }
    setMateriaSeleccionada(materia); setComisionSeleccionada(null); setExamenes([]); setCargandoComisiones(true);
    const coms = await api.comisionesDeMateria(materia.id);
    setComisiones(coms); setCargandoComisiones(false);
  };

  const seleccionarComision = async (comision: Comision) => {
    if (comisionSeleccionada?.id === comision.id) { setComisionSeleccionada(null); setExamenes([]); return; }
    setComisionSeleccionada(comision); setCargandoExamenes(true);
    const exams = await api.examenesDeComision(comision.id);
    setExamenes(exams); setCargandoExamenes(false);
  };

  // C-26: Iniciar inscripción muestra el paso de acuse por-examen primero.
  const iniciarInscripcion = (examenId: string) => setExamenPendienteAcuse(examenId);

  const completarInscripcionTrasAcuse = async () => {
    if (!examenPendienteAcuse) return;
    const examenId = examenPendienteAcuse;
    setExamenPendienteAcuse(null); setInscribiendoId(examenId);
    const nueva = await api.inscribir(examenId);
    setInscripciones((prev) => [nueva, ...prev.filter((i) => i.examen_id !== examenId)]);
    setInscribiendoId(null);
  };

  if (examenPendienteAcuse) {
    return (
      <AcuseExamen
        examenId={examenPendienteAcuse}
        onConfirmado={completarInscripcionTrasAcuse}
        onCancelar={() => setExamenPendienteAcuse(null)}
      />
    );
  }

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Materias disponibles</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">Seleccioná una materia para ver sus comisiones y exámenes disponibles.</p>
        </header>

        {cargandoMaterias ? (
          <Card className="flex items-center gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[20px]" />
            <span className="text-body-md">Cargando materias…</span>
          </Card>
        ) : (
          <div className="space-y-sm">
            {materias.map((materia) => (
              <MateriaCard
                key={materia.id}
                materia={materia}
                activa={materiaSeleccionada?.id === materia.id}
                cargandoComisiones={cargandoComisiones}
                comisiones={comisiones}
                comisionSeleccionada={comisionSeleccionada}
                cargandoExamenes={cargandoExamenes}
                examenes={examenes}
                inscripciones={inscripciones}
                inscribiendoId={inscribiendoId}
                onSelect={() => seleccionarMateria(materia)}
                onSelectComision={seleccionarComision}
                onInscribir={iniciarInscripcion}
              />
            ))}
          </div>
        )}
      </div>
    </StudentShell>
  );
}
