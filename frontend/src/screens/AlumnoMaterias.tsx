// Portal del alumno — Exploración Materia → Comisión → Examen (C-21)
// C-69: datos REALES desde el backend (materias/comisiones/exámenes importados de Moodle).
//       El leaf es un examen de contenido: el alumno lo rinde directo (sin inscripción demo).
import { useEffect, useState } from 'react';
import { BackButton, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { Materia, Comision, Examen, ExamenContenidoResumen } from '../lib/types';
import { MateriaCard } from './alumno/components/MateriaCard';

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

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const mats = await api.materiasDisponibles();
      if (cancelado) return;
      setMaterias(mats);
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
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl mx-auto space-y-xl">
        <BackButton onClick={() => navigate('/alumno')} />
        <header>
          <div className="flex items-center gap-sm">
            <h1 className="text-[22px] sm:text-[24px] font-semibold text-on-surface tracking-tight">Materias disponibles</h1>
            <HelpButton title="Materias">
              <p>
                Explorá el catálogo de <strong>materias y comisiones</strong>: entrá a una materia
                para ver sus comisiones; entrá a una comisión para ver los exámenes disponibles.
              </p>
              <p>
                Cada examen se rinde directamente: al tocar <em>Rendir</em> verificamos tu perfil
                (consentimiento y biometría) y te llevamos a los requisitos previos.
              </p>
            </HelpButton>
          </div>
          <p className="text-[13px] text-on-surface-variant mt-1">Seleccioná una materia para ver sus comisiones y exámenes disponibles.</p>
        </header>

        {cargandoMaterias ? (
          <div className="min-h-[60vh] flex items-center justify-center">
            <LoadingSpinner label="Cargando materias…" />
          </div>
        ) : materias.length === 0 ? (
          <p className="text-[13px] text-on-surface-variant px-md py-lg">
            No hay materias disponibles. Un administrador debe importar exámenes y asociarlos a una comisión.
          </p>
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
                rindiendoId={rindiendoId}
                onSelect={() => seleccionarMateria(materia)}
                onSelectComision={seleccionarComision}
                onRendir={rendirExamen}
              />
            ))}
          </div>
        )}
      </div>
    </StudentShell>
  );
}
