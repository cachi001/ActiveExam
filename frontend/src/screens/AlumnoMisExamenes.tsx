// Portal del alumno — Mis inscripciones a exámenes (C-21)
import { useEffect, useState } from 'react';
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { api } from '../lib/api';
import type { Inscripcion } from '../lib/types';

export default function AlumnoMisExamenes() {
  const navigate = useNavigate();
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [puedeRendir, setPuedeRendir] = useState<boolean | null>(null);
  const [razonBloqueo, setRazonBloqueo] = useState<string | undefined>();
  const [cargando, setCargando] = useState(true);
  const [verificandoId, setVerificandoId] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [insc, gate] = await Promise.all([api.misInscripciones(), api.puedeRendir()]);
      if (cancelado) return;
      setInscripciones(insc);
      setPuedeRendir(gate.puede);
      setRazonBloqueo(gate.razon);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  // Verificar gate y navegar a rendir
  const handleRendir = async (inscripcionId: string) => {
    setVerificandoId(inscripcionId);
    const gate = await api.puedeRendir();
    setVerificandoId(null);
    if (gate.puede) {
      navigate('/requisitos');
    } else {
      setPuedeRendir(false);
      setRazonBloqueo(gate.razon);
    }
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

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mis exámenes</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Registro de tus inscripciones con estado y acción siguiente.
          </p>
        </header>

        {/* Banner de perfil incompleto (visible cuando hay exámenes habilitados y perfil incompleto) */}
        {puedeRendir === false && inscripciones.some((i) => i.estado === 'habilitado') && (
          <div className="flex items-start gap-md bg-warning-container border border-warning/30 rounded-xl p-md">
            <Icon name="warning" className="text-warning text-[22px] shrink-0 mt-base" fill />
            <div className="flex-1 min-w-0">
              <p className="text-label-md font-semibold text-on-surface">Tu perfil está incompleto</p>
              <p className="text-label-sm text-on-surface-variant mt-base">{razonBloqueo}</p>
            </div>
            <Button variant="outline" onClick={() => navigate('/alumno/perfil')} className="shrink-0 h-9 px-md text-label-sm">
              Completar perfil
            </Button>
          </div>
        )}

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

                  {/* Acción siguiente según estado */}
                  {insc.estado === 'habilitado' && (
                    <div className="flex items-center gap-sm pt-sm border-t border-outline-variant/40">
                      {puedeRendir ? (
                        <Button
                          onClick={() => handleRendir(insc.id)}
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
                      ) : (
                        <>
                          <p className="text-label-sm text-on-surface-variant flex-1">Completá tu perfil para poder rendir.</p>
                          <Button
                            variant="outline"
                            onClick={() => navigate('/alumno/perfil')}
                            icon="manage_accounts"
                            className="h-10"
                          >
                            Completar perfil
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
