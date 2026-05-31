// Portal del alumno — Perfil: datos personales + shell de consentimiento y biometría (C-21)
// El contenido real de cada sección (texto de consentimiento, captura biométrica) es
// implementado por C-22. Esta pantalla contiene los contenedores (shell) con estado.
import { useEffect, useState } from 'react';
import { Card, Badge, Button, Icon } from '../ui/components';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';

export default function AlumnoPerfil() {
  const navigate = useNavigate();
  const principal = useApp((s) => s.principal);

  const [consentimientoOk, setConsentimientoOk] = useState(false);
  const [biometriaOk, setBiometriaOk] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [simulandoConsent, setSimulandoConsent] = useState(false);
  const [simulandoBio, setSimulandoBio] = useState(false);

  // Leer el estado actual del perfil al montar.
  // puedeRendir() refleja el estado in-memory de perfilAlumno; si ya fue simulado
  // en esta sesión (p.ej., el alumno volvió a esta pantalla), mostramos el estado real.
  useEffect(() => {
    let cancelado = false;
    (async () => {
      const gate = await api.puedeRendir();
      if (cancelado) return;
      if (gate.puede) {
        // Ambas secciones completadas
        setConsentimientoOk(true);
        setBiometriaOk(true);
      } else {
        // Determinamos qué secciones faltan por la razón
        const razon = gate.razon ?? '';
        // razon puede ser 'falta consentimiento informado' o 'falta consentimiento informado y verificación biométrica'
        const faltaConsent = razon.includes('consentimiento');
        const faltaBio = razon.includes('verificaci');
        setConsentimientoOk(!faltaConsent);
        setBiometriaOk(!faltaBio);
      }
      setCargando(false);
    })();
    return () => { cancelado = true; };
  }, []);

  const handleSimularConsentimiento = async () => {
    setSimulandoConsent(true);
    await api.simularConsentimientoOk();
    setConsentimientoOk(true);
    setSimulandoConsent(false);
  };

  const handleSimularBiometria = async () => {
    setSimulandoBio(true);
    await api.simularBiometriaOk();
    setBiometriaOk(true);
    setSimulandoBio(false);
  };

  const perfilCompleto = consentimientoOk && biometriaOk;

  return (
    <StudentShell>
      <div className="max-w-2xl mx-auto space-y-xl">
        <header>
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mi perfil</h1>
          <p className="text-body-md text-on-surface-variant mt-xs">
            Datos personales y requisitos para rendir exámenes.
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

        {/* Perfil completo — banner positivo */}
        {!cargando && perfilCompleto && (
          <div className="flex items-center gap-md bg-success-container border border-success/30 rounded-xl p-md">
            <Icon name="verified" className="text-success text-[24px] shrink-0" fill />
            <div className="flex-1">
              <p className="text-label-md font-semibold text-on-surface">Perfil completo — podés rendir tus exámenes</p>
              <p className="text-label-sm text-on-surface-variant mt-base">Todos los requisitos están satisfechos.</p>
            </div>
            <Button variant="secondary" onClick={() => navigate('/alumno/mis-examenes')} className="shrink-0 h-9 px-md text-label-sm">
              Mis exámenes
            </Button>
          </div>
        )}

        {/* Sección: Consentimiento informado */}
        <Card className="space-y-md">
          <div className="flex items-center justify-between gap-md">
            <div className="flex items-center gap-sm">
              <Icon name="gavel" className="text-[22px] text-on-surface-variant" />
              <h2 className="font-headline text-title-md text-on-surface">Consentimiento informado</h2>
            </div>
            {cargando ? (
              <Icon name="progress_activity" className="ae-spin text-[18px] text-on-surface-variant" />
            ) : (
              <Badge tone={consentimientoOk ? 'success' : 'warning'} dot>
                {consentimientoOk ? 'Completado' : 'Pendiente'}
              </Badge>
            )}
          </div>

          {/* Placeholder C-22 */}
          <div className="bg-surface-container rounded-xl p-md border border-outline-variant/30">
            <p className="text-label-sm text-on-surface-variant italic">
              Contenido disponible próximamente — C-22 implementará el texto de consentimiento completo y el flujo de firma digital.
            </p>
          </div>

          {!consentimientoOk && (
            <div className="flex items-center justify-between gap-md pt-sm border-t border-outline-variant/40">
              <div className="flex items-center gap-xs text-on-surface-variant">
                <Icon name="science" className="text-[16px]" />
                <span className="text-label-sm">Control de demostración</span>
              </div>
              <Button
                variant="outline"
                onClick={handleSimularConsentimiento}
                disabled={simulandoConsent}
                className="h-9 px-md text-label-sm"
              >
                {simulandoConsent ? (
                  <span className="inline-flex items-center gap-xs">
                    <Icon name="progress_activity" className="ae-spin text-[16px]" />
                    Simulando…
                  </span>
                ) : 'Demo: simular completado'}
              </Button>
            </div>
          )}
        </Card>

        {/* Sección: Verificación biométrica */}
        <Card className="space-y-md">
          <div className="flex items-center justify-between gap-md">
            <div className="flex items-center gap-sm">
              <Icon name="face" className="text-[22px] text-on-surface-variant" />
              <h2 className="font-headline text-title-md text-on-surface">Verificación biométrica</h2>
            </div>
            {cargando ? (
              <Icon name="progress_activity" className="ae-spin text-[18px] text-on-surface-variant" />
            ) : (
              <Badge tone={biometriaOk ? 'success' : 'warning'} dot>
                {biometriaOk ? 'Completado' : 'Pendiente'}
              </Badge>
            )}
          </div>

          {/* Placeholder C-22 */}
          <div className="bg-surface-container rounded-xl p-md border border-outline-variant/30">
            <p className="text-label-sm text-on-surface-variant italic">
              Contenido disponible próximamente — C-22 implementará la captura de foto de referencia y el flujo de verificación biométrica (liveness check).
            </p>
          </div>

          <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-lg p-sm">
            <span className="font-semibold">Privacidad:</span> El embedding biométrico se trata como dato sensible (Ley 25.326). Se elimina al egreso, salvo hold disciplinario. El sistema nunca sanciona automáticamente — solo prioriza para revisión humana.
          </div>

          {!biometriaOk && (
            <div className="flex items-center justify-between gap-md pt-sm border-t border-outline-variant/40">
              <div className="flex items-center gap-xs text-on-surface-variant">
                <Icon name="science" className="text-[16px]" />
                <span className="text-label-sm">Control de demostración</span>
              </div>
              <Button
                variant="outline"
                onClick={handleSimularBiometria}
                disabled={simulandoBio}
                className="h-9 px-md text-label-sm"
              >
                {simulandoBio ? (
                  <span className="inline-flex items-center gap-xs">
                    <Icon name="progress_activity" className="ae-spin text-[16px]" />
                    Simulando…
                  </span>
                ) : 'Demo: simular completado'}
              </Button>
            </div>
          )}
        </Card>

        {/* Estado del gate cuando el perfil se acaba de completar */}
        {!cargando && perfilCompleto && (
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
