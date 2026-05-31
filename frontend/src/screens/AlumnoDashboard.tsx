// Portal del alumno — Dashboard de aterrizaje post-login (C-21)
import { useEffect, useState } from 'react';
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { Inscripcion } from '../lib/types';

export default function AlumnoDashboard() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);

  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [puedeRendir, setPuedeRendir] = useState<boolean | null>(null);
  const [razonBloqueo, setRazonBloqueo] = useState<string | undefined>();
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [insc, gate] = await Promise.all([
        api.misInscripciones(),
        api.puedeRendir(),
      ]);
      if (cancelado) return;
      setInscripciones(insc);
      setPuedeRendir(gate.puede);
      setRazonBloqueo(gate.razon);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const proximos = inscripciones.filter(
    (i) => i.estado === 'inscripto' || i.estado === 'habilitado'
  );

  const ESTADO_BADGE: Record<Inscripcion['estado'], { label: string; tone: 'neutral' | 'primary' | 'success' | 'warning' | 'error' }> = {
    inscripto: { label: 'Inscripto', tone: 'primary' },
    pendiente: { label: 'Pendiente', tone: 'warning' },
    habilitado: { label: 'Habilitado', tone: 'success' },
    rendido: { label: 'Rendido', tone: 'neutral' },
  };

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        {/* Saludo */}
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
            Hola, {principal?.nombre ?? 'estudiante'} 👋
          </h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            {principal?.email} · UTN Regional Mendoza
          </p>
        </header>

        {/* Banner perfil incompleto */}
        {puedeRendir === false && (
          <div className="flex items-start gap-md bg-warning-container border border-warning/30 rounded-xl p-md">
            <Icon name="warning" className="text-warning text-[22px] shrink-0 mt-base" fill />
            <div className="flex-1 min-w-0">
              <p className="text-label-md font-semibold text-on-surface">Completá tu perfil antes de rendir</p>
              <p className="text-label-sm text-on-surface-variant mt-base">{razonBloqueo}</p>
            </div>
            <Button variant="outline" onClick={() => navigate('/alumno/perfil')} className="shrink-0 h-9 px-md text-label-sm">
              Completar perfil
            </Button>
          </div>
        )}

        {/* Próximos exámenes */}
        <section>
          <div className="flex items-center justify-between mb-md">
            <h2 className="font-headline text-title-lg text-on-surface">Próximos exámenes</h2>
            <button onClick={() => navigate('/alumno/mis-examenes')} className="text-label-sm text-primary hover:underline">
              Ver todos
            </button>
          </div>

          {cargando ? (
            <Card className="flex items-center gap-sm text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[20px]" />
              <span className="text-body-md">Cargando inscripciones…</span>
            </Card>
          ) : proximos.length === 0 ? (
            <Card className="text-center py-xl">
              <Icon name="event_busy" className="text-[40px] text-on-surface-variant mb-md" />
              <p className="text-body-md text-on-surface-variant">No tenés exámenes próximos.</p>
              <Button variant="secondary" onClick={() => navigate('/alumno/materias')} className="mt-md" icon="add_circle">
                Inscribite a un examen
              </Button>
            </Card>
          ) : (
            <div className="space-y-sm">
              {proximos.map((insc) => {
                const badge = ESTADO_BADGE[insc.estado];
                const fecha = new Date(insc.fecha);
                return (
                  <Card key={insc.id} className="flex items-center gap-md">
                    <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                      <Icon name="event" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-label-md font-semibold text-on-surface truncate">{insc.nombre_examen}</p>
                      <p className="text-label-sm text-on-surface-variant">{insc.nombre_materia} · {fecha.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}</p>
                    </div>
                    <Badge tone={badge.tone} dot>{badge.label}</Badge>
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        {/* Accesos rápidos */}
        <section>
          <h2 className="font-headline text-title-lg text-on-surface mb-md">Acceso rápido</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
            <button
              onClick={() => navigate('/alumno/materias')}
              className="flex items-center gap-md p-md bg-surface-container-lowest border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-left"
            >
              <div className="w-11 h-11 rounded-xl bg-secondary-container text-on-secondary flex items-center justify-center shrink-0">
                <Icon name="menu_book" />
              </div>
              <div>
                <p className="text-label-md font-semibold text-on-surface">Mis materias</p>
                <p className="text-label-sm text-on-surface-variant">Explorar y inscribirse</p>
              </div>
              <Icon name="arrow_forward" className="text-on-surface-variant ml-auto" />
            </button>

            <button
              onClick={() => navigate('/alumno/mis-examenes')}
              className="flex items-center gap-md p-md bg-surface-container-lowest border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-left"
            >
              <div className="w-11 h-11 rounded-xl bg-secondary-container text-on-secondary flex items-center justify-center shrink-0">
                <Icon name="assignment" />
              </div>
              <div>
                <p className="text-label-md font-semibold text-on-surface">Mis exámenes</p>
                <p className="text-label-sm text-on-surface-variant">Ver inscripciones y estado</p>
              </div>
              <Icon name="arrow_forward" className="text-on-surface-variant ml-auto" />
            </button>

            <button
              onClick={() => navigate('/alumno/perfil')}
              className="flex items-center gap-md p-md bg-surface-container-lowest border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-left"
            >
              <div className="w-11 h-11 rounded-xl bg-secondary-container text-on-secondary flex items-center justify-center shrink-0">
                <Icon name="manage_accounts" />
              </div>
              <div>
                <p className="text-label-md font-semibold text-on-surface">Mi perfil</p>
                <p className="text-label-sm text-on-surface-variant">Consentimiento y biometría</p>
              </div>
              <Icon name="arrow_forward" className="text-on-surface-variant ml-auto" />
            </button>
          </div>
        </section>
      </div>
    </StudentShell>
  );
}
