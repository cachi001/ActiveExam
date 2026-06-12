// Portal del alumno — Dashboard de aterrizaje post-login (C-21)
import { useEffect, useState } from 'react';
import { Card, Button, Icon, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { INSTITUTION } from '../config/institution';
import type { Inscripcion } from '../lib/types';
import { QuickAccessCard } from './alumno/components/QuickAccessCard';
import { ExamenProximoCard } from './alumno/components/ExamenProximoCard';

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
      const [insc, gate] = await Promise.all([api.misInscripciones(), api.puedeRendir()]);
      if (cancelado) return;
      setInscripciones(insc);
      setPuedeRendir(gate.puede);
      setRazonBloqueo(gate.razon);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const proximos = inscripciones.filter((i) => i.estado === 'inscripto' || i.estado === 'habilitado');

  const Header = (
    <header>
      <div className="flex items-center gap-sm">
        <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
          Hola, {principal?.nombre ?? 'estudiante'} 👋
        </h1>
        <HelpButton title="Tu dashboard">
          <p>
            Esta es tu pantalla de inicio: vas a ver tus próximos exámenes y si tu perfil está
            listo para rendir.
          </p>
          <p>
            Antes de rendir necesitás <strong>completar tu perfil</strong> desde <em>Mi perfil</em>:
            aceptar el consentimiento informado y registrar tu foto y verificación facial. Si te
            falta algo, te lo vamos a avisar acá arriba con un cartel.
          </p>
          <p>
            Desde el menú lateral llegás a tus materias e inscripciones, y a tus exámenes
            programados.
          </p>
        </HelpButton>
      </div>
      <p className="text-body-md text-on-surface-variant mt-xs">{principal?.email} · {INSTITUTION.nombreCorto}</p>
    </header>
  );

  // C-66: bloquear render hasta saber si el perfil está completo —
  // sin esto el layout izquierdo flashea antes de saltar al centrado.
  if (puedeRendir === null) {
    return (
      <StudentShell>
        <div className="min-h-[calc(100vh-180px)] flex items-center justify-center">
          <LoadingSpinner />
        </div>
      </StudentShell>
    );
  }

  if (puedeRendir === false) {
    return (
      <StudentShell>
        <div className="min-h-[calc(100vh-180px)] flex items-center justify-center px-md">
          <div className="w-full max-w-2xl space-y-xl">
            {Header}
            <div className="bg-warning-container border border-warning/30 rounded-xl p-md sm:p-lg">
              <div className="flex flex-col sm:flex-row sm:items-center gap-md">
                <div className="flex items-start gap-md flex-1 min-w-0">
                  <Icon name="warning" className="text-warning text-[28px] shrink-0 mt-base" fill />
                  <div className="flex-1 min-w-0">
                    <p className="text-title-md font-semibold text-on-surface">Completá tu perfil antes de rendir</p>
                    <p className="text-body-md text-on-surface-variant mt-base">{razonBloqueo}</p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  onClick={() => navigate('/alumno/perfil')}
                  className="shrink-0 w-full sm:w-auto"
                >
                  Completar perfil
                </Button>
              </div>
            </div>
          </div>
        </div>
      </StudentShell>
    );
  }

  return (
    <StudentShell>
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl 2xl:max-w-7xl mx-auto space-y-xl">
        {Header}

        {puedeRendir === true && (
          <>
            <section>
              <div className="flex items-center justify-between mb-md">
                <h2 className="font-headline text-title-lg text-on-surface">Próximos exámenes</h2>
                <button onClick={() => navigate('/alumno/mis-examenes')} className="text-label-sm text-primary hover:underline">Ver todos</button>
              </div>
              {cargando ? (
                <Card>
                  <LoadingSpinner size="sm" label="Cargando inscripciones…" />
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
                  {proximos.map((insc) => <ExamenProximoCard key={insc.id} inscripcion={insc} />)}
                </div>
              )}
            </section>

            <section>
              <h2 className="font-headline text-title-lg text-on-surface mb-md">Acceso rápido</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-md">
                <QuickAccessCard icon="menu_book" title="Mis materias" description="Explorar y inscribirse" onClick={() => navigate('/alumno/materias')} />
                <QuickAccessCard icon="assignment" title="Mis exámenes" description="Ver inscripciones y estado" onClick={() => navigate('/alumno/mis-examenes')} />
                <QuickAccessCard icon="manage_accounts" title="Mi perfil" description="Consentimiento y biometría" onClick={() => navigate('/alumno/perfil')} />
              </div>
            </section>
          </>
        )}
      </div>
    </StudentShell>
  );
}
