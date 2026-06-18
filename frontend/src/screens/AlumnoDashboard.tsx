// Portal del alumno — Dashboard de aterrizaje post-login (C-21).
//
// Layout pensado para el alumno (no admin): header, dos cards compactas
// con counts personales (Materias / Exámenes) en estilo "personal" — fondo
// blanco, sin gradiente —, sección de Próximos exámenes con una lista, accesos
// rápidos en grid y un panel chico de Estado del perfil al pie.
import { useEffect, useMemo, useState } from 'react';
import { Card, Button, Icon, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { INSTITUTION } from '../config/institution';
import { nombreCompleto } from '../lib/types';
import type { Inscripcion, EstadoEnrollment } from '../lib/types';
import { QuickAccessCard } from './alumno/components/QuickAccessCard';
import { ExamenProximoCard } from './alumno/components/ExamenProximoCard';

const VIGENCIA_LABEL: Record<string, string> = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  caducada: 'Caducada',
  renovacion_requerida: 'Renovación requerida',
};

export default function AlumnoDashboard() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);
  const [puedeRendir, setPuedeRendir] = useState<boolean | null>(null);
  const [enrollment, setEnrollment] = useState<EstadoEnrollment | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [insc, gate, enr] = await Promise.all([api.misInscripciones(), api.puedeRendir(), api.getEnrollment()]);
      if (cancelado) return;
      setInscripciones(insc);
      setPuedeRendir(gate.puede);
      setEnrollment(enr);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const proximos = useMemo(
    () => inscripciones.filter((i) => i.estado === 'inscripto' || i.estado === 'habilitado'),
    [inscripciones],
  );
  const materias = useMemo(
    () => new Set(inscripciones.map((i) => i.materia_id)).size,
    [inscripciones],
  );

  const renderHeader = (centered = false) => (
    <header className={centered ? 'text-center' : ''}>
      <div className={`flex items-center gap-sm ${centered ? 'justify-center' : ''}`}>
        <h1 className="text-[22px] sm:text-[24px] font-semibold text-on-surface tracking-tight leading-tight">
          Hola, {nombreCompleto(principal) || 'estudiante'} 👋
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
      <p className="text-[13px] text-on-surface-variant mt-1">{principal?.email} · {INSTITUTION.nombreCorto}</p>
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
    const pasos = [
      { label: 'Consentimiento informado', done: !!enrollment?.consentimiento },
      { label: 'Captura biométrica de referencia', done: !!enrollment?.biometria },
    ];
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto min-h-[calc(100dvh-13rem)] flex flex-col gap-lg">
          {renderHeader(false)}
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full bg-warning-container border border-warning/30 rounded-lg p-lg sm:p-xl flex flex-col items-center text-center gap-md">
              <Icon name="warning" className="text-warning text-[32px] shrink-0" fill />
              <div className="space-y-base">
                <p className="text-[18px] font-semibold text-on-surface">Completá tu perfil antes de rendir</p>
                <p className="text-[13px] text-on-surface-variant max-w-md mx-auto">Antes de poder rendir necesitás completar estos pasos:</p>
              </div>
              <ul className="space-y-sm w-full max-w-xs mx-auto text-left">
                {pasos.map((p) => (
                  <li key={p.label} className="flex items-center gap-sm">
                    <Icon
                      name={p.done ? 'check_circle' : 'radio_button_unchecked'}
                      className={`text-[22px] shrink-0 ${p.done ? 'text-success' : 'text-on-surface-variant'}`}
                      fill={p.done}
                    />
                    <span className={`text-body-md ${p.done ? 'text-on-surface-variant line-through' : 'text-on-surface font-medium'}`}>{p.label}</span>
                    {p.done && <span className="ml-auto text-label-sm text-success font-semibold shrink-0">Listo</span>}
                  </li>
                ))}
              </ul>
              <Button
                variant="outline"
                onClick={() => navigate('/alumno/perfil')}
                className="w-full sm:w-auto"
              >
                Completar perfil
              </Button>
            </div>
          </div>
        </div>
      </StudentShell>
    );
  }

  const vigencia = enrollment?.biometria?.vigencia ?? 'vigente';

  return (
    <StudentShell>
      <div className="max-w-2xl lg:max-w-5xl xl:max-w-6xl 2xl:max-w-7xl mx-auto space-y-xl">
        {renderHeader()}

        {/* Counts personales: 2 cards SOBRIAS (fondo blanco, sin gradiente) —
            informan, no hacen "ruido admin". */}
        <div className="grid grid-cols-2 gap-md">
          <ContadorPersonal icon="menu_book" label="Mis materias" value={materias} />
          <ContadorPersonal icon="assignment" label="Mis exámenes" value={inscripciones.length} />
        </div>

        <section>
          <div className="flex items-center justify-between mb-md">
            <h2 className="text-[16px] font-semibold text-on-surface">Próximos exámenes</h2>
            <button onClick={() => navigate('/alumno/mis-examenes')} className="text-[13px] text-primary hover:underline">Ver todos</button>
          </div>
          {cargando ? (
            <LoadingSpinner size="sm" label="Cargando inscripciones…" />
          ) : proximos.length === 0 ? (
            <Card className="text-center py-xl">
              <Icon name="event_busy" className="text-[36px] text-on-surface-variant mb-md" />
              <p className="text-[14px] text-on-surface-variant">No tenés exámenes próximos.</p>
              <Button variant="outline" size="sm" onClick={() => navigate('/alumno/materias')} className="mt-md" icon="add_circle">
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
          <h2 className="text-[16px] font-semibold text-on-surface mb-md">Acceso rápido</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-md">
            <QuickAccessCard icon="menu_book" title="Mis materias" description="Explorar y inscribirse" onClick={() => navigate('/alumno/materias')} />
            <QuickAccessCard icon="assignment" title="Mis exámenes" description="Ver inscripciones y estado" onClick={() => navigate('/alumno/mis-examenes')} />
            <QuickAccessCard icon="manage_accounts" title="Mi perfil" description="Consentimiento y biometría" onClick={() => navigate('/alumno/perfil')} />
          </div>
        </section>

        <section>
          <h2 className="text-[16px] font-semibold text-on-surface mb-md">Estado del perfil</h2>
          <Card padded={false}>
            <div className="p-md space-y-3">
              <EstadoItem
                ok={!!enrollment?.consentimiento}
                label="Consentimiento informado"
                hint={enrollment?.consentimiento ? `Versión ${enrollment.consentimiento.version}` : 'Pendiente'}
              />
              <EstadoItem
                ok={vigencia === 'vigente'}
                warn={vigencia === 'por_vencer' || vigencia === 'renovacion_requerida'}
                label="Verificación biométrica"
                hint={VIGENCIA_LABEL[vigencia] ?? 'Vigente'}
              />
            </div>
          </Card>
        </section>
      </div>
    </StudentShell>
  );
}

/** Card sobria, fondo blanco, borde sutil, número grande + label — para counts
 *  del propio alumno (no es un KPI ni admin). */
function ContadorPersonal({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-white border border-surface-200 rounded-lg">
      <div className="w-10 h-10 rounded-md bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[20px]" />
      </div>
      <div className="min-w-0">
        <p className="text-[12.5px] text-on-surface-variant leading-tight">{label}</p>
        <p className="text-[22px] font-semibold text-on-surface leading-tight tabular-nums">{value}</p>
      </div>
    </div>
  );
}

function EstadoItem({ ok, warn = false, label, hint }: { ok: boolean; warn?: boolean; label: string; hint: string }) {
  const tono = ok && !warn ? 'success' : warn ? 'warning' : 'error';
  const iconName = ok && !warn ? 'check_circle' : warn ? 'warning' : 'radio_button_unchecked';
  const colorMap = {
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-on-surface-variant',
  } as const;
  return (
    <div className="flex items-center gap-3">
      <Icon name={iconName} className={`text-[22px] shrink-0 ${colorMap[tono]}`} fill={ok || warn} />
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-medium text-on-surface leading-tight">{label}</p>
        <p className="text-[12px] text-on-surface-variant leading-tight mt-0.5">{hint}</p>
      </div>
    </div>
  );
}
