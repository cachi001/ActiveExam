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
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, ENABLE_DNI_SCAN } from '../lib/api';
import { EnrollmentConsentStep } from './enrollment/EnrollmentConsentStep';
import { EnrollmentBiometricStep } from './enrollment/EnrollmentBiometricStep';
import { EnrollmentDniStep } from './enrollment/EnrollmentDniStep';
import { BiometricRenewalStatus } from './enrollment/BiometricRenewalStatus';
import type { EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI } from '../lib/types';

/**
 * Pasos del flujo de enrollment.
 * 'perfil' = vista del perfil (enrollment ya completado o estado actual).
 */
type PasoEnrollment =
  | 'cargando'
  | 'perfil'
  | 'consentimiento'
  | 'biometria'
  | 'dni'
  | 'renovar_biometria';

export default function StudentProfile() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);

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
    } else if (!estado.biometria?.captura_completada) {
      // Continúa al paso de biometría
      setPaso('biometria');
    } else {
      setPaso('perfil');
    }
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
    if (!enrollment?.consentimiento) {
      setPaso('consentimiento');
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
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 1 de {ENABLE_DNI_SCAN ? '3' : '2'} — Leé y aceptá el uso de tus datos biométricos.
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
            <p className="text-body-md text-on-surface-variant mt-xs">
              Paso 2 de {ENABLE_DNI_SCAN ? '3' : '2'} — Se realiza UNA sola vez. La referencia es reutilizable en todos tus exámenes.
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
              Paso 3 de 3 — Opcional. El DNI refuerza la verificación pero no bloquea el perfil completo.
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

        {/* Datos personales */}
        <Card>
          <div className="flex items-center gap-md mb-lg">
            <div className="w-14 h-14 rounded-full bg-secondary-container text-on-secondary flex items-center justify-center font-headline text-headline-sm shrink-0">
              {principal?.nombre.charAt(0) ?? '?'}
            </div>
            <div className="min-w-0">
              <p className="text-label-lg font-semibold text-on-surface">{principal?.nombre ?? '—'}</p>
              <p className="text-label-sm text-on-surface-variant">{principal?.roles.join(', ')}</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
            <div>
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Legajo</p>
              <p className="text-label-md text-on-surface font-semibold">{principal?.id_institucional ?? '—'}</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Email institucional</p>
              <p className="text-label-md text-on-surface font-semibold">{principal?.email ?? '—'}</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Institución</p>
              <p className="text-label-md text-on-surface font-semibold">UTN Regional Mendoza</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide mb-base">Jurisdicción</p>
              <p className="text-label-md text-on-surface font-semibold">{principal?.jurisdiccion ?? '—'}</p>
            </div>
          </div>
        </Card>

        {/* Banner: perfil completo */}
        {perfilCompleto && !biometriaCaducada && !biometriaRenovacionRequerida && (
          <div className="flex items-center gap-md bg-success-container border border-success/30 rounded-xl p-md">
            <Icon name="verified" className="text-success text-[24px] shrink-0" fill />
            <div className="flex-1">
              <p className="text-label-md font-semibold text-on-surface">
                Perfil completo — podés rendir tus exámenes
              </p>
              <p className="text-label-sm text-on-surface-variant mt-base">
                {viaAlternativa
                  ? 'Elegiste la vía alternativa. Un proctor supervisará tu verificación de identidad.'
                  : 'Consentimiento y referencia biométrica vigentes.'}
              </p>
            </div>
            <Button
              variant="secondary"
              onClick={() => navigate('/alumno/mis-examenes')}
              className="shrink-0 h-9 px-md text-label-sm"
            >
              Mis exámenes
            </Button>
          </div>
        )}

        {/* Banner: referencia caducada — bloqueo */}
        {biometriaCaducada && (
          <div className="flex items-start gap-md bg-error-container border border-error/30 rounded-xl p-md">
            <Icon name="cancel" className="text-error text-[22px] shrink-0 mt-base" fill />
            <div className="flex-1">
              <p className="text-label-md font-semibold text-on-surface">
                Referencia biométrica caducada — no podés rendir
              </p>
              <p className="text-label-sm text-on-surface-variant mt-base">
                Tu referencia biométrica venció. Renovála para volver a poder rendir tus exámenes.
              </p>
            </div>
            <Button variant="danger" onClick={handleRenovarBiometria} className="shrink-0 h-9 px-md text-label-sm" icon="refresh">
              Renovar
            </Button>
          </div>
        )}

        {/* Banner: renovación requerida por deriva */}
        {biometriaRenovacionRequerida && !biometriaCaducada && (
          <div className="flex items-start gap-md bg-warning-container border border-warning/30 rounded-xl p-md">
            <Icon name="refresh" className="text-warning text-[22px] shrink-0 mt-base" />
            <div className="flex-1">
              <p className="text-label-md font-semibold text-on-surface">
                Renovación biométrica requerida
              </p>
              <p className="text-label-sm text-on-surface-variant mt-base">
                Las verificaciones silenciosas detectaron deriva del embedding. Se requiere renovar la referencia.
                Las rendiciones en curso no se ven afectadas (decisión disciplinaria siempre humana — L2.5).
              </p>
            </div>
            <Button variant="outline" onClick={handleRenovarBiometria} className="shrink-0 h-9 px-md text-label-sm" icon="refresh">
              Renovar
            </Button>
          </div>
        )}

        {/* ── Sección: Consentimiento informado ───────────────────────────────── */}
        <Card className="space-y-md">
          <div className="flex items-center justify-between gap-md">
            <div className="flex items-center gap-sm">
              <Icon name="gavel" className="text-[22px] text-on-surface-variant" />
              <h2 className="font-headline text-title-md text-on-surface">Consentimiento informado</h2>
            </div>
            <Badge tone={consentimientoOk ? 'success' : 'warning'} dot>
              {consentimientoOk ? (viaAlternativa ? 'Vía alternativa' : 'Completado') : 'Pendiente'}
            </Badge>
          </div>

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
        </Card>

        {/* ── Sección: Referencia biométrica ──────────────────────────────────── */}
        {!viaAlternativa && (
          <Card className="space-y-md">
            <div className="flex items-center justify-between gap-md">
              <div className="flex items-center gap-sm">
                <Icon name="face" className="text-[22px] text-on-surface-variant" />
                <h2 className="font-headline text-title-md text-on-surface">Referencia biométrica</h2>
              </div>
              <Badge
                tone={
                  !biometriaOk ? 'warning' :
                  biometriaCaducada ? 'error' :
                  enrollment?.biometria?.vigencia === 'por_vencer' ? 'warning' :
                  biometriaRenovacionRequerida ? 'warning' :
                  'success'
                }
                dot
              >
                {!biometriaOk ? 'Pendiente' :
                 biometriaCaducada ? 'Caducada' :
                 enrollment?.biometria?.vigencia === 'por_vencer' ? 'Por vencer' :
                 biometriaRenovacionRequerida ? 'Renovación requerida' :
                 'Vigente'}
              </Badge>
            </div>

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

                {/* Nota de privacidad */}
                <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-sm border border-outline-variant/30">
                  <span className="font-semibold">Privacidad (Ley 25.326):</span> La imagen y el embedding
                  biométrico son <strong>datos sensibles</strong>: cifrados at-rest, con finalidad acotada
                  a la verificación de identidad. Se eliminan al egreso (salvo hold disciplinario).
                  El sistema nunca sanciona automáticamente — solo prioriza para revisión humana (L2.5).
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

            {/* Tool de demo: simular deriva del embedding */}
            {biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida && (
              <div className="flex items-center justify-between gap-md pt-sm border-t border-outline-variant/40">
                <div className="flex items-center gap-xs text-on-surface-variant">
                  <Icon name="science" className="text-[16px]" />
                  <span className="text-label-sm">Control de demostración</span>
                </div>
                <Button
                  variant="ghost"
                  onClick={handleSimularDeriva}
                  className="h-9 px-md text-label-sm text-on-surface-variant"
                >
                  Demo: simular deriva embedding
                </Button>
              </div>
            )}
          </Card>
        )}

        {/* ── Sección: DNI (opcional / flaggeado) ────────────────────────────── */}
        <Card className="space-y-md">
          <div className="flex items-center justify-between gap-md">
            <div className="flex items-center gap-sm">
              <Icon name="badge" className="text-[22px] text-on-surface-variant" />
              <h2 className="font-headline text-title-md text-on-surface">
                Verificación documental
                <span className="ml-sm text-label-sm font-normal text-on-surface-variant bg-surface-container px-sm py-base rounded-full">
                  Opcional
                </span>
              </h2>
            </div>
            <Badge tone={dniOk ? 'success' : 'neutral'} dot>
              {dniOk ? 'Registrado' : (ENABLE_DNI_SCAN ? 'Pendiente' : 'Próximamente')}
            </Badge>
          </div>

          {dniOk && enrollment?.dni ? (
            <div className="space-y-xs text-label-sm">
              <p className="text-on-surface-variant">
                DNI registrado el {new Date(enrollment.dni.fecha_captura).toLocaleDateString('es-AR', {
                  day: '2-digit', month: 'long', year: 'numeric',
                })}.
              </p>
              <p className="text-on-surface-variant">
                Tratado como dato sensible (Ley 25.326): cifrado, finalidad acotada, eliminado al egreso.
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
                onClick={() => setPaso('dni')}
                icon="badge"
                className="h-9 px-md text-label-sm"
              >
                Escanear DNI (opcional)
              </Button>
            </div>
          ) : (
            <p className="text-label-sm text-on-surface-variant">
              Disponible próximamente. No bloquea el perfil completo. Cuando esté activo, el DNI
              será tratado como dato sensible (Ley 25.326): cifrado, finalidad acotada, eliminado al egreso.
            </p>
          )}
        </Card>

        {/* CTA de navegación */}
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
