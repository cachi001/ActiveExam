/**
 * ColaPanelDecision — Panel de decisión del revisor (C-71 slice 2, D6/D9/D11).
 *
 * Modelo de DOS FASES:
 *  - Fase 1 (revisión, capacidad `revisar_sesion`): sin_hallazgos / aprobado /
 *    abrir caso (derivar). Cada decisión exige un MOTIVO no vacío (D11).
 *  - Fase 2 (resolución, capacidad `resolver_caso`): SOLO si el caso está abierto —
 *    ANULAR la nota por fraude (destacado, danger) o descartar el caso. Anular exige
 *    motivo + evidencia. El botón de anulación se habilita SOLO con la capacidad
 *    `resolver_caso`; el backend igual lo verifica (backstop, D8/regla #6).
 *
 * El sistema solo prioriza y ordena; la decisión es siempre humana, nunca automática.
 * Reusa Card/Button/Icon/SectionTitle/FormField del design system. Sin window.confirm.
 */
import { useState } from 'react';
import { Card, Button, Icon, SectionTitle, FormField } from '../../ui/components';
import type {
  DecisionRevisor,
  DecisionRevision,
  DecisionResolucion,
  SesionProctoringResumen,
} from '../../lib/types';
import type { ExamInfo } from './helpers';
import { scoreTextColor } from './helpers';

export function ColaPanelDecision({
  sesion,
  info,
  puedeResolver,
  onResolver,
  onVerDetalle,
}: {
  sesion: SesionProctoringResumen;
  info: ExamInfo | null;
  /** Capacidad `resolver_caso` (front-hides; el backend deniega igual). */
  puedeResolver: boolean;
  /** Registra una decisión (fase 1 o 2) con su motivo obligatorio (+ evidencia si anula). */
  onResolver: (decision: DecisionRevisor, motivo: string, evidenciaRef?: string) => void;
  onVerDetalle: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const [evidenciaRef, setEvidenciaRef] = useState('');
  const [casoAbierto, setCasoAbierto] = useState(false);

  const motivoOk = motivo.trim().length > 0;

  const revisar = (d: DecisionRevision) => {
    if (!motivoOk) return;
    if (d === 'caso_abierto') {
      // Deriva: abre la fase 2 en el propio panel (no valida ni anula la nota).
      onResolver('caso_abierto', motivo.trim());
      setCasoAbierto(true);
      return;
    }
    onResolver(d, motivo.trim());
  };

  const resolver = (d: DecisionResolucion) => {
    if (!motivoOk || !puedeResolver) return;
    if (d === 'anulado_por_fraude' && evidenciaRef.trim().length === 0) return;
    onResolver(d, motivo.trim(), evidenciaRef.trim() || undefined);
  };

  return (
    <Card className="space-y-lg">
      <div className="flex items-start justify-between gap-md flex-wrap border-b
        border-outline-variant/40 pb-md">
        <div className="min-w-0">
          <h3 className="font-headline text-title-lg text-on-surface truncate">
            {sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
          </h3>
          {info && (
            <p className="text-label-sm text-on-surface-variant mt-base">
              {info.examNombre} · {info.comisionNombre} · {info.docente}
            </p>
          )}
        </div>
        <span className={`font-headline text-headline-md font-bold ${scoreTextColor(sesion.score)}`}>
          {sesion.score}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-sm">
        <Metrica label="Señales registradas" valor={String(sesion.total_eventos ?? 0)} />
        <Metrica
          label="Diferencias con el servidor"
          valor={String(sesion.total_discrepancias ?? 0)}
          clase={(sesion.total_discrepancias ?? 0) > 0 ? 'text-error' : 'text-on-surface'}
        />
      </div>

      <button
        type="button"
        onClick={onVerDetalle}
        className="inline-flex items-center gap-base text-label-md font-semibold text-on-surface-variant
          hover:text-on-surface transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
      >
        Ver detalle completo
        <Icon name="arrow_forward" className="text-[18px]" />
      </button>

      <div className="border-t border-outline-variant/40 pt-md space-y-md">
        <SectionTitle sub="El sistema solo ordena por prioridad. La decisión es siempre tuya.">
          Decisión del revisor
        </SectionTitle>

        {/* Motivo obligatorio en TODA decisión (D11, RN-RV-06). */}
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
            className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md
              focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
        </FormField>

        {/* Fase 1 — Revisión. */}
        <div className="grid gap-sm sm:grid-cols-3">
          <Button
            variant="outline"
            icon="done"
            disabled={!motivoOk}
            onClick={() => revisar('sin_hallazgos')}
            className="justify-center"
          >
            Sin observaciones
          </Button>
          <Button
            variant="secondary"
            icon="verified"
            disabled={!motivoOk}
            onClick={() => revisar('aprobado')}
            className="justify-center"
          >
            Aprobar con nota
          </Button>
          <Button
            variant="outline"
            icon="gavel"
            disabled={!motivoOk}
            onClick={() => revisar('caso_abierto')}
            className="justify-center"
          >
            Abrir caso (derivar)
          </Button>
        </div>

        {/* Fase 2 — Resolución. Solo visible con caso abierto; el veredicto de
            anulación se habilita SOLO con la capacidad resolver_caso. */}
        {casoAbierto && (
          <div className="border-t border-outline-variant/40 pt-md space-y-md">
            <SectionTitle sub="Caso abierto: la nota no cambia hasta que se resuelva.">
              Resolución del caso
            </SectionTitle>

            {puedeResolver ? (
              <>
                <FormField
                  label="Referencia de evidencia (obligatoria para anular)"
                  hint="Identificador del clip/captura que fundamenta la anulación."
                >
                  <input
                    type="text"
                    value={evidenciaRef}
                    onChange={(e) => setEvidenciaRef(e.target.value)}
                    placeholder="Ej.: clip-42"
                    className="w-full rounded-xl border border-outline-variant/60 bg-white p-sm text-body-md
                      focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  />
                </FormField>
                <div className="grid gap-sm sm:grid-cols-2">
                  <Button
                    variant="outline"
                    icon="check_circle"
                    disabled={!motivoOk}
                    onClick={() => resolver('caso_descartado')}
                    className="justify-center"
                  >
                    Descartar el caso
                  </Button>
                  {/* Botón de anulación DESTACADO y diferenciado (danger). */}
                  <Button
                    variant="danger"
                    icon="block"
                    disabled={!motivoOk || evidenciaRef.trim().length === 0}
                    onClick={() => resolver('anulado_por_fraude')}
                    className="justify-center font-bold ring-2 ring-error/30"
                  >
                    Anular la nota por fraude
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-label-sm text-on-surface-variant inline-flex items-center gap-base">
                <Icon name="lock" className="text-[16px]" />
                No tenés la atribución para resolver el caso (anular o descartar). Queda
                derivado para la autoridad con esa capacidad.
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function Metrica({
  label,
  valor,
  clase = 'text-on-surface',
}: {
  label: string;
  valor: string;
  clase?: string;
}) {
  return (
    <div className="rounded-xl bg-white border border-outline-variant/60 p-sm">
      <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className={`font-headline text-title-lg font-bold ${clase}`}>{valor}</p>
    </div>
  );
}

export default ColaPanelDecision;
