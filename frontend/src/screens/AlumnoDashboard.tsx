// Portal del alumno — Dashboard de aterrizaje post-login (C-21).
//
// Layout pensado para el alumno (no admin): header, dos cards compactas
// con counts personales (Materias / Exámenes) en estilo "personal" — fondo
// blanco, sin gradiente —, sección de Exámenes disponibles y accesos
// rápidos en grid y un panel chico de Estado del perfil al pie.
//
// FUENTES DE DATOS (modo real, USE_REAL_BACKEND=1):
//   • Materias disponibles: GET /api/v1/exam-content/materias (api.materiasDisponibles)
//   • Exámenes disponibles: GET /api/v1/exam-content          (api.listarExamenesContenido)
//   • Inscripciones: SIN endpoint real en slim → vacío honesto (no se inventan datos)
//
// FUENTES DE DATOS (modo demo, USE_REAL_BACKEND=0):
//   • Todo viene de api.misInscripciones() (datos en memoria)
import { useEffect, useMemo, useState } from 'react';
import { Card, Button, Icon, LoadingSpinner } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { INSTITUTION } from '../config/institution';
import { nombreCompleto } from '../lib/types';
import type { Inscripcion, EstadoEnrollment, ExamenContenidoResumen } from '../lib/types';
import { QuickAccessCard } from './alumno/components/QuickAccessCard';
import { ExamenProximoCard } from './alumno/components/ExamenProximoCard';
import { examenContenidoSubtitulo } from './dashboards.helpers';

const VIGENCIA_LABEL: Record<string, string> = {
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  caducada: 'Caducada',
  renovacion_requerida: 'Renovación requerida',
};

export default function AlumnoDashboard() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);

  // Demo mode: inscripciones del alumno (datos en memoria).
  const [inscripciones, setInscripciones] = useState<Inscripcion[]>([]);

  // Modo real: datos del catálogo oficial (sin inscripciones inventadas).
  const [materiasCount, setMateriasCount] = useState(0);
  const [examenesDisponibles, setExamenesDisponibles] = useState<ExamenContenidoResumen[]>([]);

  const [puedeRendir, setPuedeRendir] = useState<boolean | null>(null);
  const [gateCodigo, setGateCodigo] = useState<string | null>(null);
  const [enrollment, setEnrollment] = useState<EstadoEnrollment | null>(null);
  const [cargando, setCargando] = useState(true);

  const modoDemo = api.modoDemo;

  useEffect(() => {
    let cancelado = false;
    (async () => {
      if (modoDemo) {
        // Modo demo: usar datos en memoria (MIS_INSCRIPCIONES)
        const [insc, gate, enr] = await Promise.all([
          api.misInscripciones(),
          api.puedeRendir(),
          api.getEnrollment(),
        ]);
        if (cancelado) return;
        setInscripciones(insc);
        setPuedeRendir(gate.puede);
        setGateCodigo(gate.codigo ?? null);
        setEnrollment(enr);
      } else {
        // Modo real: fuentes reales; sin inscripciones (no hay endpoint en slim)
        const [materias, examenes, gate, enr] = await Promise.all([
          api.materiasDisponibles(),
          api.listarExamenesContenido(),
          api.puedeRendir(),
          api.getEnrollment(),
        ]);
        if (cancelado) return;
        setMateriasCount(materias.length);
        setExamenesDisponibles(examenes);
        setPuedeRendir(gate.puede);
        setGateCodigo(gate.codigo ?? null);
        setEnrollment(enr);
      }
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, [modoDemo]);

  // Demo: derivar counts desde inscripciones en memoria
  const proximos = useMemo(
    () => inscripciones.filter((i) => i.estado === 'inscripto' || i.estado === 'habilitado'),
    [inscripciones],
  );
  const materiasDeInscripciones = useMemo(
    () => new Set(inscripciones.map((i) => i.materia_id)).size,
    [inscripciones],
  );

  // Valores de display: modo real usa catálogo real; modo demo usa inscripciones.
  const displayMateriasCount = modoDemo ? materiasDeInscripciones : materiasCount;
  const displayExamenesCount = modoDemo ? inscripciones.length : examenesDisponibles.length;

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
    // El consentimiento puede EXISTIR pero estar desactualizado (el admin publicó una
    // versión nueva): en ese caso NO está "listo" — hay que renovarlo. No basta con
    // mirar si existe el acuse; usamos el código del gate para distinguirlo.
    const consentDesactualizado = gateCodigo === 'consentimiento_version_desactualizada';
    const consentListo = !!enrollment?.consentimiento && !consentDesactualizado;
    const pasos = [
      {
        label: consentDesactualizado
          ? 'Renovar el consentimiento (hay una versión nueva)'
          : 'Consentimiento informado',
        done: consentListo,
      },
      { label: 'Captura biométrica de referencia', done: !!enrollment?.biometria },
    ];
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto min-h-[calc(100dvh-13rem)] flex flex-col gap-lg">
          {renderHeader(false)}
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full bg-warning-container border border-warning-200 rounded-lg p-lg sm:p-xl flex flex-col items-center text-center gap-md">
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

        {/* Counts: 2 cards SOBRIAS (fondo blanco, sin gradiente).
            Modo real: del catálogo oficial (materias disponibles / exámenes importados).
            Modo demo: de las inscripciones en memoria. */}
        <div className="grid grid-cols-2 gap-md">
          <ContadorPersonal
            icon="menu_book"
            label="Mis materias"
            value={displayMateriasCount}
          />
          <ContadorPersonal
            icon="assignment"
            label={modoDemo ? 'Mis exámenes' : 'Exámenes disponibles'}
            value={displayExamenesCount}
          />
        </div>

        <div className="flex flex-col lg:flex-row gap-xl items-start">
          {/* Exámenes disponibles — columna principal (izquierda, ~70%) */}
          <section className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-md">
              <h2 className="text-[16px] font-semibold text-on-surface">
                {modoDemo ? 'Próximos exámenes' : 'Exámenes disponibles'}
              </h2>
              <button
                onClick={() => navigate('/alumno/mis-examenes')}
                className="text-[13px] text-primary hover:underline"
              >
                Ver todos
              </button>
            </div>

            {cargando ? (
              <LoadingSpinner size="sm" label={modoDemo ? 'Cargando inscripciones…' : 'Cargando catálogo…'} />
            ) : modoDemo ? (
              proximos.length === 0 ? (
                <Card className="text-center py-2xl min-h-[320px] flex flex-col items-center justify-center">
                  <Icon name="event_busy" className="text-[44px] text-on-surface-variant mb-md" />
                  <p className="text-[14px] text-on-surface-variant">No tenés exámenes próximos.</p>
                  <Button variant="outline" size="sm" onClick={() => navigate('/alumno/materias')} className="mt-md" icon="add_circle">
                    Inscribite a un examen
                  </Button>
                </Card>
              ) : (
                <div className="space-y-sm">
                  {proximos.map((insc) => <ExamenProximoCard key={insc.id} inscripcion={insc} />)}
                </div>
              )
            ) : (
              examenesDisponibles.length === 0 ? (
                <Card className="text-center py-2xl min-h-[320px] flex flex-col items-center justify-center">
                  <Icon name="assignment" className="text-[44px] text-on-surface-variant mb-md" />
                  <p className="text-[14px] text-on-surface-variant">No hay exámenes disponibles por el momento.</p>
                  <Button variant="outline" size="sm" onClick={() => navigate('/alumno/materias')} className="mt-md" icon="menu_book">
                    Explorar materias
                  </Button>
                </Card>
              ) : (
                <div className="space-y-sm">
                  {examenesDisponibles.map((e) => (
                    <ExamenCatalogoCard key={e.id} examen={e} onNavigate={() => navigate('/alumno/mis-examenes')} />
                  ))}
                </div>
              )
            )}
          </section>

          {/* Acceso rápido — columna secundaria (derecha, ~30%) */}
          <section className="w-full lg:w-64 xl:w-72 shrink-0">
            <h2 className="text-[16px] font-semibold text-on-surface mb-md">Acceso rápido</h2>
            <div className="flex flex-row lg:flex-col gap-md">
              <QuickAccessCard icon="menu_book" title="Mis materias" description="Explorar y inscribirse" onClick={() => navigate('/alumno/materias')} />
              <QuickAccessCard icon="assignment" title="Mis exámenes" description="Ver inscripciones y estado" onClick={() => navigate('/alumno/mis-examenes')} />
              <QuickAccessCard icon="manage_accounts" title="Mi perfil" description="Consentimiento y biometría" onClick={() => navigate('/alumno/perfil')} />
            </div>
          </section>
        </div>

        <section>
          <h2 className="text-[16px] font-semibold text-on-surface mb-md">Estado del perfil</h2>
          <div className="space-y-2">
            <EstadoItem
              ok={!!enrollment?.consentimiento}
              label="Consentimiento informado"
              hint={enrollment?.consentimiento ? `Versión ${enrollment.consentimiento.version}` : 'Pendiente — aceptá el consentimiento en Mi perfil'}
            />
            <EstadoItem
              ok={vigencia === 'vigente'}
              warn={vigencia === 'por_vencer' || vigencia === 'renovacion_requerida'}
              label="Verificación biométrica"
              hint={VIGENCIA_LABEL[vigencia] ?? 'Vigente'}
            />
          </div>
        </section>
      </div>
    </StudentShell>
  );
}

/** Card sobria, fondo blanco, borde sutil, número grande + label — para counts
 *  del propio alumno (no es un KPI ni admin). */
function ContadorPersonal({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-4 px-5 py-5 bg-white border border-surface-200 rounded-lg">
      <div className="w-9 h-9 rounded-md bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[18px]" />
      </div>
      <div className="min-w-0">
        <p className="text-[13px] text-on-surface-variant leading-tight">{label}</p>
        <p className="text-[28px] font-semibold text-on-surface leading-tight tabular-nums">{value}</p>
      </div>
    </div>
  );
}

/**
 * Card de examen del catálogo real (modo real).
 * Muestra titulo + materia/comision + cantidad de preguntas.
 * Navega a /alumno/materias para que el alumno explore e inscriba.
 */
function ExamenCatalogoCard({
  examen,
  onNavigate,
}: {
  examen: ExamenContenidoResumen;
  onNavigate: () => void;
}) {
  const subtitulo = examenContenidoSubtitulo(examen);
  return (
    <button
      type="button"
      onClick={onNavigate}
      className="w-full text-left bg-white rounded-lg border border-surface-200 px-4 py-4 flex items-center gap-4 hover:border-primary/40 hover:bg-surface-50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      aria-label={`Ver detalle del examen ${examen.titulo}`}
    >
      <div className="w-8 h-8 rounded-md bg-primary-fixed text-primary flex items-center justify-center shrink-0">
        <Icon name="assignment" className="text-[16px]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] font-semibold text-on-surface truncate leading-tight">{examen.titulo}</p>
        <p className="text-[13px] text-on-surface-variant leading-tight mt-1">{subtitulo}</p>
      </div>
      <span className="text-[12px] text-on-surface-variant shrink-0 tabular-nums">{examen.cantidad_preguntas} preg.</span>
      <Icon name="chevron_right" className="text-[22px] text-on-surface-variant shrink-0" />
    </button>
  );
}

function EstadoItem({ ok, warn = false, label, hint }: { ok: boolean; warn?: boolean; label: string; hint: string }) {
  const tono = ok && !warn ? 'success' : warn ? 'warning' : 'pending';
  const iconName = ok && !warn ? 'check_circle' : warn ? 'warning' : 'radio_button_unchecked';

  const bgMap = {
    success: 'bg-[#f0faf4] border border-[#bbdfc8]',
    warning: 'bg-warning-container border border-warning-200',
    pending: 'bg-surface-50 border border-surface-200',
  } as const;
  const iconColorMap = {
    success: 'text-success',
    warning: 'text-warning',
    pending: 'text-on-surface-variant',
  } as const;
  const badgeMap = {
    success: <span className="ml-auto text-[11px] font-semibold text-success bg-success/10 px-2 py-0.5 rounded-full shrink-0">Listo</span>,
    warning: <span className="ml-auto text-[11px] font-semibold text-warning bg-warning/10 px-2 py-0.5 rounded-full shrink-0">Atención</span>,
    pending: <span className="ml-auto text-[11px] font-semibold text-on-surface-variant bg-surface-200 px-2 py-0.5 rounded-full shrink-0">Pendiente</span>,
  } as const;

  return (
    <div className={`flex items-center gap-3 rounded-xl px-4 py-3 ${bgMap[tono]}`}>
      <Icon name={iconName} className={`text-[24px] shrink-0 ${iconColorMap[tono]}`} fill={ok || warn} />
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold text-on-surface leading-tight">{label}</p>
        <p className="text-[12px] text-on-surface-variant leading-tight mt-0.5">{hint}</p>
      </div>
      {badgeMap[tono]}
    </div>
  );
}
