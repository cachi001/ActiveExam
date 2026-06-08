/**
 * Pantalla de Perfil del alumno — hogar del enrollment único (C-22).
 *
 * Reemplaza los placeholders de AlumnoPerfil.tsx (C-21) con el flujo REAL:
 *   - Consentimiento informado (RN-CO-01/02/05) — una sola vez, reutilizable.
 *   - Captura de referencia biométrica (Face Mesh + liveness) — vigencia 24 meses.
 *   - Escaneo de DNI opcional (feature flag ENABLE_DNI_SCAN).
 *   - Gate de perfil completo → puedeRendir (conecta con C-21).
 *
 * Flujo de enrollment: consentimiento → referencia biométrica → DNI (opcional).
 * Tras completar, el perfil queda enrollado y no se vuelve a pedir en el pre-examen.
 *
 * BREAKING respecto a C-21/C-08: el gate de consentimiento se resuelve aquí,
 * en el perfil, no antes de cada examen.
 *
 * Las secciones del flujo se delegan en sub-componentes (≤ 400 líneas por archivo):
 *   - enrollment/EnrollmentStepLayout — encabezado común de cada paso
 *   - alumno/components/RequisitoConsentimiento | RequisitoBiometria | RequisitoDni
 *
 * Spec: student-profile-enrollment + consent-gate + informed-consent-presentation
 *       + embedding-computation + biometric-custody-encryption + biometric-reference-renewal
 *       + optional-dni-scan (C-22) · profile-requisito-cards (C-42)
 */
import { useEffect, useState } from 'react';
import { Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, ENABLE_DNI_SCAN, USE_REAL_BACKEND } from '../lib/api';
import { DEV_TOOLS_ENABLED } from '../lib/devConfig';
import { EnrollmentConsentStep } from './enrollment/EnrollmentConsentStep';
import { EnrollmentBiometricStep } from './enrollment/EnrollmentBiometricStep';
import { EnrollmentDniStep } from './enrollment/EnrollmentDniStep';
import { EnrollmentStepLayout } from './enrollment/EnrollmentStepLayout';
import { CameraSnapshotCapture } from '../ui/CameraSnapshotCapture';
import { PerfilHeaderCard } from './alumno/components/PerfilHeaderCard';
import { PerfilBannerEstado } from './alumno/components/PerfilBannerEstado';
import { RequisitoConsentimiento } from './alumno/components/RequisitoConsentimiento';
import { RequisitoBiometria } from './alumno/components/RequisitoBiometria';
import { RequisitoDni } from './alumno/components/RequisitoDni';
import type { AcuseConsentimiento, EstadoEnrollment, ReferenciasBiometrica, EscaneDNI } from '../lib/types';

/**
 * Pasos del flujo de enrollment.
 * 'perfil' = vista del perfil (enrollment ya completado o estado actual).
 * 'foto_perfil' = captura de foto de perfil (C-37) — entre consentimiento y biometria.
 */
type PasoEnrollment =
  | 'cargando'
  | 'perfil'
  | 'consentimiento'
  | 'foto_perfil'
  | 'biometria'
  | 'dni'
  | 'renovar_biometria';

/** Total de pasos del enrollment según el flag de DNI (afecta el contador "Paso X de N"). */
const totalPasos = () => (ENABLE_DNI_SCAN ? '4' : '3');

export default function StudentProfile() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const setFotoPerfil = useApp((s) => s.setFotoPerfil);

  const [enrollment, setEnrollment] = useState<EstadoEnrollment | null>(null);
  const [paso, setPaso] = useState<PasoEnrollment>('cargando');
  /** C-56: error de backend al guardar la foto de perfil (para mostrar al alumno). */
  const [fotoError, setFotoError] = useState<string | null>(null);

  /** Carga el estado de enrollment y actualiza el store de Zustand. */
  const cargarEnrollment = async () => {
    const estado = await api.getEnrollment();
    setEnrollment(estado);
    setEnrollmentStatus(estado); // sincroniza el store
    return estado;
  };

  useEffect(() => {
    let cancelado = false;
    (async () => {
      await cargarEnrollment();
      // C-61 task 5.2: cargar foto de perfil desde el backend real y mostrar avatar.
      if (USE_REAL_BACKEND && !principal?.foto_perfil) {
        const foto = await api.obtenerFotoPerfil();
        if (!cancelado && foto) setFotoPerfil(foto);
      }
      if (cancelado) return;
      // La UI del perfil ofrece iniciar/continuar enrollment según el estado.
      setPaso('perfil');
    })();
    return () => { cancelado = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────────────────────────────────────────────
  // Handlers de los pasos de enrollment
  // ─────────────────────────────────────────────────────────────────────────────

  const handleConsentido = async (acuse: AcuseConsentimiento) => {
    const estado = await cargarEnrollment();
    if (acuse.via_alternativa) {
      // Vía alternativa: el perfil puede estar completo sin biometría
      setPaso('perfil');
    } else if (!principal?.foto_perfil) {
      // Task 7.5: sin foto de perfil → paso foto_perfil (C-37)
      setPaso('foto_perfil');
    } else if (!estado.biometria?.captura_completada) {
      // Tiene foto pero no biometría → paso biometría
      setPaso('biometria');
    } else {
      setPaso('perfil');
    }
  };

  /**
   * C-56 — Handler al confirmar la foto de perfil.
   * En modo real: llama a POST /enrollment/foto-perfil, obtiene el foto_referencia_id
   * opaco y avanza al paso de biometría. Si el backend falla, muestra el error y
   * no avanza la fase (el alumno puede reintentar).
   * En modo demo: guarda en memoria y avanza.
   */
  const handleFotoCapturada = async (dataUrl: string) => {
    setFotoError(null);
    try {
      const fotoId = await api.guardarFotoPerfil(dataUrl);
      // En modo demo fotoId es undefined; en modo real es el UUID del backend.
      // El store actualiza la foto del principal para el avatar de la UI (demo).
      if (!fotoId) {
        // Modo demo: actualizar el avatar con el dataUrl.
        setFotoPerfil(dataUrl);
      }
      // En modo real no mostramos el dataUrl como avatar (solo el ID opaco nos llega).
      setPaso('biometria');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFotoError(msg);
      // No avanzar la fase: el alumno debe reintentar.
    }
  };

  /**
   * Task 7.4 — Handler al cancelar la foto de perfil (C-37).
   * El paso NO bloquea el enrollment: si cancela, avanza a biometría igualmente.
   */
  const handleFotoCancelada = () => setPaso('biometria');

  const handleBiometriaCapturada = async (_ref: ReferenciasBiometrica) => {
    await cargarEnrollment();
    // Continúa al paso de DNI (opcional)
    setPaso('dni');
  };

  const handleDniEscaneado = async (_escan: EscaneDNI) => {
    await cargarEnrollment();
    setPaso('perfil');
  };

  const handleOmitirDni = async () => {
    await cargarEnrollment();
    setPaso('perfil');
  };

  const handleIniciarEnrollment = () => {
    // Task 7.6: navegar al paso correcto según estado actual
    if (!enrollment?.consentimiento) {
      setPaso('consentimiento');
    } else if (!principal?.foto_perfil && !enrollment.consentimiento.via_alternativa) {
      // Tiene consentimiento pero no foto → foto_perfil (C-37)
      setPaso('foto_perfil');
    } else {
      // Resto de casos (sin biometría o renovar) → captura biométrica
      setPaso('biometria');
    }
  };

  const handleRenovarBiometria = () => setPaso('renovar_biometria');

  const handleBiometriaRenovada = async (_ref: ReferenciasBiometrica) => {
    await cargarEnrollment();
    setPaso('perfil');
  };

  /** Simula deriva del embedding (demo tool — gatilla flag de renovación anticipada). */
  const handleSimularDeriva = async () => {
    await api.simularDerivaEmbedding();
    await cargarEnrollment();
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Estado derivado
  // ─────────────────────────────────────────────────────────────────────────────

  const consentimientoOk = Boolean(enrollment?.consentimiento);
  const viaAlternativa = enrollment?.consentimiento?.via_alternativa ?? false;
  const biometriaOk = Boolean(enrollment?.biometria?.captura_completada);
  const biometriaCaducada = enrollment?.biometria?.vigencia === 'caducada';
  const biometriaRenovacionRequerida =
    enrollment?.biometria?.vigencia === 'renovacion_requerida' ||
    (enrollment?.biometria?.renovacion_anticipada_requerida ?? false);
  const dniOk = Boolean(enrollment?.dni?.captura_completada);
  const perfilCompleto = enrollment?.perfil_completo ?? false;

  const volverAlPerfil = () => setPaso('perfil');

  // ─────────────────────────────────────────────────────────────────────────────
  // Pasos del flujo de enrollment
  // ─────────────────────────────────────────────────────────────────────────────

  if (paso === 'cargando') {
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto flex items-center justify-center py-xl gap-sm text-on-surface-variant">
          <Icon name="progress_activity" className="ae-spin text-[24px]" />
          <span className="text-body-md">Cargando perfil…</span>
        </div>
      </StudentShell>
    );
  }

  if (paso === 'consentimiento') {
    return (
      <StudentShell>
        <EnrollmentStepLayout
          maxWidth="3xl"
          title="Consentimiento informado"
          subtitle={<>Paso 1 de {totalPasos()} — Leé y aceptá el uso de tus datos biométricos.</>}
          onBack={volverAlPerfil}
        >
          <EnrollmentConsentStep
            acuseActual={enrollment?.consentimiento ?? null}
            onConsentido={handleConsentido}
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  // C-56: Paso foto de perfil — entre consentimiento y biometría
  if (paso === 'foto_perfil') {
    return (
      <StudentShell>
        <EnrollmentStepLayout
          title="Foto de perfil"
          subtitle={<>Paso 2 de {totalPasos()} — Tu foto será usada como avatar en la plataforma.</>}
          onBack={volverAlPerfil}
        >
          <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-sm border border-outline-variant/30">
            <span className="font-semibold">Privacidad:</span> La foto de perfil se procesa server-side y se elimina al egreso.
          </div>

          {/* C-56: mostrar error del backend con opción de reintentar (task 11.2) */}
          {fotoError && (
            <div className="flex items-start gap-sm bg-error-container border border-error/30 rounded-xl p-md">
              <Icon name="error" className="text-error text-[18px] shrink-0 mt-px" />
              <div className="text-label-sm text-on-surface">
                <p className="font-semibold text-error">Error al guardar la foto</p>
                <p className="text-on-surface-variant mt-xs">{fotoError}</p>
                <p className="text-on-surface-variant mt-xs">
                  Intentá capturar la foto nuevamente. Si el problema persiste, contactá al soporte.
                </p>
              </div>
            </div>
          )}

          <CameraSnapshotCapture
            shape="oval"
            instruction="Posicioná tu cara dentro del óvalo y presioná Capturar"
            contextLabel="Foto de perfil"
            onCapture={handleFotoCapturada}
            onCancel={handleFotoCancelada}
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  if (paso === 'biometria') {
    return (
      <StudentShell>
        <EnrollmentStepLayout
          title="Captura biométrica de referencia"
          subtitle={<>Paso 3 de {totalPasos()} — Se realiza UNA sola vez. La referencia es reutilizable en todos tus exámenes.</>}
          onBack={volverAlPerfil}
        >
          <EnrollmentBiometricStep
            referenciaActual={enrollment?.biometria ?? null}
            onCapturada={handleBiometriaCapturada}
            esRenovacion={false}
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  if (paso === 'renovar_biometria') {
    return (
      <StudentShell>
        <EnrollmentStepLayout
          title="Renovar referencia biométrica"
          subtitle={<>La nueva captura reemplazará tu referencia actual y tendrá vigencia de {enrollment?.biometria?.vigencia_meses ?? 24} meses.</>}
          onBack={volverAlPerfil}
        >
          <EnrollmentBiometricStep
            referenciaActual={enrollment?.biometria ?? null}
            onCapturada={handleBiometriaRenovada}
            esRenovacion
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  if (paso === 'dni') {
    return (
      <StudentShell>
        <EnrollmentStepLayout
          title="Verificación documental"
          subtitle="Paso 4 de 4 — Opcional. El escaneo del DNI (frente y dorso) refuerza la verificación pero no bloquea el perfil completo."
          onBack={volverAlPerfil}
        >
          <EnrollmentDniStep
            escanActual={enrollment?.dni ?? null}
            onEscaneado={handleDniEscaneado}
            onOmitir={handleOmitirDni}
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Vista principal del perfil (paso === 'perfil')
  // ─────────────────────────────────────────────────────────────────────────────

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl animate-in fade-in duration-300">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mi perfil</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Datos personales y requisitos de enrollment para rendir exámenes.
          </p>
        </header>

        <PerfilHeaderCard principal={principal} />

        <PerfilBannerEstado
          perfilCompleto={perfilCompleto}
          biometriaCaducada={biometriaCaducada}
          biometriaRenovacionRequerida={biometriaRenovacionRequerida}
          viaAlternativa={viaAlternativa}
          onIrAExamenes={() => navigate('/alumno/mis-examenes')}
          onRenovarBiometria={handleRenovarBiometria}
        />

        <RequisitoConsentimiento
          consentimiento={enrollment?.consentimiento ?? null}
          viaAlternativa={viaAlternativa}
          onIniciar={() => setPaso('consentimiento')}
        />

        {!viaAlternativa && (
          <RequisitoBiometria
            biometria={enrollment?.biometria ?? null}
            biometriaOk={biometriaOk}
            biometriaCaducada={biometriaCaducada}
            biometriaRenovacionRequerida={biometriaRenovacionRequerida}
            consentimientoOk={consentimientoOk}
            devToolsEnabled={DEV_TOOLS_ENABLED}
            onCapturar={handleIniciarEnrollment}
            onRenovar={handleRenovarBiometria}
            onSimularDeriva={handleSimularDeriva}
          />
        )}

        <RequisitoDni
          dni={enrollment?.dni ?? null}
          dniOk={dniOk}
          dniScanHabilitado={ENABLE_DNI_SCAN}
          onEscanear={() => setPaso('dni')}
        />

        {perfilCompleto && (
          <div className="text-center">
            <Button onClick={() => navigate('/alumno/mis-examenes')} icon="assignment" iconRight="arrow_forward">
              Ir a mis exámenes
            </Button>
          </div>
        )}
      </div>
    </StudentShell>
  );
}
