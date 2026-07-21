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
import { useState } from 'react';
import { Icon, Button, Card, LoadingSpinner } from '../../ui/components';
import { api } from '../../lib/api';
import { useAsyncData } from '../../lib/useAsyncData';
import { Term } from '../../ui/Term';
import type { AcuseConsentimiento } from '../../lib/types';

interface Props {
  /** Acuse existente en el perfil (null = primer consentimiento). */
  acuseActual: AcuseConsentimiento | null;
  /** Callback tras consentir (acción afirmativa o vía alternativa). */
  onConsentido: (acuse: AcuseConsentimiento) => void;
  /** Modo solo lectura: muestra el texto sin el formulario de aceptación (volver a leer). */
  soloLectura?: boolean;
}

export function EnrollmentConsentStep({ acuseActual, onConsentido, soloLectura = false }: Props) {
  const [acepto, setAcepto] = useState(false); // RN-CO-02: NUNCA pre-marcado
  const [guardando, setGuardando] = useState(false);

  // Contrato de carga resiliente (C-73): un fallo del fetch NO puede degradar a
  // un "Cargando…" eterno (patrón viejo `.then(setTexto)` sin `.catch`). El
  // estado distingue loading/ready/error, y el error ofrece reintentar.
  const textoState = useAsyncData(() => api.getConsentText(), []);
  const texto = textoState.data;

  /** ¿Es un re-consentimiento por cambio de versión? */
  const esRenovacion = acuseActual !== null && texto !== null && acuseActual.version !== texto.version;

  const handleAceptar = async () => {
    if (!acepto || !texto) return;
    setGuardando(true);
    const acuse = await api.registrarConsentimientoPerfil(texto.version, false);
    setGuardando(false);
    onConsentido(acuse);
  };

  // C-73: un fallo de carga muestra error + reintento, nunca un spinner eterno.
  if (textoState.status === 'error') {
    return (
      <Card className="flex items-start gap-sm bg-error-container/40 border-error/40">
        <Icon name="cloud_off" className="text-error text-[20px] shrink-0 mt-px" fill />
        <div className="min-w-0 space-y-sm">
          <p className="text-body-md text-on-surface">
            No pudimos cargar el texto de consentimiento. Revisá tu conexión y probá de nuevo.
          </p>
          <Button variant="outline" icon="refresh" onClick={textoState.retry}>
            Reintentar
          </Button>
        </div>
      </Card>
    );
  }

  // c-66: bloquear render hasta tener `texto` (mismo fix que Consent.tsx).
  if (texto === null) {
    return <LoadingSpinner label="Cargando consentimiento…" />;
  }

  return (
    <div className="space-y-lg animate-in fade-in duration-400">
      {/* Encabezado */}
      <div className="space-y-xs">
        <div className="flex items-center gap-sm">
          <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
            <Icon name="description" className="text-[20px]" />
          </div>
          <div className="flex-1 min-w-0 flex items-center justify-between gap-sm">
            <h3 className="font-headline text-title-md text-on-surface">Consentimiento informado</h3>
            {texto?.version && (
              <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-primary-fixed text-primary text-label-sm font-semibold shrink-0">
                <Icon name="bookmark" className="text-[16px]" />
                Versión {texto.version}
              </span>
            )}
          </div>
        </div>

        {esRenovacion && (
          <div className="flex items-start gap-sm bg-warning-container border border-warning-200 rounded-xl p-md">
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
          <Card key={b.titulo} className="flex gap-md items-start">
            <div
              className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-fixed to-primary-fixed-dim ring-1 ring-primary/15 shadow-sm shrink-0"
              aria-hidden
            />
            <div className="min-w-0">
              <h4 className="text-label-md font-semibold text-on-surface">{b.titulo}</h4>
              <p className="text-label-sm text-on-surface-variant mt-base leading-relaxed">{b.cuerpo}</p>
            </div>
          </Card>
        ))}
      </div>

      {/* Solo lectura: confirmación de que ya aceptó (sin formulario) */}
      {soloLectura && (
        <Card className="bg-success-container/40 border-success/40 flex items-start gap-sm">
          <Icon name="check_circle" className="text-success text-[20px] shrink-0 mt-px" fill />
          <p className="text-body-md text-on-surface">
            Ya aceptaste este consentimiento
            {acuseActual ? ` el ${new Date(acuseActual.timestamp).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })}` : ''}.
            Acá arriba podés volver a leer todo lo que aceptaste.
          </p>
        </Card>
      )}

      {/* Acción afirmativa — RN-CO-02: checkbox NUNCA premarcado */}
      {!soloLectura && <Card className="bg-white border-primary-fixed-dim/60">
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
            (incluido el <Term termKey="embedding">embedding biométrico</Term> y la imagen de referencia, tratados como datos sensibles)
            con la única finalidad de supervisar mis evaluaciones académicas.
            Entiendo que <strong>el sistema nunca sanciona automáticamente</strong> y que toda decisión disciplinaria
            es humana. Tu aceptación queda registrada con la versión {texto?.version} del texto.
          </span>
        </label>
      </Card>}

      {/* Acciones */}
      {!soloLectura && (
        <div className="flex items-center justify-end">
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
      )}

      {/* Nota de privacidad */}
      <p className="text-label-sm text-on-surface-variant text-center">
        Tu aceptación queda registrada de forma permanente e inalterable. Si cambia la versión o el
        contenido del consentimiento, te lo vamos a pedir de nuevo antes de continuar.
      </p>
    </div>
  );
}
