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
import { LoadingSpinner } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { api, ENABLE_DNI_SCAN } from '../lib/api';
import { EnrollmentConsentStep } from './enrollment/EnrollmentConsentStep';
import { EnrollmentBiometricStep } from './enrollment/EnrollmentBiometricStep';
import { EnrollmentDniStep } from './enrollment/EnrollmentDniStep';
import { EnrollmentStepLayout, type WizardPaso } from './enrollment/EnrollmentStepLayout';
import { EnrollmentFotoPerfilStep } from './enrollment/EnrollmentFotoPerfilStep';
import { PerfilVistaGeneral } from './alumno/components/PerfilVistaGeneral';
import type { AcuseConsentimiento, EstadoEnrollment, ReferenciasBiometrica, EscaneDNI } from '../lib/types';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../config/effectiveConfigCache';

/**
 * Pasos del flujo de enrollment.
 * 'perfil' = vista del perfil (enrollment ya completado o estado actual).
 * 'foto_perfil' = captura de foto de perfil (C-37) — entre consentimiento y biometria.
 */
type PasoEnrollment =
  | 'cargando'
  | 'perfil'
  | 'consentimiento'
  | 'leer_consentimiento'
  | 'foto_perfil'
  | 'biometria'
  | 'dni'
  | 'renovar_biometria';

/** Total de pasos del enrollment según el flag de DNI (afecta el contador "Paso X de N"). */

export default function StudentProfile() {
  const navigate = useNavigate();
  const principal = useAuth((s) => s.principal);
  const setEnrollmentStatus = useApp((s) => s.setEnrollmentStatus);
  const setFotoPerfil = useAuth((s) => s.setFotoPerfil);

  const [enrollment, setEnrollment] = useState<EstadoEnrollment | null>(null);
  const [paso, setPaso] = useState<PasoEnrollment>('cargando');
  // Versión vigente del consentimiento (config del sistema). Si cambia, el
  // alumno debe re-aceptar — RequisitoConsentimiento lo detecta comparando.
  const [versionVigente, setVersionVigente] = useState<string | null>(null);
  /** C-56: error de backend al guardar la foto de perfil (para mostrar al alumno). */
  const [fotoError, setFotoError] = useState<string | null>(null);
  // C-66: foto capturada pendiente de confirmar (paso 2) antes de avanzar a biometría.
  const [fotoConfirmando, setFotoConfirmando] = useState<string | null>(null);

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
      // Cargar foto de perfil (backend real o persistida en demo) y mostrar avatar.
      if (!principal?.foto_perfil) {
        const foto = await api.obtenerFotoPerfil();
        if (!cancelado && foto) setFotoPerfil(foto);
      }
      // Cargar versión vigente del consentimiento desde la config efectiva.
      // Invalidamos el cache para detectar cambios hechos por admin entre sesiones.
      try {
        resetEffectiveConfigCache();
        await loadEffectiveConfig();
        if (!cancelado) {
          setVersionVigente(getEffectiveConfig()?.consent_version_vigente ?? null);
        }
      } catch { /* sin red: deja versionVigente=null y RequisitoConsentimiento no marca desactualizado */ }
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

  const handleConsentido = async (_acuse: AcuseConsentimiento) => {
    const estado = await cargarEnrollment();
    if (!principal?.foto_perfil) {
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
      await api.guardarFotoPerfil(dataUrl);
      // El POST devolvió OK: la imagen ya fue persistida server-side. Como el
      // alumno acaba de capturarla, tenemos el mismo binario en el cliente
      // (`dataUrl`). Usarlo directamente como avatar evita una ida-y-vuelta
      // adicional (GET /enrollment/foto-perfil → base64) y elimina la demora
      // perceptual entre capturar y ver la foto en el header/perfil.
      setFotoPerfil(dataUrl);
      // C-66: mostrar la foto capturada (confirmación del paso 2) antes de avanzar.
      setFotoConfirmando(dataUrl);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFotoError(msg);
      // No avanzar la fase: el alumno debe reintentar.
    }
  };

  /**
   * Handler al cancelar la foto de perfil.
   * La foto ahora es OBLIGATORIA (decisión del dueño): cancelar NO avanza a biometría
   * (eso era un salteo encubierto), sino que vuelve a la vista general del perfil. Para
   * llegar a biometría hay que pasar el paso de foto capturando una — no hay atajo.
   */
  const handleFotoCancelada = () => setPaso('perfil');

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
    } else if (!principal?.foto_perfil) {
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
  const biometriaOk = Boolean(enrollment?.biometria?.captura_completada);
  const biometriaCaducada = enrollment?.biometria?.vigencia === 'caducada';
  const biometriaRenovacionRequerida =
    enrollment?.biometria?.vigencia === 'renovacion_requerida' ||
    (enrollment?.biometria?.renovacion_anticipada_requerida ?? false);
  const dniOk = Boolean(enrollment?.dni?.captura_completada);
  const perfilCompleto = enrollment?.perfil_completo ?? false;

  const volverAlPerfil = () => setPaso('perfil');

  // C-66: pasos del wizard de enrollment. `actual` = nº de paso en curso (1-based).
  // Un paso se pinta verde cuando su requisito está completo O cuando ya se dejó
  // atrás navegando (pasos opcionales como Foto/DNI se pueden saltear sin dejar
  // un dato real — "completado" en el stepper no es "hay una foto guardada", es
  // "ya no estás ahí").
  const wizardPasos = (actual: number): WizardPaso[] => {
    const items = [
      { label: 'Consentimiento', done: consentimientoOk },
      { label: 'Foto', done: Boolean(principal?.foto_perfil) },
      { label: 'Biometría', done: biometriaOk },
    ];
    if (ENABLE_DNI_SCAN) items.push({ label: 'DNI', done: dniOk });
    return items.map((it, i) => ({
      label: it.label,
      estado: it.done || i + 1 < actual ? 'completado' : i + 1 === actual ? 'actual' : 'pendiente',
    }));
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Pasos del flujo de enrollment
  // ─────────────────────────────────────────────────────────────────────────────

  if (paso === 'cargando') {
    return (
      <StudentShell ocultarNavegacion>
        <div className="min-h-[calc(100dvh-13rem)] flex items-center justify-center">
          <LoadingSpinner label="Cargando perfil…" />
        </div>
      </StudentShell>
    );
  }

  if (paso === 'consentimiento') {
    // Re-consentimiento (ya enrollado: tiene consentimiento previo + biometría) vs
    // enrollment por primera vez. El stepper de 4 pasos SOLO tiene sentido la primera
    // vez; al re-consentir una versión nueva no mostramos el wizard (foto/biometría
    // ya están hechos y confunde — ver feedback del dueño).
    const esReconsentimiento = !!enrollment?.consentimiento && !!enrollment?.biometria;
    return (
      <StudentShell ocultarNavegacion>
        <EnrollmentStepLayout
          maxWidth="3xl"
          title="Consentimiento informado"
          subtitle="Leé y aceptá el uso de tus datos para verificar tu identidad."
          pasos={esReconsentimiento ? undefined : wizardPasos(1)}
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

  // C-66: lectura del consentimiento ya aceptado (solo lectura, sin formulario)
  if (paso === 'leer_consentimiento') {
    return (
      <StudentShell ocultarNavegacion>
        <EnrollmentStepLayout
          maxWidth="3xl"
          title="Consentimiento informado"
          subtitle="Este es el consentimiento que aceptaste."
          onBack={volverAlPerfil}
        >
          <EnrollmentConsentStep
            acuseActual={enrollment?.consentimiento ?? null}
            onConsentido={volverAlPerfil}
            soloLectura
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  // C-56: Paso foto de perfil — entre consentimiento y biometría
  if (paso === 'foto_perfil') {
    return (
      <StudentShell ocultarNavegacion>
        <EnrollmentStepLayout
          title="Foto de perfil"
          subtitle="Tu foto se usará como tu imagen en la plataforma."
          pasos={enrollment?.biometria?.captura_completada ? undefined : wizardPasos(2)}
          onBack={volverAlPerfil}
        >
          <EnrollmentFotoPerfilStep
            fotoConfirmando={fotoConfirmando}
            setFotoConfirmando={setFotoConfirmando}
            fotoError={fotoError}
            enrollment={enrollment}
            onAvanzar={() => setPaso(enrollment?.biometria?.captura_completada ? 'perfil' : 'biometria')}
            onCapture={handleFotoCapturada}
            onCancel={handleFotoCancelada}
          />
        </EnrollmentStepLayout>
      </StudentShell>
    );
  }

  if (paso === 'biometria') {
    return (
      <StudentShell ocultarNavegacion>
        <EnrollmentStepLayout
          title="Captura biométrica de referencia"
          subtitle="Configurás tu referencia una sola vez. En cada examen comparamos tu rostro con ella para confirmar que sos vos."
          pasos={wizardPasos(3)}
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
      <StudentShell ocultarNavegacion>
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
      <StudentShell ocultarNavegacion>
        <EnrollmentStepLayout
          title="Verificación documental"
          subtitle="Opcional. Escanear tu DNI (frente y dorso) refuerza la verificación, pero no es obligatorio para completar el perfil."
          pasos={wizardPasos(4)}
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

  // Vista principal del perfil (paso === 'perfil')
  return (
    <StudentShell>
      <PerfilVistaGeneral
        principal={principal}
        enrollment={enrollment}
        versionVigente={versionVigente}
        consentimientoOk={consentimientoOk}
        biometriaOk={biometriaOk}
        biometriaCaducada={biometriaCaducada}
        biometriaRenovacionRequerida={biometriaRenovacionRequerida}
        dniOk={dniOk}
        perfilCompleto={perfilCompleto}
        onNavigate={navigate}
        onIniciarConsentimiento={() => setPaso('consentimiento')}
        onLeerConsentimiento={() => setPaso('leer_consentimiento')}
        onIniciarEnrollment={handleIniciarEnrollment}
        onRenovarBiometria={handleRenovarBiometria}
        onSimularDeriva={handleSimularDeriva}
        onRehacerFoto={() => setPaso('foto_perfil')}
        onEscanearDni={() => setPaso('dni')}
      />
    </StudentShell>
  );
}
