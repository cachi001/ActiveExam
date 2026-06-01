/**
 * Paso de consentimiento informado dentro del flujo de enrollment del perfil (C-22).
 *
 * Ubicado en el Perfil del alumno — NO es un paso del pre-examen.
 * Implementa:
 *   - RN-CO-01: texto versionado con acuse inmutable (version + timestamp + hash)
 *   - RN-CO-02: acción afirmativa sin casilla premarcada
 *   - RN-CO-05: vía alternativa sin biometría
 *   - Re-disparo al cambiar la versión del texto (spec informed-consent-presentation)
 */
import { useEffect, useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { api } from '../../lib/api';
import { Term } from '../../ui/Term';
import type { ConsentTextResponse } from '../../lib/types';
import type { AcuseConsentimiento } from '../../lib/types';

interface Props {
  /** Acuse existente en el perfil (null = primer consentimiento). */
  acuseActual: AcuseConsentimiento | null;
  /** Callback tras consentir (acción afirmativa o vía alternativa). */
  onConsentido: (acuse: AcuseConsentimiento) => void;
}

export function EnrollmentConsentStep({ acuseActual, onConsentido }: Props) {
  const [texto, setTexto] = useState<ConsentTextResponse | null>(null);
  const [acepto, setAcepto] = useState(false); // RN-CO-02: NUNCA pre-marcado
  const [guardando, setGuardando] = useState(false);
  const [cargandoTexto, setCargandoTexto] = useState(true);

  useEffect(() => {
    api.getConsentText().then((t) => {
      setTexto(t);
      setCargandoTexto(false);
    });
  }, []);

  /** ¿Es un re-consentimiento por cambio de versión? */
  const esRenovacion = acuseActual !== null && texto !== null && acuseActual.version !== texto.version;

  const handleAceptar = async () => {
    if (!acepto || !texto) return;
    setGuardando(true);
    const acuse = await api.registrarConsentimientoPerfil(texto.version, false);
    setGuardando(false);
    onConsentido(acuse);
  };

  const handleViaAlternativa = async () => {
    if (!texto) return;
    setGuardando(true);
    // Vía alternativa: registra consentimiento con via_alternativa=true (RN-CO-05).
    // El proctor humano toma el rol de verificación de identidad.
    const acuse = await api.registrarConsentimientoPerfil(texto.version, true);
    setGuardando(false);
    onConsentido(acuse);
  };

  if (cargandoTexto) {
    return (
      <div className="flex items-center gap-sm text-on-surface-variant py-lg">
        <Icon name="progress_activity" className="ae-spin text-[20px]" />
        <span className="text-body-md">Cargando texto de consentimiento…</span>
      </div>
    );
  }

  return (
    <div className="space-y-lg animate-in fade-in duration-400">
      {/* Encabezado */}
      <div className="space-y-xs">
        <div className="flex items-center gap-sm">
          <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
            <Icon name="shield" className="text-[20px]" fill />
          </div>
          <div>
            <h3 className="font-headline text-title-md text-on-surface">Consentimiento informado</h3>
            {texto && (
              <p className="text-label-sm text-on-surface-variant">
                Versión {texto.version} · {texto.hash_texto}
              </p>
            )}
          </div>
        </div>

        {esRenovacion && (
          <div className="flex items-start gap-sm bg-warning-container border border-warning/30 rounded-xl p-md">
            <Icon name="update" className="text-warning text-[18px] shrink-0 mt-px" />
            <p className="text-label-sm text-on-surface">
              <strong>El texto de consentimiento fue actualizado</strong> (versión {texto?.version}).
              Necesitás re-consentir antes de continuar.
            </p>
          </div>
        )}
      </div>

      {/* Bloques informativos */}
      <div className="grid sm:grid-cols-2 gap-md">
        {(texto?.bloques ?? []).map((b) => (
          <Card key={b.titulo} className="flex gap-sm">
            <div className="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
              <Icon name={b.icono} className="text-[18px]" />
            </div>
            <div>
              <h4 className="text-label-md font-semibold text-on-surface">{b.titulo}</h4>
              <p className="text-label-sm text-on-surface-variant mt-base leading-relaxed">{b.cuerpo}</p>
            </div>
          </Card>
        ))}
      </div>

      {/* Acción afirmativa — RN-CO-02: checkbox NUNCA premarcado */}
      <Card className="bg-surface-container-low border-primary-fixed-dim/60">
        <label className="flex items-start gap-sm cursor-pointer select-none">
          {/* El estado inicial es false (sin pre-marcar) — acción afirmativa explícita */}
          <input
            type="checkbox"
            checked={acepto}
            onChange={(e) => setAcepto(e.target.checked)}
            className="mt-base w-5 h-5 accent-[#4241bc] rounded shrink-0"
          />
          <span className="text-body-md text-on-surface">
            Presto mi <strong>consentimiento libre, expreso e informado</strong> para el tratamiento de mis datos
            (incluido el <Term termKey="embedding">embedding biométrico</Term> y la imagen de referencia, tratados como datos sensibles bajo la{' '}
            <strong>Ley 25.326</strong>) con la única finalidad de supervisar mis evaluaciones académicas.
            Entiendo que <strong>el sistema nunca sanciona automáticamente</strong> y que toda decisión disciplinaria
            es humana. El acuse queda registrado con la versión {texto?.version} del texto.
          </span>
        </label>
      </Card>

      {/* Acciones */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-md">
        <button
          onClick={handleViaAlternativa}
          disabled={guardando}
          className="text-label-md text-on-surface-variant hover:text-primary inline-flex items-center gap-base disabled:opacity-50"
        >
          <Icon name="support_agent" className="text-[20px]" />
          No acepto — solicitar vía alternativa sin biometría
        </button>
        <Button
          onClick={handleAceptar}
          disabled={!acepto || guardando}
          icon={guardando ? undefined : 'check'}
          iconRight={guardando ? undefined : 'arrow_forward'}
        >
          {guardando ? (
            <span className="inline-flex items-center gap-xs">
              <Icon name="progress_activity" className="ae-spin text-[20px]" />
              Registrando…
            </span>
          ) : 'Acepto y continúo'}
        </Button>
      </div>

      {/* Nota de privacidad */}
      <p className="text-label-sm text-on-surface-variant text-center">
        El acuse queda registrado con timestamp y hash inmutable (RN-CO-01). Podés solicitar acceso,
        rectificación y eliminación de tus datos ante la AAIP.
      </p>
    </div>
  );
}
