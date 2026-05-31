// Portal del alumno — Exploración Materia → Comisión → Examen (C-21)
import { useEffect, useState } from 'react';
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { api } from '../lib/api';
import type { Materia, Comision, Examen, Inscripcion } from '../lib/types';

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

  // Carga inicial
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

  // Cargar comisiones al seleccionar materia
  const seleccionarMateria = async (materia: Materia) => {
    if (materiaSeleccionada?.id === materia.id) {
      setMateriaSeleccionada(null);
      setComisionSeleccionada(null);
      setComisiones([]);
      setExamenes([]);
      return;
    }
    setMateriaSeleccionada(materia);
    setComisionSeleccionada(null);
    setExamenes([]);
    setCargandoComisiones(true);
    const coms = await api.comisionesDeMateria(materia.id);
    setComisiones(coms);
    setCargandoComisiones(false);
  };

  // Cargar exámenes al seleccionar comisión
  const seleccionarComision = async (comision: Comision) => {
    if (comisionSeleccionada?.id === comision.id) {
      setComisionSeleccionada(null);
      setExamenes([]);
      return;
    }
    setComisionSeleccionada(comision);
    setCargandoExamenes(true);
    const exams = await api.examenesDeComision(comision.id);
    setExamenes(exams);
    setCargandoExamenes(false);
  };

  // Inscribir al alumno a un examen
  const inscribir = async (examenId: string) => {
    setInscribiendoId(examenId);
    const nueva = await api.inscribir(examenId);
    setInscripciones((prev) => {
      const sin = prev.filter((i) => i.examen_id !== examenId);
      return [nueva, ...sin];
    });
    setInscribiendoId(null);
  };

  const estaInscripto = (examenId: string) =>
    inscripciones.some((i) => i.examen_id === examenId);

  const ESTADO_EXAMEN_LABEL: Record<Examen['estado'], string> = {
    borrador: 'Borrador',
    programado: 'Programado',
    en_curso: 'En curso',
    finalizado: 'Finalizado',
  };

  const ESTADO_EXAMEN_TONE: Record<Examen['estado'], 'neutral' | 'primary' | 'success' | 'warning' | 'error'> = {
    borrador: 'neutral',
    programado: 'primary',
    en_curso: 'success',
    finalizado: 'neutral',
  };

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Materias disponibles</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Seleccioná una materia para ver sus comisiones y exámenes disponibles.
          </p>
        </header>

        {/* Lista de materias */}
        {cargandoMaterias ? (
          <Card className="flex items-center gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[20px]" />
            <span className="text-body-md">Cargando materias…</span>
          </Card>
        ) : (
          <div className="space-y-sm">
            {materias.map((materia) => {
              const activa = materiaSeleccionada?.id === materia.id;
              return (
                <div key={materia.id}>
                  <button
                    onClick={() => seleccionarMateria(materia)}
                    className={`w-full flex items-center gap-md p-md rounded-xl border transition-colors text-left ${
                      activa
                        ? 'bg-primary-fixed border-primary/30 text-on-primary-fixed-variant'
                        : 'bg-surface-container-lowest border-outline-variant/40 hover:bg-surface-container text-on-surface'
                    }`}
                  >
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${activa ? 'bg-primary text-on-primary' : 'bg-secondary-container text-on-secondary'}`}>
                      <Icon name="school" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-label-md font-semibold">{materia.nombre}</p>
                      <p className={`text-label-sm ${activa ? 'text-on-primary-fixed-variant/70' : 'text-on-surface-variant'}`}>{materia.codigo} · {materia.descripcion}</p>
                    </div>
                    <Icon name={activa ? 'expand_less' : 'expand_more'} className="text-[22px] shrink-0" />
                  </button>

                  {/* Comisiones de la materia seleccionada */}
                  {activa && (
                    <div className="mt-sm ml-lg space-y-sm">
                      {cargandoComisiones ? (
                        <div className="flex items-center gap-sm text-on-surface-variant px-md py-sm">
                          <Icon name="progress_activity" className="ae-spin text-[18px]" />
                          <span className="text-label-md">Cargando comisiones…</span>
                        </div>
                      ) : comisiones.length === 0 ? (
                        <p className="text-label-md text-on-surface-variant px-md py-sm">No hay comisiones disponibles.</p>
                      ) : (
                        comisiones.map((comision) => {
                          const comActiva = comisionSeleccionada?.id === comision.id;
                          return (
                            <div key={comision.id}>
                              <button
                                onClick={() => seleccionarComision(comision)}
                                className={`w-full flex items-center gap-md px-md py-sm rounded-xl border transition-colors text-left ${
                                  comActiva
                                    ? 'bg-secondary-container border-secondary/20'
                                    : 'bg-surface-container border-outline-variant/30 hover:bg-surface-container-high'
                                }`}
                              >
                                <Icon name="groups" className="text-on-surface-variant shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-label-md font-semibold text-on-surface">{comision.nombre}</p>
                                  <p className="text-label-sm text-on-surface-variant">
                                    {comision.docente} · {comision.horario}
                                  </p>
                                </div>
                                <Icon name={comActiva ? 'expand_less' : 'expand_more'} className="text-[20px] text-on-surface-variant shrink-0" />
                              </button>

                              {/* Exámenes de la comisión seleccionada */}
                              {comActiva && (
                                <div className="mt-sm ml-lg space-y-sm">
                                  {cargandoExamenes ? (
                                    <div className="flex items-center gap-sm text-on-surface-variant px-md py-sm">
                                      <Icon name="progress_activity" className="ae-spin text-[18px]" />
                                      <span className="text-label-md">Cargando exámenes…</span>
                                    </div>
                                  ) : examenes.length === 0 ? (
                                    <p className="text-label-md text-on-surface-variant px-md py-sm">No hay exámenes en esta comisión.</p>
                                  ) : (
                                    examenes.map((examen) => {
                                      const inscripto = estaInscripto(examen.id);
                                      const inscribiendo = inscribiendoId === examen.id;
                                      const fecha = new Date(examen.inicio);
                                      const puedeInscribirse = examen.estado === 'programado' && !inscripto;
                                      return (
                                        <Card key={examen.id} className="flex items-center gap-md">
                                          <div className="flex-1 min-w-0">
                                            <p className="text-label-md font-semibold text-on-surface">{examen.nombre}</p>
                                            <p className="text-label-sm text-on-surface-variant">
                                              {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })} · {examen.duracion_min} min
                                            </p>
                                          </div>
                                          <div className="flex items-center gap-sm shrink-0">
                                            <Badge tone={ESTADO_EXAMEN_TONE[examen.estado]} dot>
                                              {ESTADO_EXAMEN_LABEL[examen.estado]}
                                            </Badge>
                                            {inscripto ? (
                                              <Badge tone="success" dot>Inscripto</Badge>
                                            ) : puedeInscribirse ? (
                                              <Button
                                                variant="secondary"
                                                onClick={() => inscribir(examen.id)}
                                                disabled={inscribiendo}
                                                className="h-9 px-md text-label-sm"
                                              >
                                                {inscribiendo ? (
                                                  <span className="inline-flex items-center gap-xs">
                                                    <Icon name="progress_activity" className="ae-spin text-[16px]" />
                                                    Inscribiendo…
                                                  </span>
                                                ) : 'Inscribirme'}
                                              </Button>
                                            ) : null}
                                          </div>
                                        </Card>
                                      );
                                    })
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </StudentShell>
  );
}
