// C-58 D2: consentimiento liviano cuando el alumno ya consintió en el perfil con versión vigente.
import { useEffect, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';
import { useToast } from '../ui/toast';
import type { ConsentTextResponse, AcuseConsentimiento } from '../lib/types';

export default function Consent() {
  const navigate = useNavigate();
  const toast = useToast();
  const examen = useApp((s) => s.examenActivo);
  const [texto, setTexto] = useState<ConsentTextResponse | null>(null);
  // Acuse de perfil (del enrollment) — null si no consintió aún.
  const [acusePerfil, setAcusePerfil] = useState<AcuseConsentimiento | null | undefined>(undefined);
  const [acepto, setAcepto] = useState(false); // RN-CO-02: nunca pre-marcado
  const [guardando, setGuardando] = useState(false);
  // C-58 D2: enlace "ver texto completo" en rama liviana
  const [verTextoCompleto, setVerTextoCompleto] = useState(false);

  useEffect(() => {
    // Cargar texto de consentimiento y estado de enrollment en paralelo (D3: render progresivo).
    Promise.all([api.getConsentText(), api.getEnrollment()]).then(([t, enrollment]) => {
      setTexto(t);
      setAcusePerfil(enrollment.consentimiento);
    });
  }, []);

  // D2: la rama liviana aplica cuando el acuse de perfil es válido con la versión vigente.
  // via_alternativa también cuenta como consentimiento de perfil válido.
  const yaConsintioPerfil =
    acusePerfil != null &&
    texto != null &&
    (acusePerfil.via_alternativa || acusePerfil.version === texto.version);

  const aceptar = async () => {
    if (!acepto || !examen) return; // guard defensivo: deep-link directo sin examenActivo
    setGuardando(true);
    // RN-CC: acuse por-rendición siempre obligatorio, en AMBAS ramas.
    await api.recordConsent(examen.id);
    setGuardando(false);
    navigate('/biometria');
  };

  const alternativa = () => {
    toast.info('Tu caso se escala a un proctor — se te asignará una vía alternativa sin biometría.');
    navigate('/sala-espera');
  };

  // Formatear fecha del acuse de perfil para mostrarla en la rama liviana.
  const fechaAcuse = acusePerfil?.timestamp
    ? new Date(acusePerfil.timestamp).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })
    : null;

  return (
    <StudentShell step={2}>
      <div className="max-w-3xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <div className="w-14 h-14 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center mx-auto">
            <Icon name="shield" className="text-[28px]" fill />
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface">Consentimiento informado</h2>
          <p className="text-body-md text-on-surface-variant">
            Active Exam respeta tus derechos bajo la <strong>Ley 25.326</strong> y un DPIA aprobado.
          </p>
          {texto && <p className="text-label-sm text-on-surface-variant">Versión {texto.version} · {texto.hash_texto}</p>}
        </div>

        {/* Rama liviana: ya consintió en perfil con versión vigente */}
        {yaConsintioPerfil && !verTextoCompleto ? (
          <>
            <Card className="bg-success-container border-success/30 flex gap-md items-start">
              <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                <Icon name="verified" fill />
              </div>
              <div className="min-w-0">
                <p className="text-body-md font-semibold text-on-surface">
                  Ya consentiste el tratamiento de tus datos
                  {fechaAcuse && <span className="font-normal text-on-surface-variant"> el {fechaAcuse}</span>}
                </p>
                <p className="text-label-sm text-on-surface-variant mt-base">
                  Tu consentimiento de perfil (versión {acusePerfil.version}) está vigente.
                  Solo necesitás confirmar tu participación en esta evaluación.
                </p>
                {/* Enlace discreto para ver el texto completo — Ley 25.326: siempre accesible */}
                <button
                  onClick={() => setVerTextoCompleto(true)}
                  className="text-label-sm text-primary hover:underline mt-xs inline-flex items-center gap-base"
                  type="button"
                >
                  <Icon name="description" className="text-[16px]" /> Ver texto completo del consentimiento
                </button>
              </div>
            </Card>

            <Card className="bg-surface-container-low border-primary-fixed-dim/60">
              <label className="flex items-start gap-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={acepto}
                  onChange={(e) => setAcepto(e.target.checked)}
                  className="mt-base w-5 h-5 accent-[#4241bc] rounded"
                />
                <span className="text-body-md text-on-surface">
                  Confirmo que acepto ser supervisado en esta evaluación y que mis datos biométricos
                  serán tratados de acuerdo al consentimiento que presté en mi perfil.
                  Entiendo que <strong>el sistema nunca sanciona automáticamente</strong> y que toda decisión es humana.
                </span>
              </label>
            </Card>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-md">
              <button onClick={alternativa} className="text-label-md text-on-surface-variant hover:text-primary inline-flex items-center gap-base">
                <Icon name="support_agent" className="text-[20px]" /> No acepto — solicitar vía alternativa
              </button>
              <Button onClick={aceptar} disabled={!acepto || guardando} icon={guardando ? undefined : 'check'} iconRight={guardando ? undefined : 'arrow_forward'}>
                {guardando
                  ? <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Registrando…</span>
                  : 'Confirmar y continuar'}
              </Button>
            </div>
          </>
        ) : (
          <>
            {/* Rama completa: primera vez o versión desactualizada.
                También se muestra cuando el alumno pidió "ver texto completo" desde la rama liviana. */}
            {verTextoCompleto && (
              <button
                onClick={() => setVerTextoCompleto(false)}
                type="button"
                className="inline-flex items-center gap-xs text-label-sm text-on-surface-variant hover:text-primary"
              >
                <Icon name="arrow_back" className="text-[18px]" /> Volver a la confirmación rápida
              </button>
            )}

            {/* Render progresivo: la grilla aparece vacía hasta que llega el texto (D3) */}
            <div className="grid sm:grid-cols-2 gap-md">
              {(texto?.bloques ?? []).map((b) => (
                <Card key={b.titulo} className="flex gap-sm">
                  <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                    <Icon name={b.icono} />
                  </div>
                  <div>
                    <h3 className="text-label-md font-semibold text-on-surface">{b.titulo}</h3>
                    <p className="text-label-sm text-on-surface-variant mt-base leading-relaxed">{b.cuerpo}</p>
                  </div>
                </Card>
              ))}
            </div>

            <Card className="bg-surface-container-low border-primary-fixed-dim/60">
              <label className="flex items-start gap-sm cursor-pointer">
                <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)}
                  className="mt-base w-5 h-5 accent-[#4241bc] rounded" />
                <span className="text-body-md text-on-surface">
                  Presto mi <strong>consentimiento libre, expreso e informado</strong> para el tratamiento de mis datos
                  (incluido el <Term termKey="embedding">embedding biométrico</Term>, tratado como dato sensible) con la única finalidad de supervisar esta evaluación.
                  Entiendo que <strong>el sistema nunca sanciona automáticamente</strong> y que toda decisión es humana.
                </span>
              </label>
            </Card>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-md">
              <button onClick={alternativa} className="text-label-md text-on-surface-variant hover:text-primary inline-flex items-center gap-base">
                <Icon name="support_agent" className="text-[20px]" /> No acepto — solicitar vía alternativa
              </button>
              <Button onClick={aceptar} disabled={!acepto || guardando} icon={guardando ? undefined : 'check'} iconRight={guardando ? undefined : 'arrow_forward'}>
                {guardando ? <span className="inline-flex items-center gap-xs"><Icon name="progress_activity" className="ae-spin text-[20px]" /> Registrando…</span> : 'Acepto y continúo'}
              </Button>
            </div>
          </>
        )}
      </div>
    </StudentShell>
  );
}
