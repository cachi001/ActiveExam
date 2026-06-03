// Paso de acuse por-examen (C-26) — acuse LIVIANO y ESPECÍFICO por (estudiante, examen).
// Da finalidad/propósito concreto a la instancia de tratamiento (Ley 25.326, art. 4).
// NO re-captura biometría ni re-presenta el consentimiento de perfil: LO REFERENCIA.
// Sin acción afirmativa explícita el acuse NO se registra (RN-CO-02 adaptado a C-26).
import { useEffect, useState } from 'react';
import { Card, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, ALCANCE_MONITOREO, ACUSE_EXAMEN_VERSION } from '../lib/api';
import type { Examen } from '../lib/types';

interface Props {
  /** ID del examen para el cual se está acusando. Viene del caller (AlumnoMaterias / AlumnoMisExamenes). */
  examenId: string;
  /** Adónde navegar tras confirmar el acuse o cancelar. */
  onConfirmado?: () => void;
  onCancelar?: () => void;
}

export default function AcuseExamen({ examenId, onConfirmado, onCancelar }: Props) {
  const navigate = useNavigate();
  const enrollment = useApp((s) => s.enrollmentStatus);

  const [examen, setExamen] = useState<Examen | null>(null);
  const [cargando, setCargando] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [acuseRegistrado, setAcuseRegistrado] = useState(false);

  // Carga el examen y verifica si ya hay acuse afirmativo (idempotente)
  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [ex, acuse] = await Promise.all([
        api.getExam(examenId),
        api.getAcuseExamen(examenId),
      ]);
      if (cancelado) return;
      setExamen(ex ?? null);
      if (acuse?.afirmativo) setAcuseRegistrado(true);
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, [examenId]);

  const handleConfirmar = async () => {
    if (confirmando) return;
    setConfirmando(true);
    try {
      await api.registrarAcuseExamen(examenId, { afirmativo: true });
      setAcuseRegistrado(true);
      if (onConfirmado) {
        onConfirmado();
      } else {
        navigate('/alumno/mis-examenes');
      }
    } finally {
      setConfirmando(false);
    }
  };

  const handleCancelar = () => {
    if (onCancelar) {
      onCancelar();
    } else {
      navigate('/alumno/materias');
    }
  };

  if (cargando) {
    return (
      <StudentShell>
        <div className="max-w-xl mx-auto flex items-center gap-sm text-on-surface-variant py-xl">
          <Icon name="progress_activity" className="ae-spin text-[22px]" />
          <span className="text-body-md">Cargando datos del examen…</span>
        </div>
      </StudentShell>
    );
  }

  if (!examen) {
    return (
      <StudentShell>
        <div className="max-w-xl mx-auto py-xl text-center">
          <Icon name="error_outline" className="text-[40px] text-error mb-md" />
          <p className="text-body-md text-on-surface font-semibold">Examen no encontrado</p>
          <Button variant="outline" onClick={handleCancelar} className="mt-md">Volver</Button>
        </div>
      </StudentShell>
    );
  }

  const fechaExamen = new Date(examen.inicio);
  const versionPerfilVigente = enrollment?.consentimiento?.version ?? '—';
  const perfilCompleto = enrollment?.perfil_completo ?? false;

  // Si el perfil no está completo, derivar a completarlo primero (C-22 presupone C-26)
  if (!perfilCompleto) {
    return (
      <StudentShell>
        <div className="max-w-xl mx-auto space-y-lg py-lg">
          <div className="flex items-start gap-md bg-warning-container border border-warning/30 rounded-xl p-md">
            <Icon name="warning" className="text-[22px] text-warning shrink-0 mt-base" fill />
            <div className="flex-1 min-w-0">
              <p className="text-label-md font-semibold text-on-surface">Completá tu perfil primero</p>
              <p className="text-label-sm text-on-surface-variant mt-base">
                El acuse de consentimiento por examen requiere que tu perfil esté completo
                (consentimiento de perfil vigente + biometría). Completalo antes de continuar.
              </p>
            </div>
          </div>
          <div className="flex gap-sm">
            <Button variant="outline" onClick={handleCancelar} className="flex-1">Cancelar</Button>
            <Button onClick={() => navigate('/alumno/perfil')} icon="manage_accounts" className="flex-1">
              Ir al perfil
            </Button>
          </div>
        </div>
      </StudentShell>
    );
  }

  return (
    <StudentShell>
      <div className="max-w-xl mx-auto space-y-lg py-lg">
        {/* Encabezado */}
        <header>
          <div className="flex items-center gap-sm mb-xs">
            <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
              <Icon name="assignment_turned_in" />
            </div>
            <p className="text-label-sm text-on-surface-variant font-medium uppercase tracking-wide">Acuse de monitoreo</p>
          </div>
          <h1 className="font-headline text-headline-sm text-on-surface tracking-tight">
            Confirmación de participación
          </h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Antes de inscribirte, confirmá que entendés qué se monitoreará durante este examen específico.
          </p>
        </header>

        {/* Datos del examen */}
        <Card>
          <p className="text-label-sm text-on-surface-variant font-medium uppercase tracking-wide mb-sm">Examen</p>
          <p className="text-title-md text-on-surface font-semibold">{examen.nombre}</p>
          <div className="mt-sm flex flex-wrap gap-md text-label-sm text-on-surface-variant">
            <span className="flex items-center gap-xs">
              <Icon name="school" className="text-[16px]" />
              {examen.catedra}
            </span>
            <span className="flex items-center gap-xs">
              <Icon name="calendar_today" className="text-[16px]" />
              {fechaExamen.toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })}
              {' '}
              {fechaExamen.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className="flex items-center gap-xs">
              <Icon name="timer" className="text-[16px]" />
              {examen.duracion_min} min
            </span>
          </div>
        </Card>

        {/* Alcance de monitoreo */}
        <Card>
          <p className="text-label-sm text-on-surface-variant font-medium uppercase tracking-wide mb-md">
            Qué se va a monitorear en esta instancia
          </p>
          <div className="space-y-md">
            {ALCANCE_MONITOREO.map((item) => (
              <div key={item.label} className="flex items-start gap-md">
                <div className="w-9 h-9 rounded-lg bg-secondary-container text-on-secondary flex items-center justify-center shrink-0">
                  <Icon name={item.icono} className="text-[18px]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-label-md font-semibold text-on-surface">{item.label}</p>
                  <p className="text-label-sm text-on-surface-variant">{item.descripcion}</p>
                </div>
                <Icon name="check_circle" className="text-[18px] text-tertiary shrink-0 mt-base" fill />
              </div>
            ))}
          </div>
        </Card>

        {/* Referencia al consentimiento de perfil (NO lo repite ni re-captura biometría) */}
        <div className="flex items-start gap-md bg-surface-container border border-outline-variant/40 rounded-xl p-md">
          <Icon name="verified_user" className="text-[22px] text-primary shrink-0 mt-base" fill />
          <div className="flex-1 min-w-0">
            <p className="text-label-md font-semibold text-on-surface">
              Consentimiento de perfil vigente
            </p>
            <p className="text-label-sm text-on-surface-variant mt-base">
              Tu consentimiento de tratamiento biométrico y de datos sensibles está registrado
              (versión {versionPerfilVigente}). Este paso referencia ese acuse como base legal;
              no se vuelve a pedir ni se re-captura biometría.
            </p>
            <button
              onClick={() => navigate('/alumno/perfil')}
              className="text-label-sm text-primary hover:underline mt-xs inline-flex items-center gap-xs"
            >
              <Icon name="open_in_new" className="text-[14px]" />
              Ver perfil y consentimiento de perfil
            </button>
          </div>
        </div>

        {/* Información de privacidad */}
        <div className="text-label-sm text-on-surface-variant bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-md space-y-xs">
          <p className="font-semibold text-on-surface flex items-center gap-xs">
            <Icon name="gavel" className="text-[16px]" />
            Acerca de este acuse (Ley 25.326)
          </p>
          <p>
            Este acuse da <strong>finalidad específica</strong> al tratamiento de datos para esta instancia de examen concreta,
            conforme al art. 4 de la Ley 25.326. El sistema no sancionará automáticamente:
            cualquier anomalía detectada se deriva a revisión humana.
          </p>
          <p className="text-on-surface-variant/70">
            Versión del texto de acuse: {ACUSE_EXAMEN_VERSION}.
            El acuse es inmutable una vez registrado.
          </p>
        </div>

        {/* Acuse ya registrado */}
        {acuseRegistrado && (
          <div className="flex items-center gap-md bg-tertiary-container border border-tertiary/20 rounded-xl p-md">
            <Icon name="check_circle" className="text-[22px] text-tertiary shrink-0" fill />
            <p className="text-label-md text-on-surface">
              Ya otorgaste el acuse para este examen. Tu inscripción está habilitada.
            </p>
          </div>
        )}

        {/* Acciones — acción afirmativa EXPLÍCITA sin casilla premarcada (RN-CO-02) */}
        {!acuseRegistrado && (
          <div className="flex flex-col gap-sm">
            <Button
              onClick={handleConfirmar}
              disabled={confirmando}
              icon={confirmando ? undefined : 'assignment_turned_in'}
              className="w-full"
            >
              {confirmando ? (
                <span className="inline-flex items-center gap-xs">
                  <Icon name="progress_activity" className="ae-spin text-[18px]" />
                  Registrando acuse…
                </span>
              ) : (
                'Confirmo que rendiré este examen bajo monitoreo'
              )}
            </Button>
            <Button variant="ghost" onClick={handleCancelar} className="w-full">
              Cancelar — decidir más tarde
            </Button>
          </div>
        )}

        {acuseRegistrado && (
          <Button onClick={onConfirmado ?? (() => navigate('/alumno/mis-examenes'))} icon="check" className="w-full">
            Ir a Mis exámenes
          </Button>
        )}
      </div>
    </StudentShell>
  );
}
