/**
 * DecisionRevisorForm — el acto de decidir sobre una sesión revisada.
 *
 * UNA decisión, dos salidas: **Aprobar con nota** o **Anular examen**. Ambas
 * exigen MOTIVO; anular exige además la referencia a la evidencia.
 *
 * Vive junto al expediente (detalle de sesión) y no en un panel lateral: para
 * anular hay que MIRAR la evidencia, y la decisión es inmutable. El backend
 * mantiene el modelo de dos fases (revisión → resolución) porque es lo que da la
 * trazabilidad y permite que mañana resuelva otra autoridad; acá se encadenan
 * solas, así el revisor ve una sola decisión y no la mecánica interna.
 */
import { useState } from 'react';
import { Button, Icon, SectionTitle, FormField } from '../../ui/components';
import type { DecisionRevisor } from '../../lib/types';

export function DecisionRevisorForm({
  puedeResolver,
  onResolver,
  onDecidido,
}: {
  /** Capacidad `resolver_caso` (el backend deniega igual: esto solo evita el 403). */
  puedeResolver: boolean;
  /** Registra la decisión; resuelve `true` solo si el backend la confirmó. */
  onResolver: (
    decision: DecisionRevisor,
    motivo: string,
    evidenciaRef?: string,
  ) => Promise<boolean>;
  /** Se llama tras una decisión confirmada (p. ej. pasar al caso siguiente). */
  onDecidido?: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const [evidenciaRef, setEvidenciaRef] = useState('');
  const [enviando, setEnviando] = useState(false);

  const motivoOk = motivo.trim().length > 0;

  const aprobar = async () => {
    if (!motivoOk || enviando) return;
    setEnviando(true);
    const ok = await onResolver('aprobado', motivo.trim());
    setEnviando(false);
    if (ok) onDecidido?.();
  };

  const derivar = async () => {
    if (!motivoOk || enviando) return;
    setEnviando(true);
    const ok = await onResolver('caso_abierto', motivo.trim());
    setEnviando(false);
    if (ok) onDecidido?.();
  };

  /**
   * Anula encadenando las dos fases. Solo emite el veredicto si la apertura del
   * caso fue confirmada: resolver un caso que nunca se abrió devuelve 409 y deja
   * a la persona sin entender qué pasó.
   */
  const anular = async () => {
    if (!motivoOk || !puedeResolver || enviando) return;
    if (evidenciaRef.trim().length === 0) return;
    setEnviando(true);
    const abierto = await onResolver('caso_abierto', motivo.trim());
    let ok = false;
    if (abierto) {
      ok = await onResolver('anulado_por_fraude', motivo.trim(), evidenciaRef.trim());
    }
    setEnviando(false);
    if (ok) onDecidido?.();
  };

  return (
    <div className="space-y-md">
      <SectionTitle sub="El sistema solo ordena por prioridad. La decisión es siempre tuya.">
        Decisión del revisor
      </SectionTitle>

      <FormField
        label="Motivo (obligatorio)"
        hint="Fundamento de la decisión. Queda en el registro inmutable de auditoría."
        error={!motivoOk ? 'Escribí un motivo para poder registrar la decisión.' : undefined}
      >
        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          rows={2}
          placeholder="Ej.: revisé las 3 señales y corresponden a un falso positivo."
          className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md resize-none
            focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
      </FormField>

      {puedeResolver && (
        <FormField
          label="Referencia de evidencia (obligatoria para anular)"
          hint="Qué captura o momento fundamenta la anulación. Las señales y sus capturas están más abajo, con su fecha."
        >
          <input
            type="text"
            value={evidenciaRef}
            onChange={(e) => setEvidenciaRef(e.target.value)}
            placeholder="Ej.: múltiples rostros, 23/07 11:16"
            className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md
              focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
        </FormField>
      )}

      <div className="grid gap-sm sm:grid-cols-2">
        <Button
          variant="success"
          icon="verified"
          disabled={!motivoOk || enviando}
          onClick={aprobar}
          className="justify-center"
        >
          Aprobar con nota
        </Button>
        {puedeResolver ? (
          <Button
            variant="danger"
            icon="gavel"
            disabled={!motivoOk || enviando || evidenciaRef.trim().length === 0}
            onClick={anular}
            className="justify-center font-bold ring-2 ring-error/30"
          >
            Anular examen
          </Button>
        ) : (
          // Sin `resolver_caso` lo único posible es derivar: mostrar "Anular"
          // a quien no puede anular garantiza un 403 y una persona confundida.
          <Button
            variant="outline"
            icon="forward_to_inbox"
            disabled={!motivoOk || enviando}
            onClick={derivar}
            className="justify-center"
          >
            Derivar a un revisor
          </Button>
        )}
      </div>

      {!puedeResolver && (
        <p className="text-label-sm text-on-surface-variant inline-flex items-center gap-base">
          <Icon name="lock" className="text-[16px]" />
          No tenés la atribución para anular. Podés aprobar la nota o derivar el caso a
          quien sí la tenga.
        </p>
      )}
    </div>
  );
}
