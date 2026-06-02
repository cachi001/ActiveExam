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
 * Spec: student-profile-enrollment + consent-gate + informed-consent-presentation
 *       + embedding-computation + biometric-custody-encryption + biometric-reference-renewal
 *       + optional-dni-scan (C-22)
 */
import { useEffect, useState } from 'react';
import { Button, Icon } from '../ui/components';
import { Term } from '../ui/Term';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, ENABLE_DNI_SCAN } from '../lib/api';
import { DEV_TOOLS_ENABLED } from '../lib/devConfig';
import { EnrollmentConsentStep } from './enrollment/EnrollmentConsentStep';
import { EnrollmentBiometricStep } from './enrollment/EnrollmentBiometricStep';
import { EnrollmentDniStep } from './enrollment/EnrollmentDniStep';
import { BiometricRenewalStatus } from './enrollment/BiometricRenewalStatus';
import { CameraSnapshotCapture } from '../ui/CameraSnapshotCapture';
import { PerfilHeaderCard } from './alumno/components/PerfilHeaderCard';
import { RequisitoCard } from './alumno/components/RequisitoCard';
import { PerfilBannerEstado } from './alumno/components/PerfilBannerEstado';
import type { EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI } from '../lib/types';

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

export default function StudentProfile() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const setFotoPerfil = useApp((s) => s.setFotoPerfil);

  const [enrollment, setEnrollment] = useState<EstadoEnrollment | null>(null);
  const [paso, setPaso] = useState<PasoEnrollment>('cargando');

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
      const estado = await cargarEnrollment();
      if (cancelado) return;

      // Determinar en qué paso iniciar según el estado actual
      if (!estado.consentimiento) {
        // Sin consentimiento: primera vez o vía alternativa no elegida
        setPaso('perfil'); // La UI del perfil ofrece iniciar enrollment
      } else if (
        !estado.consentimiento.via_alternativa &&
        !estado.biometria?.captura_completada
      ) {
        // Consentimiento ok pero sin biometría (flujo interrumpido)
        setPaso('perfil');
      } else {
        setPaso('perfil');
      }
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
   * Task 7.3 — Handler al confirmar la foto de perfil (C-37).
   * Guarda via api mock, actualiza el store, y avanza al paso de biometría.
   */
  const handleFotoCapturada = async (dataUrl: string) => {
    await api.guardarFotoPerfil(dataUrl);
    setFotoPerfil(dataUrl);
    setPaso('biometria');
  };

  /**
   * Task 7.4 — Handler al cancelar la foto de perfil (C-37).
   * El paso NO bloquea el enrollment: si cancela, avanza a biometría igualmente.
   */
  const handleFotoCancelada = () => {
    setPaso('biometria');
  };

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
    } else if (!enrollment.biometria?.captura_completada && !enrollment.consentimiento.via_alternativa) {
      setPaso('biometria');
    } else {
      setPaso('biometria'); // Renovar
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
  // Render helpers
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
        <div className="max-w-3xl mx-auto space-y-xl">
          <header>
            <button
              onClick={() => setPaso('perfil')}
              className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary mb-md"
            >
              <Icon name="arrow_back" className="text-[18px]" />
              Volver al perfil
            </button>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Consentimiento informado
            </h1>
            {/* Task 7.8: foto suma un paso al total */}
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 1 de {ENABLE_DNI_SCAN ? '4' : '3'} — Leé y aceptá el uso de tus datos biométricos.
            </p>
          </header>
          <EnrollmentConsentStep
            acuseActual={enrollment?.consentimiento ?? null}
            onConsentido={handleConsentido}
          />
        </div>
      </StudentShell>
    );
  }

  // Task 7.7: Paso foto de perfil (C-37) — entre consentimiento y biometría
  if (paso === 'foto_perfil') {
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto space-y-xl">
          <header>
            <button
              onClick={() => setPaso('perfil')}
              className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary mb-md"
            >
              <Icon name="arrow_back" className="text-[18px]" />
              Volver al perfil
            </button>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Foto de perfil
            </h1>
            {/* Task 7.8: contador de pasos actualizado */}
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 2 de {ENABLE_DNI_SCAN ? '4' : '3'} — Tu foto será usada como avatar en la plataforma.
            </p>
          </header>

          {/* Nota de privacidad Ley 25.326 (D-8) */}
          <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-sm border border-outline-variant/30">
            <span className="font-semibold">Privacidad (Ley 25.326):</span> La foto de perfil es
            un dato personal con finalidad acotada (avatar en la UI). En el cliente se almacena en memoria de sesión.
            Server-side es cifrada at-rest y eliminada al egreso (Ley 25.326).
          </div>

          {/* CameraSnapshotCapture para foto de perfil (oval) */}
          <CameraSnapshotCapture
            shape="oval"
            instruction="Posicioná tu cara dentro del óvalo y presioná Capturar"
            contextLabel="Foto de perfil"
            onCapture={handleFotoCapturada}
            onCancel={handleFotoCancelada}
          />
        </div>
      </StudentShell>
    );
  }

  if (paso === 'biometria') {
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto space-y-xl">
          <header>
            <button
              onClick={() => setPaso('perfil')}
              className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary mb-md"
            >
              <Icon name="arrow_back" className="text-[18px]" />
              Volver al perfil
            </button>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Captura biométrica de referencia
            </h1>
            {/* Task 7.9: contador de pasos actualizado (foto suma un paso) */}
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 3 de {ENABLE_DNI_SCAN ? '4' : '3'} — Se realiza UNA sola vez. La referencia es reutilizable en todos tus exámenes.
            </p>
          </header>
          <EnrollmentBiometricStep
            referenciaActual={enrollment?.biometria ?? null}
            onCapturada={handleBiometriaCapturada}
            esRenovacion={false}
          />
        </div>
      </StudentShell>
    );
  }

  if (paso === 'renovar_biometria') {
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto space-y-xl">
          <header>
            <button
              onClick={() => setPaso('perfil')}
              className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary mb-md"
            >
              <Icon name="arrow_back" className="text-[18px]" />
              Volver al perfil
            </button>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Renovar referencia biométrica
            </h1>
            <p className="text-body-md text-on-surface-variant mt-xs">
              La nueva captura reemplazará tu referencia actual y tendrá vigencia de {enrollment?.biometria?.vigencia_meses ?? 24} meses.
            </p>
          </header>
          <EnrollmentBiometricStep
            referenciaActual={enrollment?.biometria ?? null}
            onCapturada={handleBiometriaRenovada}
            esRenovacion
          />
        </div>
      </StudentShell>
    );
  }

  if (paso === 'dni') {
    return (
      <StudentShell>
        <div className="max-w-2xl mx-auto space-y-xl">
          <header>
            <button
              onClick={() => setPaso('perfil')}
              className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary mb-md"
            >
              <Icon name="arrow_back" className="text-[18px]" />
              Volver al perfil
            </button>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Verificación documental
            </h1>
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 4 de 4 — Opcional. El escaneo del DNI (frente y dorso) refuerza la verificación pero no bloquea el perfil completo.
            </p>
          </header>
          <EnrollmentDniStep
            escanActual={enrollment?.dni ?? null}
            onEscaneado={handleDniEscaneado}
            onOmitir={handleOmitirDni}
          />
        </div>
      </StudentShell>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Vista principal del perfil (paso === 'perfil')
  // ─────────────────────────────────────────────────────────────────────────────

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mi perfil</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Datos personales y requisitos de enrollment para rendir exámenes.
          </p>
        </header>

        {/* Encabezado: avatar + datos personales */}
        <PerfilHeaderCard principal={principal} />

        {/* Banners contextuales del estado del perfil */}
        <PerfilBannerEstado
          perfilCompleto={perfilCompleto}
          biometriaCaducada={biometriaCaducada}
          biometriaRenovacionRequerida={biometriaRenovacionRequerida}
          viaAlternativa={viaAlternativa}
          onIrAExamenes={() => navigate('/alumno/mis-examenes')}
          onRenovarBiometria={handleRenovarBiometria}
        />

        {/* ── Sección: Consentimiento informado ───────────────────────────────── */}
        <RequisitoCard
          icon="gavel"
          title="Consentimiento informado"
          badge={{
            tone: consentimientoOk ? 'success' : 'warning',
            label: consentimientoOk ? (viaAlternativa ? 'Vía alternativa' : 'Completado') : 'Pendiente',
          }}
        >
          {consentimientoOk && enrollment?.consentimiento ? (
            /* Acuse existente */
            <div className="space-y-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm text-label-sm">
                <div>
                  <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">Versión</p>
                  <p className="text-on-surface font-semibold">{enrollment.consentimiento.version}</p>
                </div>
                <div>
                  <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">Fecha de acuse</p>
                  <p className="text-on-surface font-semibold">
                    {new Date(enrollment.consentimiento.timestamp).toLocaleDateString('es-AR', {
                      day: '2-digit', month: 'long', year: 'numeric',
                    })}
                  </p>
                </div>
                <div className="sm:col-span-2">
                  <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">Hash de acuse</p>
                  <p className="text-on-surface font-mono text-[11px] break-all">{enrollment.consentimiento.hash}</p>
                </div>
              </div>
              {viaAlternativa && (
                <div className="flex items-start gap-sm bg-surface-container-low rounded-xl p-sm">
                  <Icon name="support_agent" className="text-[16px] text-on-surface-variant shrink-0 mt-px" />
                  <p className="text-label-sm text-on-surface-variant">
                    Elegiste la <strong>vía alternativa sin biometría</strong>. Un proctor humano supervisará
                    tu verificación de identidad en cada examen.
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* Consentimiento pendiente */
            <div className="space-y-md">
              <p className="text-label-sm text-on-surface-variant">
                Para enrollarte y poder rendir exámenes, necesitás leer y aceptar el uso de tus datos
                biométricos. El acuse es inmutable e incluye la versión del texto que firmaste.
              </p>
              <Button onClick={() => setPaso('consentimiento')} icon="gavel" iconRight="arrow_forward">
                Leer y consentir
              </Button>
            </div>
          )}
        </RequisitoCard>

        {/* ── Sección: Referencia biométrica ──────────────────────────────────── */}
        {!viaAlternativa && (
          <RequisitoCard
            icon="face"
            title="Referencia biométrica"
            badge={{
              tone: !biometriaOk ? 'warning' :
                    biometriaCaducada ? 'error' :
                    enrollment?.biometria?.vigencia === 'por_vencer' ? 'warning' :
                    biometriaRenovacionRequerida ? 'warning' :
                    'success',
              label: !biometriaOk ? 'Pendiente' :
                     biometriaCaducada ? 'Caducada' :
                     enrollment?.biometria?.vigencia === 'por_vencer' ? 'Por vencer' :
                     biometriaRenovacionRequerida ? 'Renovación requerida' :
                     'Vigente',
            }}
          >
            {biometriaOk && enrollment?.biometria ? (
              /* Referencia existente con estado de vigencia */
              <BiometricRenewalStatus
                referencia={enrollment.biometria}
                onRenovar={handleRenovarBiometria}
              />
            ) : (
              /* Captura pendiente */
              <div className="space-y-md">
                <p className="text-label-sm text-on-surface-variant">
                  La referencia biométrica se captura UNA sola vez en el perfil y es reutilizable en
                  todos tus exámenes. Tiene vigencia de{' '}
                  <strong>{enrollment?.biometria?.vigencia_meses ?? 24} meses</strong>.
                </p>

                {/* Nota de privacidad (Ley 25.326) */}
                <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-sm border border-outline-variant/30">
                  <span className="font-semibold">Privacidad (Ley 25.326):</span> La imagen y el <Term termKey="embedding" />
                  biométrico son <strong>datos sensibles</strong>: cifrados at-rest, con finalidad acotada
                  a la verificación de identidad. Se eliminan al egreso (salvo hold disciplinario).
                  El sistema nunca sanciona automáticamente — solo prioriza para revisión humana (<Term termKey="l2_5" />).
                </div>

                <Button
                  onClick={handleIniciarEnrollment}
                  disabled={!consentimientoOk}
                  icon="face"
                  iconRight="arrow_forward"
                >
                  {!consentimientoOk ? 'Primero completá el consentimiento' : 'Capturar referencia biométrica'}
                </Button>
              </div>
            )}

            {/* Tool de dev: simular deriva del embedding — solo visible con VITE_DEV_TOOLS=1 */}
            {DEV_TOOLS_ENABLED && biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida && (
              <div className="flex items-center justify-between gap-md pt-sm border-t border-outline-variant/40">
                <div className="flex items-center gap-xs text-on-surface-variant">
                  <Icon name="science" className="text-[16px]" />
                  <span className="text-label-sm">Herramientas de desarrollo</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSimularDeriva}
                  className="text-label-sm text-on-surface-variant"
                >
                  Simular deriva embedding
                </Button>
              </div>
            )}
          </RequisitoCard>
        )}

        {/* ── Sección: DNI (opcional / flaggeado) ────────────────────────────── */}
        <RequisitoCard
          icon="badge"
          title={
            <>
              Verificación documental
              <span className="ml-sm text-label-sm font-normal text-on-surface-variant bg-surface-container px-sm py-base rounded-full">
                Opcional
              </span>
            </>
          }
          badge={{
            tone: dniOk ? 'success' : 'neutral',
            label: dniOk ? 'Registrado' : (ENABLE_DNI_SCAN ? 'Pendiente' : 'No disponible'),
          }}
        >
          {dniOk && enrollment?.dni ? (
            <div className="space-y-xs text-label-sm">
              <p className="text-on-surface-variant">
                Frente y dorso registrados el {new Date(enrollment.dni.fecha_captura).toLocaleDateString('es-AR', {
                  day: '2-digit', month: 'long', year: 'numeric',
                })}.
              </p>
              <p className="text-on-surface-variant">
                Tratado como dato sensible (Ley 25.326): cifrado at-rest, finalidad acotada,
                eliminado al egreso. La verificación del documento se realiza server-side.
              </p>
            </div>
          ) : ENABLE_DNI_SCAN ? (
            <div className="space-y-md">
              <p className="text-label-sm text-on-surface-variant">
                El escaneo del DNI es opcional y no bloquea tu habilitación para rendir.
                Refuerza la verificación de identidad documental.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPaso('dni')}
                icon="badge"
                className="text-label-sm"
              >
                Escanear DNI (opcional)
              </Button>
            </div>
          ) : (
            <p className="text-label-sm text-on-surface-variant">
              No disponible en esta versión. No bloquea el perfil completo. Cuando esté activo, el DNI
              será tratado como dato sensible (Ley 25.326): cifrado, finalidad acotada, eliminado al egreso.
            </p>
          )}
        </RequisitoCard>

        {/* CTA de navegación — debajo de todas las cards */}
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
