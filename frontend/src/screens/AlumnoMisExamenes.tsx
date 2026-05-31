// Portal del alumno — Mis inscripciones a exámenes (C-21)
// C-22: puedeRendir usa estado tipado real (sin parseo por substring).
// C-26: gate en capas — muestra "Completar acuse del examen" cuando falta el acuse por-examen.
import { useEffect, useState } from 'react';
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import AcuseExamen from './AcuseExamen';
import type { Inscripcion } from '../lib/types';

/** Resultado del gate por-examen. */
interface GatePorExamen {
  puede: boolean;
  codigo?: string;
  razon?: string;
}

export default function AlumnoMisExamenes() {
  const navigate = useNavigate();
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [verificandoId, setVerificandoId] = useState<string | null>(null);

  // C-26: resultado del gate EN CAPAS por examen_id (perfil + acuse)
  const [gatesPorExamen, setGatesPorExamen] = useState<Record<string, GatePorExamen>>({});

  // C-26: examen_id para el que se está completando el acuse desde Mis Exámenes
  const [examenCompletandoAcuse, setExamenCompletandoAcuse] = useState<string | null>(null);

  /** Evalúa el gate en capas para todas las inscripciones habilitadas. */
  const evaluarGates = async (insc: Inscripcion[]) => {
    const habilitadas = insc.filter((i) => i.estado === 'habilitado');
    const resultados = await Promise.all(
      habilitadas.map((i) => api.puedeRendir(i.examen_id).then((g) => [i.examen_id, g] as const))
    );
    setGatesPorExamen(Object.fromEntries(resultados));
  };

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [insc, enrollment] = await Promise.all([
        api.misInscripciones(),
        api.getEnrollment(),
      ]);
      if (cancelado) return;
      setInscripciones(insc);
      setEnrollmentStatus(enrollment); // sincroniza store con estado real (C-22)
      await evaluarGates(insc);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Verificar gate y navegar a rendir.
  // C-26: pasa el examenId para evaluar gate en capas (perfil + acuse por-examen).
  const handleRendir = async (inscripcion: Inscripcion) => {
    setVerificandoId(inscripcion.id);
    const gate = await api.puedeRendir(inscripcion.examen_id);
    setVerificandoId(null);
    if (gate.puede) {
      navigate('/requisitos');
    } else {
      // Actualizar el gate de este examen en el estado local
      setGatesPorExamen((prev) => ({ ...prev, [inscripcion.examen_id]: gate }));
      // Si falta el acuse, el banner inline se mostrará (acuse_examen_faltante)
    }
  };

  /** Llamado cuando el alumno completa el acuse desde Mis Exámenes. */
  const handleAcuseCompletado = async () => {
    if (!examenCompletandoAcuse) return;
    const examenId = examenCompletandoAcuse;
    setExamenCompletandoAcuse(null);
    // Re-evaluar el gate para este examen
    const gate = await api.puedeRendir(examenId);
    setGatesPorExamen((prev) => ({ ...prev, [examenId]: gate }));
  };

  const ESTADO_CONFIG: Record<Inscripcion['estado'], {
    label: string;
    tone: 'neutral' | 'primary' | 'success' | 'warning' | 'error';
    icon: string;
  }> = {
    inscripto: { label: 'Inscripto', tone: 'primary', icon: 'check_circle' },
    pendiente: { label: 'Pendiente', tone: 'warning', icon: 'schedule' },
    habilitado: { label: 'Habilitado para rendir', tone: 'success', icon: 'verified' },
    rendido: { label: 'Rendido', tone: 'neutral', icon: 'assignment_turned_in' },
  };

  // C-26: Si el alumno está completando el acuse para un examen desde aquí, mostrar la pantalla de acuse.
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
          <p className="text-body-md text-on-surface-variant mt-xs">
            Registro de tus inscripciones con estado y acción siguiente.
          </p>
        </header>

        {/* Lista de inscripciones */}
        {cargando ? (
          <Card className="flex items-center gap-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[20px]" />
            <span className="text-body-md">Cargando inscripciones…</span>
          </Card>
        ) : inscripciones.length === 0 ? (
          <Card className="text-center py-xl">
            <Icon name="event_busy" className="text-[40px] text-on-surface-variant mb-md" />
            <p className="text-body-md text-on-surface font-semibold">No tenés inscripciones registradas</p>
            <p className="text-label-sm text-on-surface-variant mt-xs mb-md">
              Explorá las materias disponibles e inscribite a un examen.
            </p>
            <Button variant="secondary" onClick={() => navigate('/alumno/materias')} icon="add_circle">
              Ver materias disponibles
            </Button>
          </Card>
        ) : (
          <div className="space-y-sm">
            {inscripciones.map((insc) => {
              const config = ESTADO_CONFIG[insc.estado];
              const verificando = verificandoId === insc.id;
              const fecha = new Date(insc.fecha);
              // C-26: gate en capas por examen
              const gate = gatesPorExamen[insc.examen_id];
              const puedeRendirEsteExamen = gate?.puede ?? false;
              const codigoGate = gate?.codigo;

              return (
                <Card key={insc.id} className="space-y-md">
                  <div className="flex items-start gap-md">
                    <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                      <Icon name={config.icon} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-label-md font-semibold text-on-surface">{insc.nombre_examen}</p>
                      <p className="text-label-sm text-on-surface-variant">
                        {insc.nombre_materia} · {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </p>
                    </div>
                    <Badge tone={config.tone} dot>{config.label}</Badge>
                  </div>

                  {/* Acción siguiente según estado — gate en capas C-26 */}
                  {insc.estado === 'habilitado' && (
                    <div className="flex items-center gap-sm pt-sm border-t border-outline-variant/40">
                      {puedeRendirEsteExamen ? (
                        // Gate completo: puede rendir
                        <Button
                          onClick={() => handleRendir(insc)}
                          disabled={verificando}
                          icon={verificando ? undefined : 'play_arrow'}
                          className="h-10"
                        >
                          {verificando ? (
                            <span className="inline-flex items-center gap-xs">
                              <Icon name="progress_activity" className="ae-spin text-[16px]" />
                              Verificando…
                            </span>
                          ) : 'Rendir'}
                        </Button>
                      ) : codigoGate === 'acuse_examen_faltante' ? (
                        // Capa 2 bloqueada: falta acuse por-examen → derivar a completarlo (no sancionar)
                        <>
                          <p className="text-label-sm text-on-surface-variant flex-1">
                            Falta el acuse de consentimiento para este examen.
                          </p>
                          <Button
                            variant="secondary"
                            onClick={() => setExamenCompletandoAcuse(insc.examen_id)}
                            icon="assignment_turned_in"
                            className="h-10 shrink-0"
                          >
                            Completar acuse del examen
                          </Button>
                        </>
                      ) : (
                        // Capa 1 bloqueada: perfil incompleto (códigos de C-22)
                        <>
                          <p className="text-label-sm text-on-surface-variant flex-1">
                            {codigoGate === 'biometria_caducada'
                              ? 'Tu referencia biométrica caducó. Renovála para poder rendir.'
                              : codigoGate === 'biometria_renovacion_requerida'
                                ? 'Se requiere renovación de biometría. Actualizá tu perfil.'
                                : codigoGate === 'consentimiento_version_desactualizada'
                                  ? 'Hay una nueva versión del consentimiento. Actualizá tu perfil.'
                                  : 'Completá tu perfil para poder rendir.'}
                          </p>
                          <Button
                            variant={codigoGate === 'biometria_caducada' ? 'danger' : 'outline'}
                            onClick={() => navigate('/alumno/perfil')}
                            icon="manage_accounts"
                            className="h-10 shrink-0"
                          >
                            {codigoGate === 'biometria_caducada' ? 'Renovar biometría' : 'Completar perfil'}
                          </Button>
                        </>
                      )}
                    </div>
                  )}

                  {insc.estado === 'rendido' && (
                    <div className="pt-sm border-t border-outline-variant/40">
                      <span className="text-label-sm text-on-surface-variant">Examen completado. El resultado está sujeto a revisión académica.</span>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </StudentShell>
  );
}
